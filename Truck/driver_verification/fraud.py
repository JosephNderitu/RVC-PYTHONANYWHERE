"""
Lightweight fraud checks on parsed license data.
These run synchronously before or after OCR — no ML required.
"""
import re
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

# Known fraud patterns: license numbers that appear too frequently across couriers
# (populated at runtime from DB; refreshed per task run)
SUSPICIOUS_NUMBER_PATTERN = re.compile(r'^(.)\1{5,}$')  # e.g. AAAAAAA, 0000000


def check_license_not_expired(expiry: Optional[date]) -> tuple[bool, str]:
    if expiry is None:
        return False, "Could not extract expiry date from license."
    if expiry < date.today():
        return False, f"License expired on {expiry}."
    return True, ""


def check_license_number_not_suspicious(license_number: Optional[str]) -> tuple[bool, str]:
    if not license_number:
        return False, "License number could not be detected."
    if SUSPICIOUS_NUMBER_PATTERN.match(license_number):
        return False, f"License number '{license_number}' matches suspicious repetition pattern."
    return True, ""


def check_license_number_unique(license_number: Optional[str], current_courier_id: int) -> tuple[bool, str]:
    """Ensure no other verified courier holds the same license number."""
    if not license_number:
        return True, ""  # Can't check uniqueness without a number; OCR failure handled elsewhere

    from Truck.models import Courier  # local import to avoid circular dependency

    duplicate = (
        Courier.objects
        .filter(license_number=license_number, is_verified=True)
        .exclude(pk=current_courier_id)
        .exists()
    )
    if duplicate:
        return False, f"License number '{license_number}' is already registered to another courier."
    return True, ""


def run_fraud_checks(
    license_number: Optional[str],
    expiry: Optional[date],
    courier_id: int,
) -> tuple[bool, list[str]]:
    """
    Run all fraud checks.
    Returns (passed: bool, reasons: list[str]) where reasons lists any failures.
    """
    failures: list[str] = []

    for check_fn, args in [
        (check_license_not_expired,       (expiry,)),
        (check_license_number_not_suspicious, (license_number,)),
        (check_license_number_unique,     (license_number, courier_id)),
    ]:
        ok, reason = check_fn(*args)
        if not ok:
            failures.append(reason)
            logger.warning("Fraud check failed for courier %d: %s", courier_id, reason)

    return len(failures) == 0, failures