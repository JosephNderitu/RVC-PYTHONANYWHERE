# Truck/courier/apis.py — complete replacement

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from Truck.models import Job, Courier


def _json_auth_check(request):
    """Returns a JsonResponse error if not authenticated, else None."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "Not authenticated"},
            status=401
        )
    return None


@csrf_exempt
def available_jobs_api(request):
    auth_error = _json_auth_check(request)
    if auth_error:
        return auth_error

    jobs_qs = Job.objects.filter(
        status=Job.PROCESSING_STATUS
    ).select_related('Customer__user', 'category')

    jobs = []
    for job in jobs_qs:
        jobs.append({
            "id":               str(job.id),
            "names":            job.names,
            "description":      job.description,
            "size":             job.get_size_display(),
            "quantity":         job.quantity,
            "photo":            job.photo.url if job.photo else "",
            "status":           job.status,
            "distance":         job.distance,
            "duration":         job.duration,
            "price":            job.price,
            "pickup_address":   job.pickup_address,
            "pickup_lat":       job.pickup_lat,
            "pickup_lng":       job.pickup_lng,
            "pickup_name":      job.pickup_name,
            "pickup_phone":     job.pickup_phone,
            "delivery_address": job.delivery_address,
            "delivery_lat":     job.delivery_lat,
            "delivery_lng":     job.delivery_lng,
            "delivery_name":    job.delivery_name,
            "delivery_phone":   job.delivery_phone,
            "customer_name":    job.Customer.user.get_full_name(),
            "customer_email":   job.Customer.user.email,
            "customer_phone":   job.Customer.phone_number,
            "customer_avatar":  job.Customer.avatar.url if job.Customer.avatar else "",
            "created_at":       job.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return JsonResponse({"success": True, "jobs": jobs})


@csrf_exempt
def current_job_update_api(request, id):
    auth_error = _json_auth_check(request)
    if auth_error:
        return auth_error

    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    # Make sure this user has a courier profile
    try:
        courier = request.user.courier
    except Exception:
        return JsonResponse({"success": False, "error": "No courier profile found"}, status=403)

    job = Job.objects.filter(
        id=id,
        courier=courier,
        status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS],
    ).last()

    if job is None:
        return JsonResponse({
            "success": False,
            "error": f"Job not found. Job id={id}, courier={courier}, "
                     f"looking for status picking or delivering."
        }, status=404)

    if job.status == Job.PICKING_STATUS:
        photo = request.FILES.get('pickup_photo')
        if not photo:
            return JsonResponse({"success": False, "error": "No pickup_photo in request"}, status=400)
        job.pickup_photo = photo
        job.pickedup_at  = timezone.now()
        job.status       = Job.DELIVERING_STATUS
        job.save()

    elif job.status == Job.DELIVERING_STATUS:
        photo = request.FILES.get('delivery_photo')
        if not photo:
            return JsonResponse({"success": False, "error": "No delivery_photo in request"}, status=400)
        job.delivery_photo = photo
        job.delivered_at   = timezone.now()
        job.status         = Job.COMPLETED_STATUS
        job.save()

    return JsonResponse({"success": True, "new_status": job.status})


@csrf_exempt
def fcm_token_update_api(request):
    auth_error = _json_auth_check(request)
    if auth_error:
        return auth_error

    try:
        request.user.courier.fcm_token = request.GET.get('fcm_token', '')
        request.user.courier.save()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)