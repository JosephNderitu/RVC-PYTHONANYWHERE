"""
REST API endpoint for couriers to submit license + selfie photos.
Triggers async verification task on upload.
Follows the DRF style already used in Truck/courier/apis.py.
"""
import logging

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .tasks import verify_driver_license

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def submit_verification_documents(request):
    """
    POST /courier/api/verification/submit/
    Fields: license_photo (file), selfie_photo (file)
    """
    courier = getattr(request.user, "courier", None)
    if courier is None:
        return Response({"error": "Courier profile not found."}, status=404)

    if courier.verification_status == "verified":
        return Response({"error": "Courier is already verified."}, status=400)

    if courier.verification_attempts >= 5:
        return Response(
            {"error": "You have exceeded the maximum of 5 verification attempts. Please contact support."},
            status=429
        )

    license_photo = request.FILES.get("license_photo")
    selfie_photo  = request.FILES.get("selfie_photo")

    if not license_photo:
        return Response({"error": "license_photo is required."}, status=400)

    if license_photo:
        courier.license_photo = license_photo
    if selfie_photo:
        courier.selfie_photo = selfie_photo

    courier.verification_status = "pending"
    courier.save(update_fields=["license_photo", "selfie_photo", "verification_status"])

    # Fire async — same pattern as evaluate_geofences_task.delay()
    verify_driver_license.delay(courier.pk)

    logger.info("Verification documents submitted | courier=%d", courier.pk)
    return Response({"success": True, "message": "Documents received. Verification in progress."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verification_status(request):
    """
    GET /courier/api/verification/status/
    Returns current verification state for the authenticated courier.
    """
    courier = getattr(request.user, "courier", None)
    if courier is None:
        return Response({"error": "Courier profile not found."}, status=404)

    return Response({
        "verification_status":   courier.verification_status,
        "is_verified":           courier.is_verified,
        "face_verified":         courier.face_verified,
        "verification_score":    courier.verification_score,
        "license_class":         courier.license_class,
        "license_expiry":        str(courier.license_expiry) if courier.license_expiry else None,
        "verification_attempts": courier.verification_attempts,
        "verified_at":           courier.verified_at,
    })