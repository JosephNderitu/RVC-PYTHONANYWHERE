"""
Truck/geofencing/__init__.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RVC Geofencing Engine — public API

The single function you call from outside this package is:

    from Truck.geofencing import evaluate_courier_position

    evaluate_courier_position(courier, raw_lat, raw_lng)

Everything else (smoothing, PiP, state machine) is internal.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from .evaluator import evaluate_courier_position

__all__ = ["evaluate_courier_position"]