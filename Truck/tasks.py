"""
Truck/tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Celery tasks for the RVC platform.

WHY CELERY FOR GEOFENCING
──────────────────────────
The GPS update API endpoint must return in <50ms — the courier's
mobile app is POSTing every 5 seconds while driving, and a slow
response would cause the app to time out and miss updates.

The full geofencing pipeline (smoothing + PostGIS query + Winding
Number PiP × N zones + state machine) takes ~2–40ms depending on
zone count. By dispatching it to Celery via .delay(), the API
returns immediately and the evaluation runs in the background.

The pipeline is idempotent — if a task fails it can be retried
without producing duplicate events (the state machine handles
duplicate readings gracefully).

CELERY CONFIGURATION (confirm in settings.py):
    CELERY_BROKER_URL  = env('REDIS_URL')   # redis://redis:6379/0
    CELERY_RESULT_BACKEND = env('REDIS_URL')
    CELERY_TASK_SERIALIZER = 'json'
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,   # seconds before retry on failure
    name='Truck.tasks.evaluate_geofences_task',
)
def evaluate_geofences_task(self, courier_id: int, lat: float, lng: float):
    """
    Asynchronous geofencing evaluation for one GPS update.

    Called from courier_location_update_api immediately after
    courier.set_location() saves the new position to PostGIS.

    Args:
        courier_id: Courier.pk — used to re-fetch the object in the worker
        lat:        Raw GPS latitude (before smoothing)
        lng:        Raw GPS longitude (before smoothing)

    The courier object is re-fetched by pk in the worker rather than
    passing the full object, because Django model instances are not
    JSON-serialisable and Celery uses JSON serialisation by default.
    """
    try:
        from Truck.models import Courier
        from Truck.geofencing import evaluate_courier_position

        courier = Courier.objects.get(pk=courier_id)
        evaluate_courier_position(courier, lat, lng)

    except Exception as exc:
        logger.exception(
            "evaluate_geofences_task failed for courier_id=%s lat=%.6f lng=%.6f — %s",
            courier_id, lat, lng, exc,
        )
        # Retry up to max_retries times before giving up
        raise self.retry(exc=exc)