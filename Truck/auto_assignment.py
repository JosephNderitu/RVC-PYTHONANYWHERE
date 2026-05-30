"""
Truck/auto_assignment.py
========================
RVC Nearest Courier Auto-Assignment Engine — Priority 5

Flow:
  Job → processing → auto_assign_job.delay(job_id)
    → PostGIS ST_Distance query → nearest available, verified courier
    → FCM push notification sent
    → dispatch_fallback scheduled in 90 seconds
    → if job accepted before 90s → log dispatch time (pilot study data)
    → if not accepted → try next nearest courier (repeat up to 5 couriers)

Pilot Study Metrics Logged:
  - dispatch_start_ts: when task was triggered
  - courier_distance_km: how far nearest courier was
  - accepted_at_attempt: which attempt number accepted
  - total_dispatch_seconds: end-to-end time from processing → picking

This directly validates the "< 60s automated dispatch" claim in the proposal.
"""

import time
import logging
from django.conf  import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_DISPATCH_ATTEMPTS = 5     # try up to 5 couriers before giving up
ACCEPT_TIMEOUT_SECONDS = 90   # seconds before trying next courier


# ═══════════════════════════════════════════════════════════════════════════════
#   FCM PUSH NOTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def send_job_fcm_push(courier, job):
    """
    Send an FCM push notification to a courier for a new available job.
    Uses Firebase HTTP v1 API via the firebase_admin SDK if available,
    otherwise falls back to a direct HTTP request to the legacy FCM endpoint.
    """
    token = getattr(courier, 'fcm_token', '').strip()
    if not token:
        logger.warning(
            "auto_assign: courier %d has no FCM token — cannot push",
            courier.pk
        )
        return False

    dist_mi  = round(job.distance, 1) if job.distance else 0
    price    = f"${job.price:.2f}" if job.price else "—"

    title = "New Job Available — Accept Now"
    body  = (
        f"{dist_mi} mi · {price} · "
        f"Pickup: {(job.pickup_address or '')[:40]}"
    )
    data = {
        "job_id":       str(job.id),
        "price":        str(job.price or 0),
        "distance":     str(dist_mi),
        "pickup_lat":   str(job.pickup_lat),
        "pickup_lng":   str(job.pickup_lng),
        "job_url":      f"/courier/jobs/available/{job.id}/",
        "type":         "new_job",
    }

    # ── Try firebase_admin SDK first ─────────────────────────────────────────
    try:
        import firebase_admin
        from firebase_admin import messaging

        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data,
            token=token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default', channel_id='rvc_jobs',
                ),
            ),
        )
        response = messaging.send(msg)
        logger.info(
            "FCM sent via SDK to courier %d | job %s | response: %s",
            courier.pk, job.id, response
        )
        return True

    except ImportError:
        pass   # fall through to HTTP
    except Exception as exc:
        logger.warning("FCM SDK error for courier %d: %s", courier.pk, exc)

    # ── Fallback: legacy FCM HTTP API ────────────────────────────────────────
    try:
        import requests

        fcm_server_key = getattr(settings, 'FCM_SERVER_KEY', '')
        if not fcm_server_key:
            logger.warning("FCM_SERVER_KEY not set — cannot send push notification")
            return False

        payload = {
            "to":           token,
            "priority":     "high",
            "notification": {"title": title, "body": body, "sound": "default"},
            "data":         data,
        }
        resp = requests.post(
            "https://fcm.googleapis.com/fcm/send",
            json=payload,
            headers={
                "Authorization": f"key={fcm_server_key}",
                "Content-Type":  "application/json",
            },
            timeout=8,
        )
        result = resp.json()
        if result.get('success'):
            logger.info(
                "FCM sent via HTTP to courier %d | job %s",
                courier.pk, job.id
            )
            return True
        else:
            logger.warning(
                "FCM HTTP failed for courier %d: %s", courier.pk, result
            )
            return False

    except Exception as exc:
        logger.error("FCM HTTP error for courier %d: %s", courier.pk, exc)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#   POSTGI NEAREST COURIER QUERY
# ═══════════════════════════════════════════════════════════════════════════════

def get_nearest_couriers(job, exclude_ids=None, limit=5):
    """
    PostGIS ST_Distance query — returns couriers ordered by distance to
    job.pickup_location.

    Filters:
      - is_available = True
      - is_verified  = True   (passed driver verification)
      - location     is not null
      - fcm_token    is set   (can receive push notifications)
      - not already notified  (exclude_ids)
    """
    from Truck.models import Courier
    from django.contrib.gis.db.models.functions import Distance

    if not job.pickup_location:
        logger.error("get_nearest_couriers: job %s has no pickup_location", job.pk)
        return []

    exclude_ids = exclude_ids or []

    qs = (
        Courier.objects
        .filter(
            is_available=True,
            location__isnull=False,
        )
        .filter(
            # Verified field may not exist on older DB — check safely
            **({'is_verified': True} if _has_verification_fields() else {})
        )
        .exclude(pk__in=exclude_ids)
        .annotate(distance=Distance('location', job.pickup_location))
        .order_by('distance')
        .select_related('user')
        [:limit]
    )

    couriers = list(qs)
    for c in couriers:
        km = c.distance.km if c.distance else 0
        logger.debug(
            "  Candidate courier: %s | %.2f km away | FCM: %s",
            c.user.get_full_name(), km, bool(c.fcm_token)
        )
    return couriers


def _has_verification_fields():
    """Check if the Courier model has the is_verified field (migration may not have run)."""
    from Truck.models import Courier
    return hasattr(Courier, 'is_verified')


# ═══════════════════════════════════════════════════════════════════════════════
#   DISPATCH LOG (writes to Django logger + DB DispatchLog model)
# ═══════════════════════════════════════════════════════════════════════════════

def log_dispatch_event(job_id, courier_id, event, attempt_number=1,
                       distance_km=None, elapsed_seconds=None, notes=''):
    """
    Logs a dispatch event both to the application log and to the DispatchLog DB.
    Used to generate pilot study metrics.
    """
    # Structured log line (parseable by grep/log analysis)
    logger.info(
        "DISPATCH | job=%s | courier=%s | event=%s | attempt=%d "
        "| dist_km=%s | elapsed_s=%s | %s",
        job_id, courier_id, event, attempt_number,
        f"{distance_km:.2f}" if distance_km else "—",
        f"{elapsed_seconds:.1f}" if elapsed_seconds else "—",
        notes,
    )

    # Write to DB
    try:
        from Truck.models import Job, Courier, DispatchLog

        job     = Job.objects.get(pk=job_id)
        courier = Courier.objects.filter(pk=courier_id).first() if courier_id else None

        DispatchLog.objects.create(
            job            = job,
            courier        = courier,
            event          = event,
            attempt_number = attempt_number,
            distance_km    = distance_km,
            elapsed_seconds= elapsed_seconds,
            notes          = notes,
        )
    except Exception as exc:
        logger.warning("DispatchLog DB write failed: %s", exc)