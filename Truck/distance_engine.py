# Truck/distance_engine.py
"""
RVC Distance Computation Engine — Phase 1
RiftValley Carriers — US Trucking Operations (Georgia + surrounding states)

Distances in MILES. Prices in USD.
"""

import math
import logging
import requests
from geopy.distance import geodesic as geopy_geodesic
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_FARE_USD        = 50.00
RATE_PER_MILE_USD    = 2.50
MIN_FARE_USD         = 75.00
FUEL_SURCHARGE_PCT   = 0.08
AVG_SPEED_LOCAL_MPH  = 45.0
AVG_SPEED_HIGHWAY_MPH = 62.0
METERS_PER_MILE      = 1609.344


def _validate_coords(lat1, lng1, lat2, lng2):
    """
    Validates coordinates are within reasonable US bounds.
    Georgia + surroundings: lat 24-37, lng -92 to -75
    """
    for lat in (lat1, lat2):
        if not (24.0 <= lat <= 50.0):
            raise ValueError(f"Latitude {lat} out of US range (24-50)")
    for lng in (lng1, lng2):
        if not (-130.0 <= lng <= -65.0):
            raise ValueError(f"Longitude {lng} out of US range (-130 to -65). "
                             f"US longitudes are NEGATIVE. Got {lng} — did you swap lat/lng?")


def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlmbd = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmbd / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _geodesic_km(lat1, lng1, lat2, lng2):
    return geopy_geodesic((lat1, lng1), (lat2, lng2)).km


def _osrm_query(lat1, lng1, lat2, lng2):
    """
    Road distance via self-hosted OSRM.
    OSRM URL format: /route/v1/driving/{lon1},{lat1};{lon2},{lat2}
    Returns (distance_miles, duration_minutes) or None.
    """
    osrm_base = getattr(settings, 'OSRM_BASE_URL', None)
    if not osrm_base:
        return None

    # OSRM expects longitude FIRST, then latitude
    url = (
        f"{osrm_base}/route/v1/driving/"
        f"{lng1},{lat1};{lng2},{lat2}"
        f"?overview=false&alternatives=false&steps=false"
    )
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if data.get('code') != 'Ok':
            logger.warning("OSRM returned non-Ok code: %s", data.get('code'))
            return None

        route       = data['routes'][0]
        raw_meters  = route['distance']
        raw_seconds = route['duration']

        # Sanity check — Atlanta to Savannah is ~260 miles, max GA route ~500 miles
        dist_miles = round(raw_meters / METERS_PER_MILE, 2)
        if dist_miles > 2000:
            logger.error(
                "OSRM returned implausible distance: %.1f miles (%.0f meters). "
                "Coords: (%.4f,%.4f) → (%.4f,%.4f). Falling back to geodesic.",
                dist_miles, raw_meters, lat1, lng1, lat2, lng2
            )
            return None

        dur_minutes = round(raw_seconds / 60, 1)
        logger.info("OSRM route: %.2f miles, %.1f min", dist_miles, dur_minutes)
        return dist_miles, dur_minutes

    except Exception as exc:
        logger.warning("OSRM request failed: %s — falling back to geodesic", exc)
    return None


def _compute_price(distance_miles):
    mileage_cost   = distance_miles * RATE_PER_MILE_USD
    subtotal       = BASE_FARE_USD + mileage_cost
    fuel_surcharge = mileage_cost * FUEL_SURCHARGE_PCT
    return round(max(subtotal + fuel_surcharge, MIN_FARE_USD), 2)


def _compute_duration(distance_miles):
    speed = AVG_SPEED_HIGHWAY_MPH if distance_miles > 50 else AVG_SPEED_LOCAL_MPH
    return max(15, int((distance_miles / speed) * 60))


def compute_distance(lat1, lng1, lat2, lng2, prefer='auto'):
    """
    Main entry point. Returns distance in miles, price in USD.

    IMPORTANT — coordinate order: lat first, lng second.
    Atlanta example: compute_distance(33.7490, -84.3880, ...)
    """
    result = {
        'distance_miles': 0.0,
        'distance_km':    0.0,
        'duration_min':   0,
        'price_usd':      0.0,
        'method':         'unknown',
        'error':          None,
    }

    try:
        _validate_coords(lat1, lng1, lat2, lng2)

        if prefer in ('auto', 'osrm'):
            osrm = _osrm_query(lat1, lng1, lat2, lng2)
            if osrm:
                dist_miles, dur_min = osrm
                result.update({
                    'distance_miles': dist_miles,
                    'distance_km':    round(dist_miles * 1.60934, 2),
                    'duration_min':   int(dur_min),
                    'price_usd':      _compute_price(dist_miles),
                    'method':         'osrm',
                })
                return result

        geodesic_km    = _geodesic_km(lat1, lng1, lat2, lng2)
        geodesic_miles = round(geodesic_km * 0.621371, 2)

        if prefer == 'haversine' or (prefer == 'auto' and geodesic_miles < 1.0):
            hav_miles = round(_haversine_km(lat1, lng1, lat2, lng2) * 0.621371, 2)
            result.update({
                'distance_miles': hav_miles,
                'distance_km':    round(hav_miles * 1.60934, 2),
                'duration_min':   _compute_duration(hav_miles),
                'price_usd':      _compute_price(hav_miles),
                'method':         'haversine',
            })
        else:
            result.update({
                'distance_miles': geodesic_miles,
                'distance_km':    round(geodesic_km, 2),
                'duration_min':   _compute_duration(geodesic_miles),
                'price_usd':      _compute_price(geodesic_miles),
                'method':         'geodesic',
            })

    except ValueError as ve:
        logger.error("Coordinate validation failed: %s", ve)
        result['error'] = str(ve)
    except Exception as exc:
        logger.error("Distance computation failed: %s", exc)
        result['error'] = str(exc)

    return result


def compare_methods(lat1, lng1, lat2, lng2):
    """Benchmark all three methods for a coordinate pair."""
    _validate_coords(lat1, lng1, lat2, lng2)
    hav_km    = round(_haversine_km(lat1, lng1, lat2, lng2), 4)
    geo_km    = round(_geodesic_km(lat1, lng1, lat2, lng2), 4)
    osrm      = _osrm_query(lat1, lng1, lat2, lng2)
    geo_miles = round(geo_km * 0.621371, 4)
    hav_error = round(abs(hav_km - geo_km) / geo_km * 100, 4) if geo_km else 0

    return {
        'haversine_miles':     round(hav_km * 0.621371, 4),
        'geodesic_miles':      geo_miles,
        'osrm_miles':          osrm[0] if osrm else None,
        'osrm_duration_min':   osrm[1] if osrm else None,
        'haversine_error_pct': hav_error,
        'recommended_method':  'osrm' if osrm else ('haversine' if geo_miles < 1 else 'geodesic'),
        'price_usd':           _compute_price(geo_miles),
    }