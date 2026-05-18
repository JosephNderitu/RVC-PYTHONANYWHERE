"""
Celery tasks for driver verification.
Mirrors the pattern in Truck/tasks.py exactly.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def verify_driver_license(self, courier_id: int) -> dict:
    """
    Runs the full OCR + fraud + face verification pipeline for a courier.
    Retries up to 3 times on unexpected exceptions (network/model load issues).
    """
    try:
        from Truck.driver_verification import run_full_verification
        result = run_full_verification(courier_id)
        logger.info("verify_driver_license completed | courier=%d | result=%s", courier_id, result)
        return result
    except Exception as exc:
        logger.error("verify_driver_license error | courier=%d | %s", courier_id, exc, exc_info=True)
        raise self.retry(exc=exc)