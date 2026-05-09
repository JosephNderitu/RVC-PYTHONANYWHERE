# Truck/courier/apis.py
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.gis.geos import Point
from Truck.models import Job, Courier, CourierLocationHistory


def _json_auth_check(request):
    """Returns a JsonResponse 401 if not authenticated, else None."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"success": False, "error": "Not authenticated"},
            status=401,
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
            "error": f"Job not found. id={id}, courier={courier}",
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


# ── GPS position update ────────────────────────────────────────────────────────
@csrf_exempt
def courier_location_update_api(request):
    """
    POST {"lat": ..., "lng": ...}

    1. Validates auth and active job
    2. Calls courier.set_location() — writes to PostGIS PointField
    3. Logs to CourierLocationHistory
    4. Dispatches evaluate_geofences_task via Celery (async, non-blocking)
       → The geofencing pipeline runs in the background worker
       → This endpoint always returns in <50ms
    """
    auth_error = _json_auth_check(request)
    if auth_error:
        return auth_error

    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "POST required"}, status=405)

    try:
        courier = request.user.courier
    except Exception:
        return JsonResponse({"success": False, "error": "No courier profile"}, status=403)

    # Only accept GPS updates while a job is actively in progress
    active_job = Job.objects.filter(
        courier=courier,
        status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS],
    ).first()

    if not active_job:
        return JsonResponse({"success": False, "error": "No active job"}, status=403)

    # Parse coordinates
    try:
        body = json.loads(request.body)
        lat  = float(body['lat'])
        lng  = float(body['lng'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({"success": False, "error": "Invalid lat/lng"}, status=400)

    # ── Step 1: Save position to PostGIS ────────────────────────────────────
    courier.set_location(lat, lng)

    # ── Step 2: Log to history ───────────────────────────────────────────────
    # Creates a permanent audit trail for trajectory analysis and
    # benchmarking the geofencing engine.
    CourierLocationHistory.objects.create(
        courier  = courier,
        location = Point(lng, lat, srid=4326),
    )

    # ── Step 3: Dispatch geofencing evaluation (async) ───────────────────────
    # .delay() queues the task in Redis and returns immediately.
    # The Celery worker picks it up and runs the full pipeline:
    #   EMA smoothing → PostGIS bounding box → Winding Number PiP → state machine
    try:
        from Truck.tasks import evaluate_geofences_task
        evaluate_geofences_task.delay(courier.pk, lat, lng)
    except Exception:
        # Never let a Celery dispatch failure break the GPS update.
        # Log it but still return success — the position was saved.
        import logging
        logging.getLogger(__name__).exception(
            "Failed to dispatch evaluate_geofences_task for courier %s", courier.pk
        )

    return JsonResponse({"success": True})


# ── Customer polls courier location ───────────────────────────────────────────
def courier_location_api(request, job_id):
    """
    GET — returns courier lat/lng only while job is picking/delivering.
    Returns visible:false for completed/cancelled — coordinates never
    exposed after a job closes (privacy requirement).
    """
    auth_error = _json_auth_check(request)
    if auth_error:
        return auth_error

    try:
        job = Job.objects.select_related('courier').get(
            id=job_id,
            Customer=request.user.customer,
        )
    except Job.DoesNotExist:
        return JsonResponse({"success": False, "error": "Job not found"}, status=404)

    if job.status in (Job.COMPLETED_STATUS, Job.CANCELED_STATUS):
        return JsonResponse({"success": True, "visible": False, "status": job.status})

    if not job.courier or not job.courier.location:
        return JsonResponse({"success": True, "visible": False, "status": job.status})

    return JsonResponse({
        "success": True,
        "visible": True,
        "lat":     job.courier.lat,
        "lng":     job.courier.lng,
        "status":  job.status,
    })


# ── OSRM proxy ────────────────────────────────────────────────────────────────
def osrm_proxy(request):
    """
    Proxy OSRM requests from the browser to the Docker-internal OSRM container.
    The browser cannot resolve http://osrm:5000 — Django resolves it instead.
    """
    import requests as http_requests
    from django.conf import settings

    path  = request.GET.get('path', '')
    query = request.GET.get('query', '')

    if not path:
        return JsonResponse({"error": "path parameter required"}, status=400)

    osrm_base = getattr(settings, 'OSRM_BASE_URL', 'http://osrm:5000')
    url = f"{osrm_base}{path}"
    if query:
        url += f"?{query}"

    try:
        resp = http_requests.get(url, timeout=10)
        return JsonResponse(resp.json(), safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)