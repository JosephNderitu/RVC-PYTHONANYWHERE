import math
import logging
import requests
from datetime import datetime
from geopy.distance import geodesic as geopy_geodesic
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Routing constants (not pricing) ──────────────────────────────────────────
AVG_SPEED_LOCAL_MPH   = 45.0
AVG_SPEED_HIGHWAY_MPH = 62.0
METERS_PER_MILE       = 1609.344

# ── OSRM validation thresholds ────────────────────────────────────────────────
OSRM_MIN_RATIO = 0.85   # reject if OSRM < 85% of straight-line
OSRM_MAX_RATIO = 3.0    # reject if OSRM > 3x straight-line

# ── ORS endpoint ──────────────────────────────────────────────────────────────
ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"


# ═══════════════════════════════════════════════════════════════════════════════
#   PRICING — single source of truth is pricing_engine.VEHICLE_CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

def _load_vehicle_config() -> dict:
    """
    Load vehicle pricing config from pricing_engine.
    Provides a safe inline fallback in case of import issues during
    migrations or initial setup, so the engine never hard-crashes.
    """
    try:
        from Truck.pricing_engine import VEHICLE_CONFIG
        return VEHICLE_CONFIG
    except ImportError:
        logger.warning(
            "Could not import VEHICLE_CONFIG from pricing_engine — "
            "using inline defaults. Deploy pricing_engine.py to fix this."
        )
        return {
            'small':  {
                'name': 'Cargo Van',
                'base_fare': 35.00, 'rate_per_mile': 2.50,
                'fuel_surcharge': 0.08, 'min_fare': 75.00,
            },
            'medium': {
                'name': 'Box Truck',
                'base_fare': 65.00, 'rate_per_mile': 3.75,
                'fuel_surcharge': 0.08, 'min_fare': 125.00,
            },
            'large':  {
                'name': 'Semi-Truck',
                'base_fare': 150.00, 'rate_per_mile': 5.50,
                'fuel_surcharge': 0.08, 'min_fare': 300.00,
            },
        }


def _compute_price(distance_miles: float, vehicle_size: str = 'medium') -> float:
    """
    Compute the base delivery price for a given distance and vehicle class.

    Formula:
      mileage_cost   = distance_miles x rate_per_mile
      fuel_surcharge = mileage_cost   x fuel_surcharge_pct  (8%)
      total          = base_fare + mileage_cost + fuel_surcharge
      final          = max(total, min_fare)

    Rates come from pricing_engine.VEHICLE_CONFIG.
    This function intentionally does NOT apply weather / time-of-day /
    goods multipliers — those are quote-page estimates only.
    The job price is the stable base price.
    """
    vc = _load_vehicle_config()
    v  = vc.get(vehicle_size) or vc.get('medium')
    mileage_cost   = distance_miles * v['rate_per_mile']
    fuel_surcharge = mileage_cost   * v['fuel_surcharge']
    subtotal       = v['base_fare'] + mileage_cost + fuel_surcharge
    return round(max(subtotal, v['min_fare']), 2)


def _compute_duration(distance_miles: float) -> int:
    """
    Estimate drive time in minutes from distance.
    Uses highway speed for routes over 50 miles, local speed otherwise.
    Returns at least 15 minutes for any route.
    """
    speed = AVG_SPEED_HIGHWAY_MPH if distance_miles > 50 else AVG_SPEED_LOCAL_MPH
    return max(15, int((distance_miles / speed) * 60))


def get_vehicle_display(vehicle_size: str) -> str:
    """Return the human-readable vehicle name for a given size key."""
    vc = _load_vehicle_config()
    return vc.get(vehicle_size, vc.get('medium', {})).get('name', vehicle_size.title())


# ═══════════════════════════════════════════════════════════════════════════════
#   COORDINATE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_coords(lat1: float, lng1: float, lat2: float, lng2: float) -> None:
    """
    Validates that all coordinates fall within US bounding box.
    US longitudes are always NEGATIVE — a common bug is passing positive values.
    Raises ValueError with a clear message on failure.
    """
    for lat in (lat1, lat2):
        if not (24.0 <= lat <= 50.0):
            raise ValueError(f"Latitude {lat} out of US range (24-50).")
    for lng in (lng1, lng2):
        if not (-130.0 <= lng <= -65.0):
            raise ValueError(
                f"Longitude {lng} out of US range (-130 to -65). "
                f"US longitudes are NEGATIVE. Got {lng}."
            )


# ═══════════════════════════════════════════════════════════════════════════════
#   STRAIGHT-LINE DISTANCE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine great-circle distance in km (fast, slightly less accurate)."""
    R     = 6371.0
    phi1  = math.radians(lat1)
    phi2  = math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlmbd = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlmbd / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _geodesic_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Karney geodesic distance in km (most accurate straight-line)."""
    return geopy_geodesic((lat1, lng1), (lat2, lng2)).km


# ═══════════════════════════════════════════════════════════════════════════════
#   TRAFFIC — TIME OF DAY MULTIPLIER
#   Built-in heuristic for US Eastern timezone rush-hour patterns.
#   Used when no external traffic API is configured.
# ═══════════════════════════════════════════════════════════════════════════════

def _traffic_multiplier() -> float:
    """
    Returns a duration multiplier based on current time in Eastern Time.
    No API key required.

      Morning rush  7-9am:    +35%  (x1.35)
      Lunch         11am-1pm: +15%  (x1.15)
      Evening rush  4-6pm:    +45%  (x1.45)
      Night         10pm-5am: -10%  (x0.90)
      Weekend:                +10%  (x1.10)
      Normal daytime:          x1.00
    """
    try:
        import pytz
        tz  = pytz.timezone('America/New_York')
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()

    hour    = now.hour
    weekday = now.weekday()   # 0 = Monday, 6 = Sunday

    if weekday >= 5:
        return 1.10
    if 7 <= hour <= 9:
        return 1.35
    if 16 <= hour <= 18:
        return 1.45
    if 11 <= hour <= 13:
        return 1.15
    if hour >= 22 or hour <= 5:
        return 0.90
    return 1.00


def traffic_adjusted_duration(base_minutes: float, apply_traffic: bool = True) -> float:
    """
    Apply time-of-day traffic multiplier to a raw drive time.
    Pass apply_traffic=False to return the raw routing duration unchanged.
    """
    if not apply_traffic:
        return base_minutes
    return round(base_minutes * _traffic_multiplier(), 1)


# ═══════════════════════════════════════════════════════════════════════════════
#   ROUTER 1 — OSRM  (self-hosted, southeastern US)
# ═══════════════════════════════════════════════════════════════════════════════

def _osrm_query(lat1: float, lng1: float,
                lat2: float, lng2: float) -> tuple | None:
    """
    Road route via self-hosted OSRM container.
    OSRM coordinate convention: longitude first, then latitude.
    Returns (distance_miles, duration_minutes) or None on any failure.
    """
    osrm_base = getattr(settings, 'OSRM_BASE_URL', None)
    if not osrm_base:
        logger.debug("OSRM_BASE_URL not set in settings — skipping OSRM.")
        return None

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
            logger.warning("OSRM non-Ok response: %s", data.get('code'))
            return None

        dist_miles  = round(data['routes'][0]['distance'] / METERS_PER_MILE, 2)
        dur_minutes = round(data['routes'][0]['duration'] / 60, 1)
        logger.info("OSRM: %.2f mi, %.1f min", dist_miles, dur_minutes)
        return dist_miles, dur_minutes

    except requests.exceptions.Timeout:
        logger.warning("OSRM timed out after 5s.")
    except requests.exceptions.ConnectionError:
        logger.warning("OSRM connection refused — container may be down.")
    except Exception as exc:
        logger.warning("OSRM unexpected error: %s", exc)
    return None


def _validate_osrm(osrm_miles: float, geodesic_miles: float,
                   lat1: float, lng1: float,
                   lat2: float, lng2: float) -> bool:
    """
    Returns True if the OSRM result is plausible relative to straight-line.

    Rejects results where OSRM road distance is:
      - Less than 85% of geodesic: indicates OSRM snapped to coverage boundary
      - More than 3x geodesic: indicates a routing bug or wrong continent
    """
    if geodesic_miles < 0.1:
        return True   # same-block routes — ratio check not meaningful

    ratio = osrm_miles / geodesic_miles

    if ratio < OSRM_MIN_RATIO:
        logger.error(
            "OSRM COVERAGE MISS: %.1f mi is only %.0f%% of geodesic %.1f mi "
            "for (%.4f,%.4f)->(%.4f,%.4f). Falling back to ORS.",
            osrm_miles, ratio * 100, geodesic_miles,
            lat1, lng1, lat2, lng2,
        )
        return False

    if ratio > OSRM_MAX_RATIO:
        logger.warning(
            "OSRM returned %.1fx geodesic (%.1f mi vs %.1f mi) — discarding.",
            ratio, osrm_miles, geodesic_miles,
        )
        return False

    return True

def _ors_query(lat1: float, lng1: float,
               lat2: float, lng2: float) -> tuple | None:
    """
    Road route via OpenRouteService (free global fallback).
    ORS uses speed-limit-aware routing — durations are realistic.
    ORS coordinate convention: [longitude, latitude].
    Returns (distance_miles, duration_minutes) or None.
    """
    ors_key = getattr(settings, 'ORS_API_KEY', None)
    if not ors_key:
        logger.debug("ORS_API_KEY not configured — skipping ORS fallback.")
        return None

    headers = {
        'Authorization': ors_key,
        'Content-Type':  'application/json',
    }
    body = {
        "coordinates": [[lng1, lat1], [lng2, lat2]],
        "profile":     "driving-car",
        "format":      "json",
        "units":       "mi",
        "geometry":    False,
        "instructions": False,
    }

    try:
        resp = requests.post(ORS_BASE_URL, json=body, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        summary     = data['routes'][0]['summary']
        dist_miles  = round(summary['distance'], 2)     # already in miles (units=mi)
        dur_minutes = round(summary['duration'] / 60, 1)

        logger.info("ORS fallback: %.2f mi, %.1f min", dist_miles, dur_minutes)
        return dist_miles, dur_minutes

    except requests.exceptions.Timeout:
        logger.warning("ORS timed out after 8s.")
    except requests.exceptions.ConnectionError:
        logger.warning("ORS connection error.")
    except (KeyError, IndexError) as exc:
        logger.warning("ORS response parse error: %s", exc)
    except Exception as exc:
        logger.warning("ORS unexpected error: %s", exc)
    return None


def _ors_route_geometry(lat1: float, lng1: float,
                        lat2: float, lng2: float) -> list | None:
    """
    Fetch full GeoJSON route geometry from ORS for drawing on Leaflet.
    Returns list of [lat, lng] pairs (Leaflet convention) or None.
    Used by the frontend OSRM/ORS proxy views for the route polyline.
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
        "profile":     "driving-car",
        "format":      "geojson",
        "units":       "mi",
        "instructions": False,
    }

    try:
        resp = requests.post(ORS_BASE_URL, json=body, headers=headers, timeout=8)
        resp.raise_for_status()
        data   = resp.json()
        coords = data['features'][0]['geometry']['coordinates']
        # GeoJSON returns [lng, lat] — swap to Leaflet [lat, lng]
        return [[c[1], c[0]] for c in coords]
    except Exception as exc:
        logger.warning("ORS geometry fetch failed: %s", exc)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#   MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def compute_distance(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
    prefer: str          = 'auto',
    apply_traffic: bool  = True,
    vehicle_size: str    = 'medium',
) -> dict:
    result = {
        'distance_miles':          0.0,
        'distance_km':             0.0,
        'duration_min':            0,
        'duration_min_no_traffic': 0,
        'price_usd':               0.0,
        'vehicle_size':            vehicle_size,
        'method':                  'unknown',
        'traffic_level':           'normal',
        'traffic_multiplier':      1.0,
        'osrm_coverage_warn':      False,
        'error':                   None,
    }

    try:
        _validate_coords(lat1, lng1, lat2, lng2)

        geodesic_km    = _geodesic_km(lat1, lng1, lat2, lng2)
        geodesic_miles = round(geodesic_km * 0.621371, 2)

        # Traffic level assessed once — used by all three routing paths
        multiplier = _traffic_multiplier()
        result['traffic_multiplier'] = multiplier
        result['traffic_level'] = (
            'heavy'    if multiplier >= 1.40 else
            'moderate' if multiplier >= 1.20 else
            'light'    if multiplier <= 0.95 else
            'normal'
        )

        # ── 1. OSRM ───────────────────────────────────────────────────────
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
                    'price_usd':               _compute_price(osrm[0], vehicle_size),
                    'method':                  'osrm',
                    'osrm_coverage_warn':      False,
                })
                return result

        # ── 2. ORS ────────────────────────────────────────────────────────
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
                    'price_usd':               _compute_price(ors[0], vehicle_size),
                    'method':                  'ors',
                    'osrm_coverage_warn':      True,
                })
                logger.info("Used ORS fallback: %.1f mi", ors[0])
                return result

        # ── 3. Geodesic straight-line (last resort) ───────────────────────
        logger.warning(
            "All routing failed for (%.4f,%.4f)->(%.4f,%.4f). "
            "Using geodesic straight-line — underestimates road distance.",
            lat1, lng1, lat2, lng2,
        )
        raw_min = _compute_duration(geodesic_miles)
        adj_min = int(traffic_adjusted_duration(raw_min, apply_traffic))
        result.update({
            'distance_miles':          geodesic_miles,
            'distance_km':             round(geodesic_km, 2),
            'duration_min':            adj_min,
            'duration_min_no_traffic': raw_min,
            'price_usd':               _compute_price(geodesic_miles, vehicle_size),
            'method':                  'geodesic',
            'osrm_coverage_warn':      True,
        })
        return result

    except ValueError as ve:
        logger.error("Coordinate validation failed: %s", ve)
        result['error'] = str(ve)
    except Exception as exc:
        logger.error("Distance computation failed: %s", exc, exc_info=True)
        result['error'] = str(exc)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#   BENCHMARKING UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

def compare_methods(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
    vehicle_size: str = 'medium',
) -> dict:
    _validate_coords(lat1, lng1, lat2, lng2)

    geo_km    = round(_geodesic_km(lat1, lng1, lat2, lng2), 4)
    geo_miles = round(geo_km * 0.621371, 4)
    hav_km    = round(_haversine_km(lat1, lng1, lat2, lng2), 4)

    osrm       = _osrm_query(lat1, lng1, lat2, lng2)
    ors        = _ors_query(lat1, lng1, lat2, lng2)
    osrm_valid = bool(osrm and _validate_osrm(osrm[0], geo_miles, lat1, lng1, lat2, lng2))

    mult      = _traffic_multiplier()
    best_dist = osrm[0] if osrm_valid else (ors[0] if ors else geo_miles)

    return {
        'haversine_miles':      round(hav_km * 0.621371, 4),
        'geodesic_miles':       geo_miles,
        'osrm_miles':           osrm[0] if osrm_valid else None,
        'osrm_raw_miles':       osrm[0] if osrm else None,
        'osrm_valid':           osrm_valid,
        'ors_miles':            ors[0]  if ors else None,
        'ors_duration_min':     ors[1]  if ors else None,
        'traffic_multiplier':   mult,
        'traffic_level':        (
            'heavy'    if mult >= 1.4  else
            'moderate' if mult >= 1.2  else
            'light'    if mult <= 0.95 else
            'normal'
        ),
        'recommended_method':   'osrm' if osrm_valid else ('ors' if ors else 'geodesic'),
        'price_usd':            _compute_price(best_dist, vehicle_size),
        'vehicle_size':         vehicle_size,
        'vehicle_name':         get_vehicle_display(vehicle_size),
    }