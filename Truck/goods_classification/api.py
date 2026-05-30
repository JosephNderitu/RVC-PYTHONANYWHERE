"""
Truck/goods_classification/api.py
===================================
Two API endpoints for goods classification:

  POST /customer/api/classify-item/
    - Validates image (20MB limit)
    - Saves photo to Job
    - Queues classify_item_task
    - Returns {job_id, task_id, status: 'processing'}

  GET /customer/api/classify-item/status/<job_id>/
    - Returns current ClassificationResult status
    - Frontend polls this every 2 seconds

Both require login. Customer can only classify their own jobs.
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .utils import validate_image_file, ImageValidationError

logger = logging.getLogger(__name__)

# Maximum file size enforced at Django level (also checked in utils)
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB


@login_required
@require_http_methods(['POST'])
def classify_item(request):
    """
    POST /customer/api/classify-item/

    Accepts:
      - job_id (form field): UUID of the job being created
      - photo  (file):       The item photo (max 20MB)

    Returns JSON:
      {
        "status":  "processing",
        "job_id":  "uuid...",
        "task_id": "celery-task-id",
        "message": "Classification started"
      }
    """
    from Truck.models import Job, ClassificationResult
    from .tasks import classify_item_task

    # ── Validate job_id ────────────────────────────────────────────────────
    job_id = request.POST.get('job_id', '').strip()
    if not job_id:
        return JsonResponse({'error': 'job_id is required'}, status=400)

    try:
        job = Job.objects.get(pk=job_id, Customer=request.user.customer)
    except Job.DoesNotExist:
        return JsonResponse({'error': 'Job not found'}, status=404)
    except Exception:
        return JsonResponse({'error': 'Invalid job_id'}, status=400)

    # ── Validate uploaded photo ────────────────────────────────────────────
    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'error': 'No photo uploaded'}, status=400)

    if photo.size > MAX_UPLOAD_SIZE_BYTES:
        size_mb = photo.size / (1024 * 1024)
        return JsonResponse({
            'error': f'Image too large ({size_mb:.1f} MB). Maximum is 20 MB.'
        }, status=413)

    try:
        validate_image_file(photo)
        photo.seek(0)
    except ImageValidationError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    # ── Save photo to job ──────────────────────────────────────────────────
    job.photo = photo
    job.classification_status = 'pending'
    job.save(update_fields=['photo', 'classification_status'])

    # ── Create/reset ClassificationResult ────────────────────────────────
    result_obj, _ = ClassificationResult.objects.update_or_create(
        job=job,
        defaults={
            'status':              'pending',
            'category_suggestion': '',
            'item_name_suggestion':'',
            'prohibited_detected': False,
            'error_message':       '',
        }
    )

    # ── Queue Celery task ──────────────────────────────────────────────────
    task = classify_item_task.delay(str(job.id))

    logger.info(
        "classify_item queued | job=%s | task=%s | file=%s | size=%.1fKB",
        job.id, task.id, photo.name, photo.size / 1024
    )

    return JsonResponse({
        'status':  'processing',
        'job_id':  str(job.id),
        'task_id': task.id,
        'message': 'Classification started. Analysing your item…',
    })


@login_required
@require_http_methods(['GET'])
def classify_item_status(request, job_id):
    """
    GET /customer/api/classify-item/status/<job_id>/

    Polls the classification result for a job.
    Frontend calls this every 2 seconds after POST.

    Returns JSON:
      While processing:
        { "status": "processing", "progress": "Analysing image..." }

      On success:
        {
          "status":             "complete",
          "category_slug":      "electronics",
          "category_name":      "Electronics",
          "confidence":         0.87,
          "low_confidence":     false,
          "item_name":          "Laptop Computer",
          "size_suggestion":    "small",
          "size_options":       ["small", "medium"],
          "is_fragile":         true,
          "fragility_score":    0.82,
          "prohibited_detected": false,
          "prohibited_items":   [],
          "prohibited_reason":  "",
          "processing_time_s":  3.2
        }

      On low confidence:
        { "status": "complete", "low_confidence": true, ... }
        (frontend shows "Unable to classify — fill manually")

      On prohibited:
        { "status": "flagged", "prohibited_detected": true, "prohibited_reason": "..." }

      On failure:
        { "status": "failed", "error": "..." }
    """
    from Truck.models import Job, ClassificationResult
    from .categories import CATEGORY_DEFINITIONS

    try:
        job = Job.objects.get(pk=job_id, Customer=request.user.customer)
    except Job.DoesNotExist:
        return JsonResponse({'error': 'Job not found'}, status=404)
    except Exception:
        return JsonResponse({'error': 'Invalid job_id'}, status=400)

    try:
        result = ClassificationResult.objects.get(job=job)
    except ClassificationResult.DoesNotExist:
        return JsonResponse({'status': 'pending', 'progress': 'Waiting to start…'})

    if result.status in ('pending', 'processing'):
        return JsonResponse({
            'status':   result.status,
            'progress': 'Analysing your item with AI… this takes a few seconds.',
        })

    if result.status == 'failed':
        return JsonResponse({
            'status': 'failed',
            'error':  result.error_message or 'Classification failed. Please fill in details manually.',
        })

    # Build size options labels for the frontend
    cat_def      = CATEGORY_DEFINITIONS.get(result.category_suggestion, {})
    size_options = cat_def.get('size_options', ['small', 'medium', 'large'])
    cat_desc     = cat_def.get('description', '')

    return JsonResponse({
        'status':              result.status,         # 'complete' or 'flagged'

        # CLIP results
        'category_slug':       result.category_suggestion,
        'category_name':       CATEGORY_DEFINITIONS.get(
                                   result.category_suggestion, {}
                               ).get('name', 'General Cargo'),
        'category_description': cat_desc,
        'confidence':          result.category_confidence,
        'low_confidence':      result.low_confidence,
        'item_name':           result.item_name_suggestion,

        # Size
        'size_suggestion':     result.size_suggestion,
        'size_reliable':       result.size_reliable,
        'size_options':        size_options,

        # Fragility
        'is_fragile':          result.is_fragile,
        'fragility_score':     result.fragility_score,

        # Prohibited
        'prohibited_detected': result.prohibited_detected,
        'prohibited_items':    result.prohibited_items or [],
        'prohibited_reason':   result.prohibited_reason or '',

        # Meta
        'processing_time_s':   result.processing_time_s,
    })