"""
Truck/tasks.py — Celery tasks for RVC platform.
Tasks: evaluate_geofences_task + generate_zones_task
"""
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