"""
Truck/pricing_engine.py
========================
Advanced pricing engine for RiftValley Carriers quote calculator.

Factors:
  1. Vehicle class     — base fare + per-mile rate
  2. Distance          — from distance_engine (OSRM → ORS → geodesic)
  3. Fuel surcharge    — 8% of mileage cost
  4. Traffic           — live from distance_engine traffic_level
  5. Weather           — live from Open-Meteo API (free, no key)
  6. Time of day       — rush hour, off-peak, weekend
  7. Goods sensitivity — fragile, medical, artwork, perishable surcharges
  8. Long haul         — >200 miles discount
  9. Minimum fares     — per vehicle class floor
"""

import logging
import requests
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# ── Vehicle configurations ────────────────────────────────────────────────────

VEHICLE_CONFIG = {
    'small': {
        'name':          'Cargo Van',
        'subtitle':      'Up to 150 lbs',
        'base_fare':     35.00,
        'rate_per_mile': 2.50,
        'fuel_surcharge': 0.08,
        'min_fare':      75.00,
        'icon':          'fa-truck',
        'color':         '#2563EB',
    },
    'medium': {
        'name':          'Box Truck',
        'subtitle':      '150 lbs – 5 tons',
        'base_fare':     65.00,
        'rate_per_mile': 3.75,
        'fuel_surcharge': 0.08,
        'min_fare':      125.00,
        'icon':          'fa-truck-moving',
        'color':         '#059669',
    },
    'large': {
        'name':          'Semi-Truck',
        'subtitle':      '5 – 36 tons',
        'base_fare':     150.00,
        'rate_per_mile': 5.50,
        'fuel_surcharge': 0.08,
        'min_fare':      300.00,
        'icon':          'fa-trailer',
        'color':         '#D97706',
    },
}

# ── Goods sensitivity surcharges ──────────────────────────────────────────────

GOODS_SENSITIVITY = {
    'standard':   {'name': 'Standard Goods',    'surcharge': 0.00, 'icon': 'fa-box'},
    'fragile':    {'name': 'Fragile / Delicate', 'surcharge': 0.12, 'icon': 'fa-wine-glass-alt'},
    'medical':    {'name': 'Medical Supplies',   'surcharge': 0.18, 'icon': 'fa-pills'},
    'artwork':    {'name': 'Artwork / Antiques', 'surcharge': 0.20, 'icon': 'fa-palette'},
    'perishable': {'name': 'Perishables',        'surcharge': 0.15, 'icon': 'fa-thermometer-half'},
}

# ── Traffic multipliers ───────────────────────────────────────────────────────

TRAFFIC_MULTIPLIERS = {
    'heavy':    {'label': 'Heavy Traffic',    'multiplier': 1.35, 'color': '#DC2626'},
    'moderate': {'label': 'Moderate Traffic', 'multiplier': 1.15, 'color': '#D97706'},
    'normal':   {'label': 'Normal Traffic',   'multiplier': 1.00, 'color': '#16A34A'},
    'light':    {'label': 'Light Traffic',    'multiplier': 0.95, 'color': '#2563EB'},
}

# ── Weather conditions from WMO codes ────────────────────────────────────────
# Open-Meteo API returns WMO weather interpretation codes

WMO_TO_CONDITION = {
    0:              'clear',
    1: 'cloudy', 2: 'cloudy', 3: 'cloudy',
    45: 'fog', 48: 'fog',
    51: 'drizzle', 52: 'drizzle', 53: 'drizzle',
    61: 'rain',    62: 'rain',    63: 'rain',
    65: 'heavy_rain', 66: 'heavy_rain', 67: 'heavy_rain',
    71: 'snow', 72: 'snow', 73: 'snow', 74: 'snow', 75: 'snow', 77: 'snow',
    80: 'rain', 81: 'rain', 82: 'rain',
    85: 'snow', 86: 'snow',
    95: 'storm', 96: 'storm', 99: 'storm',
}

WEATHER_CONFIG = {
    'clear':      {'label': 'Clear',        'multiplier': 1.00, 'icon': 'fa-sun',                'color': '#16A34A'},
    'cloudy':     {'label': 'Cloudy',       'multiplier': 1.00, 'icon': 'fa-cloud',              'color': '#6B7280'},
    'fog':        {'label': 'Foggy',        'multiplier': 1.15, 'icon': 'fa-smog',               'color': '#6B7280'},
    'drizzle':    {'label': 'Drizzle',      'multiplier': 1.08, 'icon': 'fa-cloud-rain',         'color': '#2563EB'},
    'rain':       {'label': 'Rain',         'multiplier': 1.12, 'icon': 'fa-cloud-showers-heavy','color': '#1D4ED8'},
    'heavy_rain': {'label': 'Heavy Rain',   'multiplier': 1.20, 'icon': 'fa-cloud-showers-heavy','color': '#1E40AF'},
    'snow':       {'label': 'Snow',         'multiplier': 1.35, 'icon': 'fa-snowflake',          'color': '#7C3AED'},
    'storm':      {'label': 'Thunderstorm', 'multiplier': 1.25, 'icon': 'fa-bolt',               'color': '#DC2626'},
}


def get_weather_condition(lat: float, lng: float) -> str:
    """
    Fetches current weather condition from Open-Meteo API.
    Free, no API key required.
    Returns a condition string key (e.g. 'rain', 'clear', 'snow').
    Falls back to 'clear' on any error so quotes still work.
    """
    try:
        resp = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude':  lat,
                'longitude': lng,
                'current':   'weather_code,wind_speed_10m',
                'timezone':  'America/New_York',
            },
            timeout=4,
        )
        data    = resp.json()
        wmo     = data['current']['weather_code']
        condition = WMO_TO_CONDITION.get(int(wmo), 'clear')
        logger.debug("Weather at (%.4f, %.4f): WMO=%s → %s", lat, lng, wmo, condition)
        return condition
    except Exception as exc:
        logger.warning("Weather API failed (non-fatal): %s", exc)
        return 'clear'


def _get_time_factor() -> dict:
    """
    Computes time-of-day and day-of-week pricing factor.
    Eastern Time (Georgia is always ET).
    """
    et  = pytz.timezone('America/New_York')
    now = datetime.now(et)
    h   = now.hour
    dow = now.weekday()   # 0 = Monday

    if dow >= 5:           # Weekend
        return {'label': 'Weekend rate', 'multiplier': 1.08, 'color': '#D97706'}
    if (7 <= h < 9) or (16 <= h < 19):
        return {'label': 'Rush hour',    'multiplier': 1.20, 'color': '#DC2626'}
    if h >= 22 or h < 6:
        return {'label': 'Off-peak',     'multiplier': 0.95, 'color': '#2563EB'}
    return     {'label': 'Standard rate','multiplier': 1.00, 'color': '#16A34A'}


def compute_quote(
    p_lat: float, p_lng: float,
    d_lat: float, d_lng: float,
    vehicle_size: str = 'medium',
    goods_type:   str = 'standard',
) -> dict:
    """
    Full pricing calculation with all factors.

    Args:
        p_lat, p_lng   : Pickup coordinates
        d_lat, d_lng   : Delivery coordinates
        vehicle_size   : 'small' | 'medium' | 'large'
        goods_type     : 'standard' | 'fragile' | 'medical' | 'artwork' | 'perishable'

    Returns:
        dict with full price breakdown or {'error': str} on failure
    """
    from Truck.distance_engine import compute_distance

    # ── Distance + traffic from engine ────────────────────────────────
    dist = compute_distance(p_lat, p_lng, d_lat, d_lng)
    if dist.get('error'):
        return {'error': dist['error']}

    miles        = dist['distance_miles']
    duration_min = dist['duration_min']
    traffic_key  = dist.get('traffic_level', 'normal')

    # ── Vehicle ───────────────────────────────────────────────────────
    v = VEHICLE_CONFIG.get(vehicle_size, VEHICLE_CONFIG['medium'])

    # ── Base calculation ──────────────────────────────────────────────
    mileage_cost  = miles * v['rate_per_mile']
    fuel_amount   = mileage_cost * v['fuel_surcharge']
    base_subtotal = v['base_fare'] + mileage_cost + fuel_amount

    # ── Traffic ───────────────────────────────────────────────────────
    traffic_cfg  = TRAFFIC_MULTIPLIERS.get(traffic_key, TRAFFIC_MULTIPLIERS['normal'])
    after_traffic = base_subtotal * traffic_cfg['multiplier']
    traffic_adj   = after_traffic - base_subtotal

    # ── Weather ───────────────────────────────────────────────────────
    weather_key  = get_weather_condition(p_lat, p_lng)
    weather_cfg  = WEATHER_CONFIG.get(weather_key, WEATHER_CONFIG['clear'])
    after_weather = after_traffic * weather_cfg['multiplier']
    weather_adj   = after_weather - after_traffic

    # ── Time of day ───────────────────────────────────────────────────
    time_cfg     = _get_time_factor()
    after_time    = after_weather * time_cfg['multiplier']
    time_adj      = after_time - after_weather

    # ── Goods sensitivity ─────────────────────────────────────────────
    goods_cfg      = GOODS_SENSITIVITY.get(goods_type, GOODS_SENSITIVITY['standard'])
    goods_surcharge = after_time * goods_cfg['surcharge']
    after_goods    = after_time + goods_surcharge

    # ── Long haul discount ────────────────────────────────────────────
    long_haul_pct      = 0.05 if miles > 200 else 0.00
    long_haul_discount = after_goods * long_haul_pct
    subtotal           = after_goods - long_haul_discount

    # ── Minimum fare ─────────────────────────────────────────────────
    min_applied = subtotal < v['min_fare']
    total       = max(subtotal, v['min_fare'])
    total       = round(total, 2)

    # ── Validity window (quote valid 30 mins) ─────────────────────────
    from datetime import timedelta
    et      = pytz.timezone('America/New_York')
    now_et  = datetime.now(et)
    valid_until = (now_et + timedelta(minutes=30)).strftime('%I:%M %p ET')

    return {
        'success':         True,
        'distance_miles':  round(miles, 2),
        'duration_min':    duration_min,
        'route_method':    dist.get('method', 'calculated'),

        # Conditions
        'traffic_key':     traffic_key,
        'traffic_label':   traffic_cfg['label'],
        'traffic_color':   traffic_cfg['color'],
        'traffic_mult':    traffic_cfg['multiplier'],

        'weather_key':     weather_key,
        'weather_label':   weather_cfg['label'],
        'weather_icon':    weather_cfg['icon'],
        'weather_color':   weather_cfg['color'],
        'weather_mult':    weather_cfg['multiplier'],

        'time_label':      time_cfg['label'],
        'time_color':      time_cfg['color'],
        'time_mult':       time_cfg['multiplier'],

        'goods_label':     goods_cfg['name'],
        'goods_surcharge_pct': goods_cfg['surcharge'],

        'vehicle_name':    v['name'],
        'vehicle_size':    vehicle_size,

        # Price
        'price_usd':       total,
        'min_fare_applied': min_applied,
        'valid_until':     valid_until,

        # Full breakdown (all in USD)
        'breakdown': {
            'base_fare':        round(v['base_fare'], 2),
            'mileage_cost':     round(mileage_cost, 2),
            'fuel_surcharge':   round(fuel_amount, 2),
            'traffic_adj':      round(traffic_adj, 2),
            'weather_adj':      round(weather_adj, 2),
            'time_adj':         round(time_adj, 2),
            'goods_surcharge':  round(goods_surcharge, 2),
            'long_haul_disc':   round(-long_haul_discount, 2),
            'subtotal':         round(subtotal, 2),
            'min_fare':         v['min_fare'],
            'total':            total,
        },
    }


# ── Redis rate limiting ───────────────────────────────────────────────────────

def check_rate_limit(ip: str, limit: int = 30, window: int = 3600) -> tuple:
    """
    IP-based rate limiting using the existing Redis instance.
    Returns (allowed: bool, remaining: int, reset_in_seconds: int)
    """
    try:
        import redis as redis_lib
        import os
        r = redis_lib.Redis.from_url(
            os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
            decode_responses=True,
            socket_connect_timeout=2,
        )
        key   = f'ratelimit:quote:{ip}'
        count = r.incr(key)
        if count == 1:
            r.expire(key, window)
        ttl       = r.ttl(key)
        remaining = max(0, limit - count)
        return (count <= limit, remaining, max(0, ttl))
    except Exception as exc:
        logger.warning("Rate limit Redis error (allowing request): %s", exc)
        return (True, 30, 3600)   # fail open — don't break quotes if Redis hiccups


def get_client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '0.0.0.0')