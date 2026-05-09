"""
Truck/geofencing/smoothing.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Exponential Moving Average (EMA) GPS smoother.

WHY GPS SMOOTHING IS NECESSARY
───────────────────────────────
Raw GPS coordinates from a mobile device have ±5 to ±15 metre
jitter even when the device is stationary. Without smoothing,
a courier standing exactly on a zone boundary would trigger
ENTER and EXIT events repeatedly as the raw coordinate oscillates
across the boundary.

EMA applies weighted averaging: recent readings matter more than
older ones, controlled by alpha (0.0–1.0).

    smoothed = alpha * raw + (1 - alpha) * previous_smoothed

alpha = 0.3 means:
  - 30% of the new reading is accepted
  - 70% of the previous smoothed value is retained
  - Higher alpha → more responsive, less smooth
  - Lower alpha → smoother, more lag

WHY STATELESS DESIGN
─────────────────────
The smoother is implemented as a pure classmethod — it does not
store state in a Python object. The previous smoothed lat/lng
values live in the Courier model (courier.smoothed_lat,
courier.smoothed_lng), which persists across Celery task
invocations, web server restarts, and container restarts.

This is critical for a Celery-based architecture: each task
invocation is independent and cannot rely on in-process state.
"""


class ExponentialSmoother:
    """
    Stateless EMA smoother. State (previous smoothed position)
    is stored in the Courier model and passed in by the caller.
    """

    ALPHA: float = 0.3   # weighting for the new reading

    @classmethod
    def smooth(
        cls,
        raw_lat: float,
        raw_lng: float,
        prev_smoothed_lat: float | None,
        prev_smoothed_lng: float | None,
    ) -> tuple[float, float]:
        """
        Apply one step of EMA smoothing.

        Args:
            raw_lat:           Raw GPS latitude from the device
            raw_lng:           Raw GPS longitude from the device
            prev_smoothed_lat: Previous smoothed latitude (from Courier model)
            prev_smoothed_lng: Previous smoothed longitude (from Courier model)

        Returns:
            (smoothed_lat, smoothed_lng) — the new smoothed position

        On the first update (no prior value), the raw coordinate is
        returned unchanged so the courier's initial position is
        captured accurately.
        """
        if prev_smoothed_lat is None or prev_smoothed_lng is None:
            # First GPS update for this courier — accept raw value directly
            return raw_lat, raw_lng

        smoothed_lat = cls.ALPHA * raw_lat + (1.0 - cls.ALPHA) * prev_smoothed_lat
        smoothed_lng = cls.ALPHA * raw_lng + (1.0 - cls.ALPHA) * prev_smoothed_lng

        return smoothed_lat, smoothed_lng