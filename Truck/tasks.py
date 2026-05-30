"""
Truck/tasks.py — Celery tasks for RVC platform.
Tasks: evaluate_geofences_task + generate_zones_task
"""
import time
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True, max_retries=3, default_retry_delay=5,
    name='Truck.tasks.evaluate_geofences_task',
)
def evaluate_geofences_task(self, courier_id: int, lat: float, lng: float):
    """Async geofencing evaluation — called after every GPS update."""
    try:
        from Truck.models import Courier
        from Truck.geofencing import evaluate_courier_position
        courier = Courier.objects.get(pk=courier_id)
        evaluate_courier_position(courier, lat, lng)
    except Exception as exc:
        logger.exception("evaluate_geofences_task failed courier=%s: %s", courier_id, exc)
        raise self.retry(exc=exc)


@shared_task(
    bind=True, max_retries=1, default_retry_delay=300,
    name='Truck.tasks.generate_zones_task',
    time_limit=600, soft_time_limit=540,
)
def generate_zones_task(self, demo_mode: bool = False, clear_existing: bool = True):
    """
    DBSCAN delivery zone generation.
    Runs daily at 2AM via Celery Beat.
    Manual trigger: generate_zones_task.delay(demo_mode=True)
    Management cmd: python manage.py generate_zones --demo
    """
    logger.info("generate_zones_task started | demo_mode=%s", demo_mode)
    try:
        from Truck.zone_generator import generate_zones
        zones = generate_zones(demo_mode=demo_mode, clear_existing=clear_existing)
        result = {'zones_created': len(zones), 'zone_names': [z.name for z in zones]}
        logger.info("generate_zones_task complete: %s", result)
        return result
    except Exception as exc:
        logger.exception("generate_zones_task failed: %s", exc)
        raise self.retry(exc=exc)
    

# ═══════════════════════════════════════════════════════════════════════════════
#   P5 — NEAREST COURIER AUTO-ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=0, name='Truck.tasks.auto_assign_job')
def auto_assign_job(self, job_id, attempted_courier_ids=None, dispatch_start_ts=None):
    """
    Finds the nearest available courier and sends them an FCM push notification.
    Schedules dispatch_fallback to run in 90 seconds if the job is not accepted.

    Called when:
      - A job transitions to status='processing' (payment confirmed)
      - dispatch_fallback re-queues this after a 90s timeout

    Pilot study data: logs every attempt with distance and timestamp.
    """
    from Truck.models import Job
    from Truck.auto_assignment import (
        get_nearest_couriers, send_job_fcm_push, log_dispatch_event,
        ACCEPT_TIMEOUT_SECONDS, MAX_DISPATCH_ATTEMPTS,
    )

    attempted_courier_ids = attempted_courier_ids or []
    dispatch_start_ts     = dispatch_start_ts     or time.time()
    attempt_number        = len(attempted_courier_ids) + 1

    logger.info(
        "auto_assign_job START | job=%s | attempt=%d | already_tried=%s",
        job_id, attempt_number, attempted_courier_ids
    )

    # ── Guard: stop if exceeded max attempts ─────────────────────────────────
    if attempt_number > MAX_DISPATCH_ATTEMPTS:
        elapsed = round(time.time() - dispatch_start_ts, 1)
        logger.error(
            "DISPATCH EXHAUSTED | job=%s | tried %d couriers over %.1fs",
            job_id, len(attempted_courier_ids), elapsed
        )
        log_dispatch_event(
            job_id, None, 'exhausted',
            attempt_number=attempt_number,
            elapsed_seconds=elapsed,
            notes=f"Tried {len(attempted_courier_ids)} couriers, none accepted",
        )
        return {'done': True, 'reason': 'max_attempts_exceeded'}

    # ── Fetch job ─────────────────────────────────────────────────────────────
    try:
        job = Job.objects.select_related('Customer__user').get(pk=job_id)
    except Job.DoesNotExist:
        logger.error("auto_assign_job: job %s not found", job_id)
        return {'done': True, 'reason': 'job_not_found'}

    if job.status != Job.PROCESSING_STATUS:
        elapsed = round(time.time() - dispatch_start_ts, 1)
        logger.info(
            "auto_assign_job: job %s already in status=%s — "
            "accepted in %.1fs at attempt %d",
            job_id, job.status, elapsed, attempt_number
        )
        log_dispatch_event(
            job_id, None, 'already_accepted',
            attempt_number=attempt_number,
            elapsed_seconds=elapsed,
        )
        return {'done': True, 'reason': 'already_accepted', 'elapsed_s': elapsed}

    # ── PostGIS nearest courier query ─────────────────────────────────────────
    couriers = get_nearest_couriers(job, exclude_ids=attempted_courier_ids, limit=5)

    if not couriers:
        elapsed = round(time.time() - dispatch_start_ts, 1)
        logger.warning(
            "auto_assign_job: no available couriers for job %s (tried %s)",
            job_id, attempted_courier_ids
        )
        log_dispatch_event(
            job_id, None, 'no_couriers',
            attempt_number=attempt_number,
            elapsed_seconds=elapsed,
        )
        return {'done': False, 'reason': 'no_available_couriers'}

    nearest     = couriers[0]
    distance_km = nearest.distance.km if nearest.distance else 0

    logger.info(
        "auto_assign_job: NOTIFYING courier=%s (%.2f km) for job=%s | attempt %d",
        nearest.user.get_full_name(), distance_km, job_id, attempt_number
    )

    # ── Log dispatch attempt ──────────────────────────────────────────────────
    log_dispatch_event(
        job_id, nearest.pk, 'notified',
        attempt_number=attempt_number,
        distance_km=distance_km,
        notes=f"Courier: {nearest.user.get_full_name()}",
    )

    # ── Send FCM push notification ────────────────────────────────────────────
    push_sent = send_job_fcm_push(nearest, job)

    if not push_sent:
        logger.warning(
            "FCM push failed for courier %d — skipping to next", nearest.pk
        )
        # Skip this courier (no FCM) and immediately try next
        new_attempted = attempted_courier_ids + [nearest.pk]
        auto_assign_job.delay(job_id, new_attempted, dispatch_start_ts)
        return {'done': False, 'reason': 'fcm_failed', 'skipped': nearest.pk}

    # ── Schedule 90-second fallback ───────────────────────────────────────────
    new_attempted = attempted_courier_ids + [nearest.pk]
    dispatch_fallback.apply_async(
        args=[job_id, new_attempted, dispatch_start_ts, attempt_number],
        countdown=ACCEPT_TIMEOUT_SECONDS,
    )

    return {
        'courier_notified': nearest.pk,
        'courier_name':     nearest.user.get_full_name(),
        'distance_km':      round(distance_km, 2),
        'fallback_in_s':    ACCEPT_TIMEOUT_SECONDS,
        'attempt':          attempt_number,
    }


@shared_task(bind=True, max_retries=0, name='Truck.tasks.dispatch_fallback')
def dispatch_fallback(self, job_id, attempted_courier_ids, dispatch_start_ts, attempt_number):
    """
    Runs 90 seconds after auto_assign_job sends an FCM push.

    If the job was accepted: logs the dispatch time (PILOT STUDY DATA).
    If still unaccepted: triggers auto_assign_job for the next nearest courier.

    This is the key metric for validating < 60s automated dispatch claim.
    """
    from Truck.models import Job
    from Truck.auto_assignment import log_dispatch_event

    elapsed = round(time.time() - dispatch_start_ts, 1)

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return {'done': True, 'reason': 'job_not_found'}

    if job.status != Job.PROCESSING_STATUS:
        # ── JOB ACCEPTED — record pilot study data ────────────────────────────
        logger.info(
            "═══════════════════════════════════════════════════\n"
            "DISPATCH SUCCESS ✓\n"
            "  job_id:          %s\n"
            "  total_time:      %.1f seconds\n"
            "  attempts:        %d\n"
            "  accepted_status: %s\n"
            "  couriers_tried:  %s\n"
            "═══════════════════════════════════════════════════",
            job_id, elapsed, attempt_number, job.status, attempted_courier_ids
        )
        log_dispatch_event(
            job_id,
            job.courier.pk if job.courier else None,
            'accepted',
            attempt_number=attempt_number,
            elapsed_seconds=elapsed,
            notes=(
                f"Accepted in {elapsed}s at attempt {attempt_number}. "
                f"Couriers tried: {attempted_courier_ids}"
            ),
        )
        return {
            'accepted':              True,
            'dispatch_time_seconds': elapsed,
            'attempt_number':        attempt_number,
            'pilot_study_note':      f"Dispatch time: {elapsed}s (target: <60s)",
        }

    # ── NOT ACCEPTED — try next nearest courier ───────────────────────────────
    logger.warning(
        "DISPATCH TIMEOUT | job=%s | attempt=%d | elapsed=%.1fs | trying next courier",
        job_id, attempt_number, elapsed
    )
    log_dispatch_event(
        job_id, None, 'timeout',
        attempt_number=attempt_number,
        elapsed_seconds=elapsed,
        notes=f"No response after {ACCEPT_TIMEOUT_SECONDS}s — escalating to next courier",
    )

    # Try next nearest (auto_assign_job excludes already_tried couriers)
    auto_assign_job.delay(job_id, attempted_courier_ids, dispatch_start_ts)

    return {
        'accepted':   False,
        'timed_out':  True,
        'elapsed_s':  elapsed,
        'retrying':   True,
    }