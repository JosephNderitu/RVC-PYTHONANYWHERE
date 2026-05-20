# Truck/distance_engine.py
"""
RVC Distance Computation Engine
RiftValley Carriers — US Trucking Operations (Georgia + surrounding states)

Routing fallback chain (in order):
  1. OSRM          — self-hosted, southeastern US, unlimited, most accurate
  2. OpenRouteService — free global fallback (2,000 req/day, no credit card)
  3. Geodesic       — straight-line estimate when all routing fails

Traffic:
  - ORS provides speed-limit-aware duration (no API needed beyond ORS key)
  - TomTom free tier for real-time traffic colour overlay on maps
  - Built-in time-of-day multiplier when no traffic API is configured

Distances in MILES. Prices in USD.
"""

import math
import logging
import requests
from datetime import datetime
from geopy.distance import geodesic as geopy_geodesic
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Pricing constants ─────────────────────────────────────────────────────────
BASE_FARE_USD         = 50.00
RATE_PER_MILE_USD     = 2.50
MIN_FARE_USD          = 75.00
FUEL_SURCHARGE_PCT    = 0.08
AVG_SPEED_LOCAL_MPH   = 45.0
AVG_SPEED_HIGHWAY_MPH = 62.0
METERS_PER_MILE       = 1609.344

# ── OSRM validation ───────────────────────────────────────────────────────────
OSRM_MIN_RATIO = 0.85   # reject if OSRM < 85% of straight-line
OSRM_MAX_RATIO = 3.0    # reject if OSRM > 3× straight-line

# ── ORS endpoint ──────────────────────────────────────────────────────────────
ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"


# ═══════════════════════════════════════════════════════════════════════════════
#   COORDINATE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_coords(lat1, lng1, lat2, lng2):
    for lat in (lat1, lat2):
        if not (24.0 <= lat <= 50.0):
            raise ValueError(f"Latitude {lat} out of US range (24-50)")
    for lng in (lng1, lng2):
        if not (-130.0 <= lng <= -65.0):
            raise ValueError(
                f"Longitude {lng} out of US range (-130 to -65). "
                f"US longitudes are NEGATIVE. Got {lng}."
            )


# ═══════════════════════════════════════════════════════════════════════════════
#   STRAIGHT-LINE DISTANCE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
#   TRAFFIC — TIME OF DAY MULTIPLIER
#   Used when no traffic API is configured.
#   Based on typical US Eastern timezone rush-hour patterns.
# ═══════════════════════════════════════════════════════════════════════════════

def _traffic_multiplier():
    """
    Returns a duration multiplier based on time of day (Eastern Time).
    No API key required — built-in heuristic.

    Typical delays:
      Morning rush 7-9am:   +35%
      Lunch 11am-2pm:       +15%
      Evening rush 4-7pm:   +45%
      Night 10pm-5am:       -10% (light traffic)
      Weekend:              +10%
    """
    try:
        import pytz
        tz = pytz.timezone('America/New_York')
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    hour    = now.hour
    weekday = now.weekday()   # 0=Mon … 6=Sun

    if weekday >= 5:          # Weekend
        return 1.10

    if 7 <= hour <= 9:        # Morning rush
        return 1.35
    if 16 <= hour <= 18:      # Evening rush (peak 5-6PM)
        return 1.45
    if 11 <= hour <= 13:      # Lunch hour
        return 1.15
    if hour >= 22 or hour <= 5:  # Night — clear roads
        return 0.90

    return 1.00               # Normal daytime


def traffic_adjusted_duration(base_minutes, apply_traffic=True):
    """
    Apply a traffic multiplier to a base drive time.
    Pass apply_traffic=False to get the raw routing duration.
    """
    if not apply_traffic:
        return base_minutes
    return round(base_minutes * _traffic_multiplier(), 1)


# ═══════════════════════════════════════════════════════════════════════════════
#   ROUTER 1 — OSRM (self-hosted, southeastern US)
# ═══════════════════════════════════════════════════════════════════════════════

def _osrm_query(lat1, lng1, lat2, lng2):
    """
    Road route via self-hosted OSRM.
    OSRM expects longitude first, then latitude.
    Returns (distance_miles, duration_minutes) or None.
    """
    osrm_base = getattr(settings, 'OSRM_BASE_URL', None)
    if not osrm_base:
        return None

    url = (f"{osrm_base}/route/v1/driving/"
           f"{lng1},{lat1};{lng2},{lat2}"
           f"?overview=false&alternatives=false&steps=false")
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get('code') != 'Ok':
            return None

        dist_miles  = round(data['routes'][0]['distance'] / METERS_PER_MILE, 2)
        dur_minutes = round(data['routes'][0]['duration'] / 60, 1)
        logger.info("OSRM: %.2f mi, %.1f min", dist_miles, dur_minutes)
        return dist_miles, dur_minutes

    except Exception as exc:
        logger.warning("OSRM failed: %s", exc)
    return None


def _validate_osrm(osrm_miles, geodesic_miles, lat1, lng1, lat2, lng2):
    """
    Returns True if OSRM result is plausible.
    Road distance must be ≥ 85% of straight-line (guards against
    OSRM snapping out-of-coverage coordinates to network boundary).
    """
    if geodesic_miles < 0.1:
        return True
    ratio = osrm_miles / geodesic_miles
    if ratio < OSRM_MIN_RATIO:
        logger.error(
            "OSRM COVERAGE: %.1f mi < 85%% of geodesic %.1f mi — "
            "coordinate outside southeastern US coverage. Falling back to ORS.",
            osrm_miles, geodesic_miles
        )
        return False
    if ratio > OSRM_MAX_RATIO:
        logger.warning("OSRM returned %.1f× geodesic — discarding.", ratio)
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#   ROUTER 2 — OPENROUTESERVICE (free global fallback, no credit card)
#
#   Free registration (no credit card):
#     https://openrouteservice.org/dev/#/signup
#   Free tier: 2,000 requests/day, 40 requests/minute
#   Add to settings.py:  ORS_API_KEY = 'your_free_key_here'
# ═══════════════════════════════════════════════════════════════════════════════

def _ors_query(lat1, lng1, lat2, lng2):
    """
    Road route via OpenRouteService (free global fallback).
    Returns (distance_miles, duration_minutes) or None.

    ORS uses speed-limit-aware routing — durations are more realistic
    than OSRM for routes OSRM can't cover (e.g. out-of-state).

    ORS expects coordinates as [longitude, latitude] arrays.
    """
    ors_key = getattr(settings, 'ORS_API_KEY', None)
    if not ors_key:
        logger.debug("ORS_API_KEY not set — skipping ORS fallback")
        return None

    headers = {
        'Authorization': ors_key,
        'Content-Type':  'application/json',
    }
    body = {
        "coordinates": [
            [lng1, lat1],   # ORS: [lng, lat]
            [lng2, lat2],
        ],
        "profile":        "driving-car",
        "format":         "json",
        "units":          "mi",
        "geometry":       False,   # distance + duration only (no geometry)
        "instructions":   False,
    }

    try:
        resp = requests.post(ORS_BASE_URL, json=body, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        summary   = data['routes'][0]['summary']

        dist_miles  = round(summary['distance'], 2)   # already in miles (units=mi)
        dur_minutes = round(summary['duration'] / 60, 1)

        logger.info("ORS fallback: %.2f mi, %.1f min", dist_miles, dur_minutes)
        return dist_miles, dur_minutes

    except Exception as exc:
        logger.warning("ORS failed: %s", exc)
    return None


def _ors_route_geometry(lat1, lng1, lat2, lng2):
    """
    Fetch the full route geometry from ORS for drawing on Leaflet.
    Returns list of [lat, lng] pairs or None.
    Used by the frontend proxy to draw the route polyline.
    """
    ors_key = getattr(settings, 'ORS_API_KEY', None)
    if not ors_key:
        return None

    headers = {
        'Authorization': ors_key,
        'Content-Type':  'application/json',
    }
    body = {
        "coordinates": [[lng1, lat1], [lng2, lat2]],
        "profile":      "driving-car",
        "format":       "geojson",
        "units":        "mi",
        "instructions": False,
    }

    try:
        resp = requests.post(ORS_BASE_URL, json=body, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        coords = data['features'][0]['geometry']['coordinates']
        # GeoJSON is [lng, lat] — convert to Leaflet [lat, lng]
        return [[c[1], c[0]] for c in coords]
    except Exception as exc:
        logger.warning("ORS geometry fetch failed: %s", exc)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#   PRICING
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_price(distance_miles):
    mileage_cost   = distance_miles * RATE_PER_MILE_USD
    subtotal       = BASE_FARE_USD + mileage_cost
    fuel_surcharge = mileage_cost * FUEL_SURCHARGE_PCT
    return round(max(subtotal + fuel_surcharge, MIN_FARE_USD), 2)


def _compute_duration(distance_miles):
    speed = AVG_SPEED_HIGHWAY_MPH if distance_miles > 50 else AVG_SPEED_LOCAL_MPH
    return max(15, int((distance_miles / speed) * 60))


# ═══════════════════════════════════════════════════════════════════════════════
#   MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def compute_distance(lat1, lng1, lat2, lng2, prefer='auto', apply_traffic=True):
    """
    Compute road distance with full fallback chain:
      OSRM (southeastern US) → ORS (global, free) → Geodesic (straight-line)

    Returns dict with:
      distance_miles  — road distance (or straight-line if all routing failed)
      distance_km
      duration_min    — drive time WITH traffic multiplier applied
      duration_min_no_traffic — raw drive time (no multiplier)
      price_usd
      method          — 'osrm' | 'ors' | 'geodesic' | 'haversine'
      traffic_level   — 'normal' | 'light' | 'moderate' | 'heavy'
      traffic_multiplier
      osrm_coverage_warn — True when routing fell back to ORS or geodesic
      error
    """
    result = {
        'distance_miles':         0.0,
        'distance_km':            0.0,
        'duration_min':           0,
        'duration_min_no_traffic': 0,
        'price_usd':              0.0,
        'method':                 'unknown',
        'traffic_level':          'normal',
        'traffic_multiplier':     1.0,
        'osrm_coverage_warn':     False,
        'error':                  None,
    }

    try:
        _validate_coords(lat1, lng1, lat2, lng2)

        geodesic_km    = _geodesic_km(lat1, lng1, lat2, lng2)
        geodesic_miles = round(geodesic_km * 0.621371, 2)

        multiplier = _traffic_multiplier()
        result['traffic_multiplier'] = multiplier
        result['traffic_level'] = (
            'heavy'    if multiplier >= 1.40 else
            'moderate' if multiplier >= 1.20 else
            'light'    if multiplier <= 0.95 else
            'normal'
        )

        # ── 1. Try OSRM ──────────────────────────────────────────────────
        if prefer in ('auto', 'osrm'):
            osrm = _osrm_query(lat1, lng1, lat2, lng2)
            if osrm and _validate_osrm(osrm[0], geodesic_miles, lat1, lng1, lat2, lng2):
                raw_min = osrm[1]
                adj_min = int(traffic_adjusted_duration(raw_min, apply_traffic))
                result.update({
                    'distance_miles':          osrm[0],
                    'distance_km':             round(osrm[0] * 1.60934, 2),
                    'duration_min':            adj_min,
                    'duration_min_no_traffic': int(raw_min),
                    'price_usd':               _compute_price(osrm[0]),
                    'method':                  'osrm',
                    'osrm_coverage_warn':      False,
                })
                return result

        # ── 2. Try OpenRouteService (free fallback) ───────────────────────
        if prefer in ('auto', 'ors', 'osrm'):
            ors = _ors_query(lat1, lng1, lat2, lng2)
            if ors:
                raw_min = ors[1]
                adj_min = int(traffic_adjusted_duration(raw_min, apply_traffic))
                result.update({
                    'distance_miles':          ors[0],
                    'distance_km':             round(ors[0] * 1.60934, 2),
                    'duration_min':            adj_min,
                    'duration_min_no_traffic': int(raw_min),
                    'price_usd':               _compute_price(ors[0]),
                    'method':                  'ors',
                    'osrm_coverage_warn':      True,
                })
                logger.info("Used ORS fallback: %.1f mi", ors[0])
                return result

        # ── 3. Geodesic straight-line (last resort) ───────────────────────
        logger.warning(
            "All routing failed for (%.4f,%.4f)→(%.4f,%.4f). "
            "Using geodesic straight-line (underestimates road distance).",
            lat1, lng1, lat2, lng2
        )
        raw_min = _compute_duration(geodesic_miles)
        adj_min = int(traffic_adjusted_duration(raw_min, apply_traffic))
        result.update({
            'distance_miles':          geodesic_miles,
            'distance_km':             round(geodesic_km, 2),
            'duration_min':            adj_min,
            'duration_min_no_traffic': raw_min,
            'price_usd':               _compute_price(geodesic_miles),
            'method':                  'geodesic',
            'osrm_coverage_warn':      True,
        })
        return result

    except ValueError as ve:
        logger.error("Coordinate validation: %s", ve)
        result['error'] = str(ve)
    except Exception as exc:
        logger.error("Distance computation: %s", exc)
        result['error'] = str(exc)

    return result


def compare_methods(lat1, lng1, lat2, lng2):
    """Benchmark all methods for a coordinate pair."""
    _validate_coords(lat1, lng1, lat2, lng2)
    geo_km    = round(_geodesic_km(lat1, lng1, lat2, lng2), 4)
    geo_miles = round(geo_km * 0.621371, 4)
    hav_km    = round(_haversine_km(lat1, lng1, lat2, lng2), 4)

    osrm  = _osrm_query(lat1, lng1, lat2, lng2)
    ors   = _ors_query(lat1, lng1, lat2, lng2)

    osrm_valid = osrm and _validate_osrm(osrm[0], geo_miles, lat1, lng1, lat2, lng2)

    mult = _traffic_multiplier()
    return {
        'haversine_miles':         round(hav_km * 0.621371, 4),
        'geodesic_miles':          geo_miles,
        'osrm_miles':              osrm[0] if osrm_valid else None,
        'osrm_raw_miles':          osrm[0] if osrm else None,
        'osrm_valid':              osrm_valid,
        'ors_miles':               ors[0]  if ors  else None,
        'ors_duration_min':        ors[1]  if ors  else None,
        'traffic_multiplier':      mult,
        'traffic_level':           ('heavy' if mult>=1.4 else 'moderate' if mult>=1.2 else 'normal'),
        'recommended_method':      'osrm' if osrm_valid else ('ors' if ors else 'geodesic'),
        'price_usd':               _compute_price(
            osrm[0] if osrm_valid else (ors[0] if ors else geo_miles)
        ),
    }