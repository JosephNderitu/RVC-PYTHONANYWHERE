"""
Truck/geofencing/evaluator.py — Main geofencing pipeline.
Stages: EMA Smooth → PostGIS bboverlaps → Winding Number PiP → State Machine → Event
"""
import logging
from django.contrib.gis.geos import Point

from Truck.models import Courier, DeliveryZone, GeofenceEvent, CourierZoneState
from .smoothing     import ExponentialSmoother
from .pip           import point_in_polygon, extract_polygon_coords
from .state_machine import process_reading
from django.contrib.gis.measure import Distance

logger = logging.getLogger(__name__)


def evaluate_courier_position(courier: Courier, raw_lat: float, raw_lng: float) -> None:
    try:
        # Stage 1: EMA smoothing
        smoothed_lat, smoothed_lng = ExponentialSmoother.smooth(
            raw_lat, raw_lng,
            courier.smoothed_lat,
            courier.smoothed_lng,
        )
        Courier.objects.filter(pk=courier.pk).update(
            smoothed_lat=smoothed_lat, smoothed_lng=smoothed_lng,
        )
        logger.debug("Courier %s | raw=(%.6f,%.6f) smoothed=(%.6f,%.6f)",
                     courier.pk, raw_lat, raw_lng, smoothed_lat, smoothed_lng)

        # Stage 2: PostGIS candidate zones via GiST bounding box
        smooth_point = Point(smoothed_lng, smoothed_lat, srid=4326)
        candidate_zones = list(DeliveryZone.objects.filter(
            is_active=True,
            boundary__distance_lte=(smooth_point, Distance(km=15)),
        ))

        if not candidate_zones:
            return

        # Stages 3+4: PiP + state machine per zone
        for zone in candidate_zones:
            _evaluate_zone(courier, zone, smoothed_lat, smoothed_lng, smooth_point)

    except Exception:
        logger.exception("Geofencing pipeline error courier=%s (%.6f,%.6f)",
                         courier.pk, raw_lat, raw_lng)


def _evaluate_zone(courier, zone, smoothed_lat, smoothed_lng, smooth_point):
    # Stage 3: Winding Number PiP
    polygon_coords = extract_polygon_coords(zone.boundary)
    is_inside = point_in_polygon((smoothed_lat, smoothed_lng), polygon_coords)

    # Stage 4: State machine
    zone_state, _ = CourierZoneState.objects.get_or_create(
        courier=courier, zone=zone,
        defaults={'state': CourierZoneState.OUTSIDE,
                  'consecutive_inside': 0, 'consecutive_outside': 0},
    )

    new_state, new_ci, new_co, event = process_reading(
        is_inside,
        zone_state.state,
        zone_state.consecutive_inside,
        zone_state.consecutive_outside,
    )

    if (new_state != zone_state.state or
            new_ci != zone_state.consecutive_inside or
            new_co != zone_state.consecutive_outside):
        CourierZoneState.objects.filter(pk=zone_state.pk).update(
            state=new_state,
            consecutive_inside=new_ci,
            consecutive_outside=new_co,
        )

    logger.debug("Courier %s | Zone '%s' | PiP=%s | %s→%s | ci=%d co=%d | event=%s",
                 courier.pk, zone.name, is_inside,
                 zone_state.state, new_state, new_ci, new_co, event)

    if event is not None:
        _fire_geofence_event(courier, zone, event, smooth_point)


def _fire_geofence_event(courier, zone, event_type, location):
    geofence_event = GeofenceEvent.objects.create(
        courier=courier, zone=zone,
        event_type=event_type, trigger_location=location,
    )
    logger.info("🔔 GEOFENCE %s | Courier '%s' | Zone '%s' | pk=%s",
                event_type.upper(), courier, zone.name, geofence_event.pk)

    try:
        _on_geofence_event(courier, zone, event_type, geofence_event)
    except Exception:
        logger.exception("Notification failed for geofence event %s", geofence_event.pk)


def _on_geofence_event(courier, zone, event_type, geofence_event):
    if event_type != GeofenceEvent.ENTER:
        logger.info("Geofence EXIT recorded: courier=%s zone=%s", courier, zone.name)
        return
    try:
        from Truck.notifications import notify_geofence_enter
        notify_geofence_enter(courier, zone, geofence_event)
    except Exception as exc:
        logger.error("notify_geofence_enter failed: %s", exc)