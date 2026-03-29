# Truck/distance_engine.py
"""
RVC Distance Computation Engine — Phase 1
Implements three computation methods per the proposal:
  - Haversine   : fast spherical approximation, good for < 1km
  - Geodesic    : accurate ellipsoidal (Karney/GeographicLib), good for 1–5km
  - Road network: OSRM (Phase 2 — placeholder returns geodesic for now)

All functions accept (lat1, lng1, lat2, lng2) as floats and return
a dict with distance_km, duration_minutes, method, and price.
"""

import math
import logging
import requests
from geopy.distance import geodesic as geopy_geodesic
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Pricing constants (adjust per RVC business rules) ────────────────────────
BASE_FARE_KES        = 50.0   # fixed base charge
RATE_PER_KM_KES      = 30.0   # per km rate
MIN_FARE_KES         = 80.0   # minimum job price
DURATION_PER_KM_MIN  = 2.5    # estimated minutes per km (urban Nairobi/Mombasa)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Spherical Haversine formula.
    Error vs geodesic: ~0.3% over short distances (<50km).
    Appropriate for: pricing preview, very short routes.
    """
    R = 6371.0  # Earth mean radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlmbd = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmbd / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _geodesic_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Karney geodesic via geopy — accurate to ~0.6mm on WGS84 ellipsoid.
    Appropriate for: all pricing calculations, ETA, zone boundaries.
    """
    return geopy_geodesic((lat1, lng1), (lat2, lng2)).km


def _osrm_km(lat1: float, lng1: float, lat2: float, lng2: float):
    """
    Road-network distance via self-hosted OSRM (Phase 2).
    Falls back to geodesic if OSRM is not yet running.
    Returns (distance_km, duration_minutes) or None on failure.
    """
    osrm_base = getattr(settings, 'OSRM_BASE_URL', None)
    if not osrm_base:
        return None  # OSRM not configured yet — caller handles fallback

    url = (
        f"{osrm_base}/route/v1/driving/"
        f"{lng1},{lat1};{lng2},{lat2}"
        f"?overview=false&alternatives=false"
    )
    try:
        resp = requests.get(url, timeout=3)
        data = resp.json()
        if data.get('code') == 'Ok':
            route = data['routes'][0]
            dist_km   = round(route['distance'] / 1000, 2)
            dur_min   = round(route['duration'] / 60,   1)
            return dist_km, dur_min
    except Exception as exc:
        logger.warning("OSRM request failed: %s — falling back to geodesic", exc)
    return None


def _compute_price(distance_km: float) -> float:
    raw = BASE_FARE_KES + (distance_km * RATE_PER_KM_KES)
    return round(max(raw, MIN_FARE_KES), 2)


def _compute_duration(distance_km: float) -> int:
    return max(1, int(distance_km * DURATION_PER_KM_MIN))


# ── Public API ────────────────────────────────────────────────────────────────

def compute_distance(
    lat1: float, lng1: float,
    lat2: float, lng2: float,
    prefer: str = 'auto',
) -> dict:
    """
    Main entry point. Returns:
    {
        'distance_km':    float,
        'duration_min':   int,
        'price':          float,
        'method':         str,   # 'haversine' | 'geodesic' | 'osrm'
        'error':          str | None,
    }

    prefer='auto' selects method by distance range:
      < 1 km  → haversine  (sub-ms, sufficient accuracy for micro-routes)
      1–5 km  → geodesic   (accurate ellipsoidal, no network call)
      > 5 km  → osrm first, geodesic fallback
    """
    result = {
        'distance_km':  0.0,
        'duration_min': 0,
        'price':        0.0,
        'method':       'unknown',
        'error':        None,
    }

    try:
        # --- try OSRM first for longer routes when prefer='auto' or 'osrm' ---
        if prefer in ('auto', 'osrm'):
            osrm = _osrm_km(lat1, lng1, lat2, lng2)
            if osrm:
                dist_km, dur_min = osrm
                result.update({
                    'distance_km':  dist_km,
                    'duration_min': int(dur_min),
                    'price':        _compute_price(dist_km),
                    'method':       'osrm',
                })
                return result

        # --- geodesic (always accurate, no network dependency) ---
        geodesic_km = _geodesic_km(lat1, lng1, lat2, lng2)

        if prefer == 'haversine' or (prefer == 'auto' and geodesic_km < 1.0):
            haversine_km = _haversine_km(lat1, lng1, lat2, lng2)
            result.update({
                'distance_km':  round(haversine_km, 2),
                'duration_min': _compute_duration(haversine_km),
                'price':        _compute_price(haversine_km),
                'method':       'haversine',
            })
        else:
            result.update({
                'distance_km':  round(geodesic_km, 2),
                'duration_min': _compute_duration(geodesic_km),
                'price':        _compute_price(geodesic_km),
                'method':       'geodesic',
            })

    except Exception as exc:
        logger.error("Distance computation failed: %s", exc)
        result['error'] = str(exc)

    return result


def compare_methods(
    lat1: float, lng1: float,
    lat2: float, lng2: float,
) -> dict:
    """
    Benchmark all three methods for a given coordinate pair.
    Used in Phase 1 validation / benchmarking scripts.
    Returns comparison dict with all three results.
    """
    haversine_km = round(_haversine_km(lat1, lng1, lat2, lng2), 4)
    geodesic_km  = round(_geodesic_km(lat1, lng1, lat2, lng2), 4)
    osrm_result  = _osrm_km(lat1, lng1, lat2, lng2)

    geodesic_error_pct = round(
        abs(haversine_km - geodesic_km) / geodesic_km * 100, 4
    ) if geodesic_km else 0

    return {
        'haversine_km':       haversine_km,
        'geodesic_km':        geodesic_km,
        'osrm_km':            osrm_result[0] if osrm_result else None,
        'osrm_duration_min':  osrm_result[1] if osrm_result else None,
        'haversine_error_pct': geodesic_error_pct,
        'recommended_method': (
            'haversine' if geodesic_km < 1
            else 'geodesic' if geodesic_km < 5
            else 'osrm'
        ),
    }