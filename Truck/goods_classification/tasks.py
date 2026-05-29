"""
Truck/goods_classification/tasks.py
=====================================
Celery task: full goods classification pipeline.

classify_item_task(job_id):
  1. Load image from job.photo
  2. Validate and preprocess to 224×224 RGB
  3. Run CLIP classification
  4. Run YOLOv8 prohibited detection
  5. Compute fragility score
  6. Estimate size
  7. Save results to ClassificationResult model
  8. Update Job.classification_status + is_flagged_prohibited
  9. Notify admin if prohibited detected

Execution time: ~3–8 seconds on CPU (first run longer — model download)
"""

import logging
import time
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='Truck.goods_classification.tasks.classify_item_task',
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=120,   # kill if > 2 minutes (stuck model load)
    time_limit=150,
)
def classify_item_task(self, job_id: str) -> dict:
    """
    Full goods classification pipeline for a job's photo.

    Args:
        job_id: UUID string of the Job

    Returns:
        dict with classification results (also saved to DB)
    """
    start_ts = time.time()
    logger.info("classify_item_task START | job=%s", job_id)

    from Truck.models import Job, ClassificationResult

    # ── Fetch job ──────────────────────────────────────────────────────────
    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        logger.error("classify_item_task: job %s not found", job_id)
        return {'success': False, 'error': 'Job not found'}

    # ── Get or create ClassificationResult ────────────────────────────────
    result_obj, _ = ClassificationResult.objects.get_or_create(job=job)
    result_obj.status   = 'processing'
    result_obj.task_id  = self.request.id or ''
    result_obj.save(update_fields=['status', 'task_id'])

    # Also mark job as processing
    Job.objects.filter(pk=job_id).update(classification_status='processing')

    # ── Validate image exists ──────────────────────────────────────────────
    if not job.photo:
        _mark_failed(result_obj, job, 'No photo attached to this job.')
        return {'success': False, 'error': 'No photo'}

    try:
        image_path = job.photo.path
    except Exception as exc:
        _mark_failed(result_obj, job, f'Cannot access photo path: {exc}')
        return {'success': False, 'error': str(exc)}

    # ── Stage 1: Load and preprocess image ────────────────────────────────
    try:
        from .utils import validate_and_preprocess
        pil_image = validate_and_preprocess(image_path)
    except Exception as exc:
        _mark_failed(result_obj, job, f'Image preprocessing failed: {exc}')
        return {'success': False, 'error': str(exc)}

    # ── Stage 2: CLIP classification ──────────────────────────────────────
    logger.info("classify_item_task: running CLIP | job=%s", job_id)
    try:
        from .classifier import classify_image
        clip_result = classify_image(pil_image)
    except Exception as exc:
        logger.warning("CLIP failed (non-fatal): %s", exc)
        clip_result = {
            'success':        False,
            'category_slug':  'general',
            'category_name':  'General Cargo',
            'confidence':     0.0,
            'low_confidence': True,
            'item_name':      '',
            'all_scores':     {},
            'top_3':          [],
            'error':          str(exc),
        }

    # ── Stage 3: Prohibited goods detection ───────────────────────────────
    logger.info("classify_item_task: running YOLOv8 prohibited check | job=%s", job_id)
    try:
        from .prohibited_fragility_size import detect_prohibited
        prohibited_result = detect_prohibited(pil_image)
    except Exception as exc:
        logger.warning("Prohibited detection failed (non-fatal): %s", exc)
        prohibited_result = {
            'prohibited_detected': False,
            'items':               [],
            'reason':              '',
            'error':               str(exc),
        }

    # ── Stage 4: Fragility score ───────────────────────────────────────────
    try:
        from .prohibited_fragility_size import compute_fragility
        fragility_result = compute_fragility(
            clip_result['category_slug'],
            clip_result['confidence'],
        )
    except Exception as exc:
        logger.warning("Fragility computation failed (non-fatal): %s", exc)
        fragility_result = {'is_fragile': False, 'fragility_score': 0.0, 'reason': ''}

    # ── Stage 5: Size estimation ───────────────────────────────────────────
    try:
        from .prohibited_fragility_size import estimate_size
        size_result = estimate_size(
            clip_result['category_slug'],
            clip_result['confidence'],
        )
    except Exception as exc:
        logger.warning("Size estimation failed (non-fatal): %s", exc)
        size_result = {
            'suggested_size': 'medium',
            'size_options':   ['small', 'medium', 'large'],
            'reason':         '',
            'reliable':       False,
        }

    # ── Stage 6: Save results to DB ────────────────────────────────────────
    elapsed = round(time.time() - start_ts, 2)

    result_obj.status                = 'complete'
    result_obj.category_suggestion   = clip_result['category_slug']
    result_obj.category_confidence   = clip_result['confidence']
    result_obj.item_name_suggestion  = clip_result.get('item_name', '')
    result_obj.size_suggestion       = size_result['suggested_size']
    result_obj.size_reliable         = size_result['reliable']
    result_obj.fragility_score       = fragility_result['fragility_score']
    result_obj.is_fragile            = fragility_result['is_fragile']
    result_obj.prohibited_detected   = prohibited_result['prohibited_detected']
    result_obj.prohibited_items      = prohibited_result.get('items', [])
    result_obj.prohibited_reason     = prohibited_result.get('reason', '')
    result_obj.low_confidence        = clip_result['low_confidence']
    result_obj.processing_time_s     = elapsed
    result_obj.raw_results           = {
        'clip':       clip_result,
        'prohibited': prohibited_result,
        'fragility':  fragility_result,
        'size':       size_result,
    }
    result_obj.save()

    # Update job flags
    Job.objects.filter(pk=job_id).update(
        classification_status=(
            'flagged' if prohibited_result['prohibited_detected'] else 'complete'
        ),
        is_flagged_prohibited=prohibited_result['prohibited_detected'],
        fragility_flag=fragility_result['is_fragile'],
    )

    # ── Stage 7: Notify admin if prohibited ───────────────────────────────
    if prohibited_result['prohibited_detected']:
        logger.warning(
            "PROHIBITED GOODS FLAG | job=%s | items=%s",
            job_id, [d['item'] for d in prohibited_result['items']]
        )
        try:
            _notify_admin_prohibited(job, prohibited_result)
        except Exception as exc:
            logger.warning("Admin prohibited notification failed: %s", exc)

    logger.info(
        "classify_item_task COMPLETE | job=%s | category=%s | conf=%.2f | "
        "prohibited=%s | fragile=%s | elapsed=%.2fs",
        job_id,
        clip_result['category_slug'],
        clip_result['confidence'],
        prohibited_result['prohibited_detected'],
        fragility_result['is_fragile'],
        elapsed,
    )

    return {
        'success':             True,
        'job_id':              str(job_id),
        'category_slug':       clip_result['category_slug'],
        'category_name':       clip_result['category_name'],
        'confidence':          clip_result['confidence'],
        'low_confidence':      clip_result['low_confidence'],
        'item_name':           clip_result.get('item_name', ''),
        'size_suggestion':     size_result['suggested_size'],
        'is_fragile':          fragility_result['is_fragile'],
        'fragility_score':     fragility_result['fragility_score'],
        'prohibited_detected': prohibited_result['prohibited_detected'],
        'prohibited_items':    prohibited_result['items'],
        'prohibited_reason':   prohibited_result.get('reason', ''),
        'processing_time_s':   elapsed,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mark_failed(result_obj, job, error_msg: str) -> None:
    """Marks classification as failed in DB."""
    from Truck.models import Job
    result_obj.status        = 'failed'
    result_obj.error_message = error_msg
    result_obj.save(update_fields=['status', 'error_message'])
    Job.objects.filter(pk=job.pk).update(classification_status='failed')
    logger.error("classify_item_task FAILED | job=%s | %s", job.pk, error_msg)


def _notify_admin_prohibited(job, prohibited_result: dict) -> None:
    """
    Sends email + WhatsApp to admin when a prohibited item is detected.
    Non-fatal — logs warnings if it fails.
    """
    from django.conf import settings
    from django.core.mail import send_mail

    admin_email = getattr(settings, 'ADMIN_EMAIL', '')
    items_str   = ', '.join(d['item'] for d in prohibited_result['items'])
    customer    = getattr(job, 'Customer', None)
    cust_name   = customer.user.get_full_name() if customer else 'Unknown'
    cust_email  = customer.user.email if customer else ''

    if admin_email:
        send_mail(
            subject=f'🚨 PROHIBITED GOODS FLAG — Job {str(job.id)[:8]}',
            message=(
                f'A customer job has been flagged for potentially prohibited goods.\n\n'
                f'Job ID:    {job.id}\n'
                f'Customer:  {cust_name} <{cust_email}>\n'
                f'Item name: {job.names}\n'
                f'Detected:  {items_str}\n\n'
                f'{prohibited_result.get("reason", "")}\n\n'
                f'Review in admin panel:\n'
                f'http://localhost:8000/admin/Truck/job/{job.id}/change/\n\n'
                f'You can clear the flag to allow the job to proceed, '
                f'or cancel the job if the detection is correct.'
            ),
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[admin_email],
            fail_silently=True,
        )

    # WhatsApp alert
    try:
        from twilio.rest import Client
        account_sid  = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token   = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        admin_wa     = getattr(settings, 'ADMIN_WHATSAPP', '')
        from_wa      = getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        if all([account_sid, auth_token, admin_wa]):
            Client(account_sid, auth_token).messages.create(
                from_=from_wa,
                to=f'whatsapp:{admin_wa}',
                body=(
                    f'🚨 PROHIBITED GOODS DETECTED\n'
                    f'Job: {str(job.id)[:8]}\n'
                    f'Customer: {cust_name}\n'
                    f'Detected: {items_str}\n'
                    f'Review: localhost:8000/admin'
                ),
            )
    except Exception as exc:
        logger.debug("WhatsApp prohibited notification failed: %s", exc)