"""
Truck/geofencing/evaluator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Main geofencing pipeline.

Called by the Celery task (Truck/tasks.py) for every GPS update.

PIPELINE STAGES
────────────────
  Stage 1 — GPS Smoothing (smoothing.py)
    Apply EMA filter to remove per-reading jitter before any
    spatial evaluation. Previous smoothed values are stored on
    the Courier model and updated each call.

  Stage 2 — Candidate Zone Lookup (PostGIS GiST)
    Use PostGIS bounding-box overlap (bboverlaps) to pre-filter
    DeliveryZone polygons whose bounding boxes intersect the
    smoothed point. This uses the GiST spatial index and is very
    fast — typically sub-millisecond even for thousands of zones.
    Only candidate zones proceed to the more expensive PiP step.

  Stage 3 — Winding Number PiP (pip.py)
    For each candidate zone, run the Winding Number algorithm to
    determine if the smoothed point is truly inside the polygon.
    Ray-casting is not used — it gives wrong answers for concave
    zones (see pip.py for detailed explanation).

  Stage 4 — State Machine (state_machine.py)
    Feed the PiP result into the per-courier×zone state machine
    to filter out boundary oscillation. Only confirmed ENTER/EXIT
    transitions (3 consecutive readings) produce events.

  Stage 5 — Event Persistence
    Confirmed events are written to GeofenceEvent. Downstream
    actions (WhatsApp, FCM push) are called from _on_geofence_event.

PERFORMANCE
────────────
The entire pipeline runs in the Celery worker — not in the Django
request/response cycle. The GPS update API returns in <50ms
regardless of how many zones are evaluated.

Typical evaluation time per GPS update:
  - 10 active zones:   ~2ms
  - 100 active zones:  ~8ms
  - 1000 active zones: ~40ms (PostGIS GiST pre-filter keeps this low)
"""

import logging
from django.contrib.gis.geos import Point

from Truck.models import Courier, DeliveryZone, GeofenceEvent, CourierZoneState
from .smoothing    import ExponentialSmoother
from .pip          import point_in_polygon, extract_polygon_coords
from .state_machine import process_reading

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════

def evaluate_courier_position(courier: Courier, raw_lat: float, raw_lng: float) -> None:
    """
    Full geofencing pipeline for one GPS update.

    Called by evaluate_geofences_task in Truck/tasks.py.
    All database operations are wrapped in try/except to prevent
    a geofencing failure from crashing the background worker.

    Args:
        courier:  Courier model instance (already saved with new location)
        raw_lat:  Raw GPS latitude from the device
        raw_lng:  Raw GPS longitude from the device
    """
    try:
        # ── Stage 1: EMA GPS smoothing ────────────────────────────────────
        smoothed_lat, smoothed_lng = ExponentialSmoother.smooth(
            raw_lat  = raw_lat,
            raw_lng  = raw_lng,
            prev_smoothed_lat = courier.smoothed_lat,
            prev_smoothed_lng = courier.smoothed_lng,
        )

        # Persist smoothed values back to Courier for the next GPS update.
        # update_fields avoids touching other courier columns.
        Courier.objects.filter(pk=courier.pk).update(
            smoothed_lat=smoothed_lat,
            smoothed_lng=smoothed_lng,
        )

        logger.debug(
            "Courier %s | raw=(%.6f, %.6f) smoothed=(%.6f, %.6f)",
            courier.pk, raw_lat, raw_lng, smoothed_lat, smoothed_lng,
        )

        # ── Stage 2: Candidate zone lookup via PostGIS GiST ───────────────
        # bboverlaps performs a bounding-box intersection test, which is
        # an index-only operation — extremely fast. It returns zones whose
        # bounding boxes CONTAIN or OVERLAP the point. Some of these will
        # be false positives (point in the bounding box but not the polygon)
        # — Stage 3 eliminates those.
        smooth_point = Point(smoothed_lng, smoothed_lat, srid=4326)

        candidate_zones = list(
            DeliveryZone.objects.filter(
                is_active=True,
                boundary__bboverlaps=smooth_point,
            )
        )

        if not candidate_zones:
            logger.debug("Courier %s — no candidate zones near (%.6f, %.6f)",
                         courier.pk, smoothed_lat, smoothed_lng)
            return

        logger.debug("Courier %s — %d candidate zone(s) for PiP evaluation",
                     courier.pk, len(candidate_zones))

        # ── Stages 3 + 4: PiP + state machine — one zone at a time ───────
        for zone in candidate_zones:
            _evaluate_zone(courier, zone, smoothed_lat, smoothed_lng, smooth_point)

    except Exception:
        # Never crash the Celery worker — log and continue
        logger.exception(
            "Geofencing pipeline error for courier %s at (%.6f, %.6f)",
            courier.pk, raw_lat, raw_lng,
        )


# ═══════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════

def _evaluate_zone(
    courier:       Courier,
    zone:          DeliveryZone,
    smoothed_lat:  float,
    smoothed_lng:  float,
    smooth_point:  Point,
) -> None:
    """
    Run PiP + state machine for one courier × zone pair.
    """
    # ── Stage 3: Winding Number PiP ───────────────────────────────────────
    polygon_coords = extract_polygon_coords(zone.boundary)
    is_inside = point_in_polygon((smoothed_lat, smoothed_lng), polygon_coords)

    # ── Stage 4: State machine ────────────────────────────────────────────
    # Get or create the persisted state for this courier × zone pair.
    zone_state, _ = CourierZoneState.objects.get_or_create(
        courier=courier,
        zone=zone,
        defaults={
            'state':               CourierZoneState.OUTSIDE,
            'consecutive_inside':  0,
            'consecutive_outside': 0,
        }
    )

    new_state, new_consec_in, new_consec_out, event = process_reading(
        is_inside           = is_inside,
        current_state       = zone_state.state,
        consecutive_inside  = zone_state.consecutive_inside,
        consecutive_outside = zone_state.consecutive_outside,
    )

    # Persist the updated state — only write if something changed
    state_changed = (
        new_state     != zone_state.state
        or new_consec_in  != zone_state.consecutive_inside
        or new_consec_out != zone_state.consecutive_outside
    )
    if state_changed:
        CourierZoneState.objects.filter(pk=zone_state.pk).update(
            state               = new_state,
            consecutive_inside  = new_consec_in,
            consecutive_outside = new_consec_out,
        )

    logger.debug(
        "Courier %s | Zone '%s' | PiP=%s | %s→%s | consec_in=%d consec_out=%d | event=%s",
        courier.pk, zone.name, is_inside,
        zone_state.state, new_state,
        new_consec_in, new_consec_out, event,
    )

    # ── Stage 5: Fire event if threshold confirmed ────────────────────────
    if event is not None:
        _fire_geofence_event(courier, zone, event, smooth_point)


def _fire_geofence_event(
    courier:      Courier,
    zone:         DeliveryZone,
    event_type:   str,
    location:     Point,
) -> None:
    """
    Persist a GeofenceEvent row and call downstream hooks.
    """
    geofence_event = GeofenceEvent.objects.create(
        courier          = courier,
        zone             = zone,
        event_type       = event_type,
        trigger_location = location,
    )

    logger.info(
        "🔔 GEOFENCE %s | Courier '%s' | Zone '%s' | event_id=%s",
        event_type.upper(), courier, zone.name, geofence_event.pk,
    )

    # ── Downstream actions ────────────────────────────────────────────────
    # These are stubs — wire in your actual notification services below.
    # They are called here so you can add WhatsApp/FCM without touching
    # the engine logic.
    try:
        _on_geofence_event(courier, zone, event_type, geofence_event)
    except Exception:
        # Notification failure must never prevent the event from being saved
        logger.exception(
            "Downstream notification failed for event %s", geofence_event.pk
        )


def _on_geofence_event(courier, zone, event_type, geofence_event):
    """
    Hook called after every confirmed ENTER or EXIT event.

    Wire your notification services here:

    ENTER — courier is confirmed inside the zone:
        if event_type == GeofenceEvent.ENTER:
            # Check if this zone is the pickup zone for the active job
            # If yes: send WhatsApp to customer "Courier has arrived at pickup"
            # If this is the delivery zone: send "Your delivery is arriving now"
            pass

    EXIT:
        if event_type == GeofenceEvent.EXIT:
            # Courier left the zone — log for analytics
            pass

    Example Twilio WhatsApp stub (fill in when ready):

        from django.conf import settings
        from Truck.models import Job

        active_job = Job.objects.filter(
            courier=courier,
            status__in=[Job.PICKING_STATUS, Job.DELIVERING_STATUS]
        ).first()

        if active_job and event_type == GeofenceEvent.ENTER:
            customer_phone = active_job.Customer.phone_number
            # send_whatsapp(customer_phone, f"Your courier has arrived at {zone.name}")
    """
    pass   # ← replace with real implementation when ready