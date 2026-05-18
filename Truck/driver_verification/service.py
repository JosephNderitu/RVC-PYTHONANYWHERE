"""
Orchestrates the full driver verification pipeline.
Called by Celery tasks — not directly from views.
"""
import logging
from datetime import timezone as tz, datetime

from django.conf import settings
from django.db import transaction as db_transaction

logger = logging.getLogger(__name__)

# ── Dev/Testing flag ────────────────────────────────────────────────────────
# Set SKIP_FACE_VERIFICATION = True in settings_dev.py to bypass face checks.
# NEVER set True in production settings.
SKIP_FACE = getattr(settings, "SKIP_FACE_VERIFICATION", False)


def run_full_verification(courier_id: int) -> dict:
    """
    Full pipeline:
      1. Document classification (lightweight heuristics + OCR keyword scan)
      2. OCR  → extract & parse license data
      3. Fraud checks (expiry, suspicious number, uniqueness)
      4. Face verification (selfie vs. license photo) — skipped if SKIP_FACE=True
      5. Persist result to Courier model

    Returns a result dict for logging / Celery chaining.
    """
    from Truck.models import Courier          # deferred — avoid circular import
    from .ocr               import extract_license_text, parse_license_data
    from .document_classifier import classify_document
    from .fraud             import run_fraud_checks
    from .face              import verify_faces

    # ── Fetch courier ────────────────────────────────────────────────────────
    try:
        courier = Courier.objects.get(pk=courier_id)
    except Courier.DoesNotExist:
        logger.error("Verification attempted for non-existent courier id=%d", courier_id)
        return {"success": False, "reason": "courier_not_found"}

    courier.verification_attempts += 1
    courier.save(update_fields=["verification_attempts"])

    # ── 0. Document classification ───────────────────────────────────────────
    if not courier.license_photo:
        return _fail(courier, "no_license_photo", "No license photo uploaded.")

    is_license, doc_conf, doc_reason = classify_document(courier.license_photo.path)
    if not is_license:
        return _fail(
            courier,
            "not_a_license",
            f"Uploaded file does not appear to be a valid driver's license. {doc_reason}",
        )

    logger.info(
        "Document classified as license | courier=%d | confidence=%.4f",
        courier_id, doc_conf,
    )

    # ── 1. OCR ───────────────────────────────────────────────────────────────
    lines  = extract_license_text(courier.license_photo.path)
    parsed = parse_license_data(lines)

    logger.info(
        "OCR parsed | courier=%d | license_no=%s | expiry=%s | class=%s",
        courier_id,
        parsed.get("license_number"),
        parsed.get("expiry_date"),
        parsed.get("license_class"),
    )

    # ── 2. Fraud checks ──────────────────────────────────────────────────────
    fraud_passed, fraud_reasons = run_fraud_checks(
        license_number=parsed["license_number"],
        expiry=parsed["expiry_date"],
        courier_id=courier_id,
    )
    if not fraud_passed:
        return _fail(courier, "fraud_check_failed", "; ".join(fraud_reasons))

    # ── 3. Face verification ─────────────────────────────────────────────────
    face_result   = None
    face_verified = False
    face_score    = 0.0
    face_error    = ""

    if SKIP_FACE:
        # ── Dev bypass: skip face entirely, rely on OCR + fraud ──────────────
        logger.warning(
            "⚠️  Face verification DISABLED (SKIP_FACE_VERIFICATION=True) "
            "— courier=%d | OCR-only mode active",
            courier_id,
        )
        face_verified = False          # not verified, but not required either
        face_error    = "Face verification skipped (dev/testing mode)."

    elif courier.selfie_photo:
        # ── Normal path: run InsightFace ─────────────────────────────────────
        face_result   = verify_faces(
            license_image_path=courier.license_photo.path,
            selfie_image_path=courier.selfie_photo.path,
        )
        face_verified = face_result.verified   if face_result else False
        face_score    = face_result.confidence if face_result else 0.0
        face_error    = face_result.error      if face_result else ""

    else:
        # ── No selfie uploaded ───────────────────────────────────────────────
        logger.warning(
            "Courier %d has no selfie; proceeding with OCR-based verification only.",
            courier_id,
        )
        face_error = "Selfie not provided; verification based on license OCR only."

    # ── 4. Aggregate score ───────────────────────────────────────────────────
    ocr_score = 1.0 if (parsed["license_number"] and parsed["expiry_date"]) else 0.5

    if SKIP_FACE or face_result is None:
        # OCR carries full weight when face is skipped or unavailable
        total_score = round(ocr_score * 1.0, 4)
    else:
        total_score = round((ocr_score * 0.4) + (face_score * 0.6), 4)

    # ── 5. Final status decision ─────────────────────────────────────────────
    #
    #  Verified when ALL of:
    #    • fraud checks passed
    #    • license number extracted
    #    • score >= 0.5
    #    • face verified  OR  face was skipped/not provided
    #
    face_ok = face_verified or SKIP_FACE or not courier.selfie_photo

    final_status = (
        "verified"
        if (fraud_passed and parsed["license_number"] and total_score >= 0.5 and face_ok)
        else "failed"
    )

    # ── 6. Persist ───────────────────────────────────────────────────────────
    with db_transaction.atomic():
        courier.license_number      = parsed["license_number"]
        courier.license_class       = parsed["license_class"]
        courier.license_expiry      = parsed["expiry_date"]
        courier.face_verified       = face_verified
        courier.verification_score  = total_score
        courier.verification_status = final_status
        courier.is_verified         = (final_status == "verified")
        courier.verified_at         = datetime.now(tz.utc) if courier.is_verified else None
        courier.verification_notes  = face_error or ""
        courier.save(update_fields=[
            "license_number", "license_class", "license_expiry",
            "face_verified", "verification_score", "verification_status",
            "is_verified", "verified_at", "verification_notes",
        ])

    logger.info(
        "Verification complete | courier=%d | status=%s | score=%.4f | "
        "face=%s | face_skipped=%s",
        courier_id, final_status, total_score, face_verified, SKIP_FACE,
    )

    return {
        "success":      courier.is_verified,
        "status":       final_status,
        "score":        total_score,
        "face":         face_verified,
        "face_skipped": SKIP_FACE,
        "license_no":   parsed["license_number"],
        "class":        parsed["license_class"],
        "expiry":       str(parsed["expiry_date"]),
    }


def _fail(courier, code: str, reason: str) -> dict:
    courier.verification_status = "failed"
    courier.is_verified         = False
    courier.verification_notes  = reason
    courier.save(update_fields=["verification_status", "is_verified", "verification_notes"])
    logger.warning(
        "Verification failed | courier=%d | code=%s | reason=%s",
        courier.pk, code, reason,
    )
    return {"success": False, "code": code, "reason": reason}