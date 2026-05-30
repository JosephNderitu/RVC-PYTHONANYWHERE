"""
Truck/geofencing/state_machine.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Jitter-dampening geofence state machine.

THE JITTER PROBLEM
───────────────────
Even after EMA smoothing, GPS coordinates still have ±3–8 metre
residual noise. A courier standing exactly on a zone boundary
would trigger ENTER and EXIT events in rapid alternation as each
GPS reading oscillates across the boundary. This is called the
"boundary oscillation" problem and makes geofence events useless
for notifications and automation.

THE SOLUTION: CONSECUTIVE THRESHOLD
─────────────────────────────────────
Fire ENTER only after X consecutive GPS readings confirm the
courier is inside the zone. Fire EXIT only after X consecutive
readings confirm they are outside.

With a 5-second GPS interval and threshold=3:
  - ENTER fires after 15 seconds of stable inside readings
  - EXIT fires after 15 seconds of stable outside readings
  - A brief boundary crossing (< 15 seconds) is ignored

THREE STATES
─────────────
    OUTSIDE ──[X inside readings]──► DWELL ──[X inside readings]──► INSIDE
       ▲                                │                              │
       │                     [outside reading]                        │
       │                                ▼                             │
       └──────────────[X outside readings]──────────────────────────┘

    OUTSIDE: Courier is confirmed outside the zone.
             Transitions to DWELL on first inside reading.

    DWELL:   Courier may be entering — accumulating consecutive
             inside readings. Transitions back to OUTSIDE immediately
             on any outside reading (the potential entry was jitter).
             Transitions to INSIDE once threshold is reached.

    INSIDE:  Courier is confirmed inside the zone.
             Transitions to OUTSIDE once X consecutive outside
             readings are accumulated (allowing brief excursions).

PURE FUNCTION DESIGN
─────────────────────
The state machine is implemented as a pure function so it can be
called from a Celery task without any in-process state. The full
state (state, consecutive_inside, consecutive_outside) is read
from and written back to the CourierZoneState database row by
the evaluator — not stored in memory.

This means the state machine correctly handles:
  - Celery worker restarts mid-job
  - Multiple Celery workers processing the same courier
  - System restarts without losing zone context
"""

from typing import Optional, Tuple

# ── Constants ─────────────────────────────────────────────────────────────────
# Number of consecutive GPS readings required to confirm a zone transition.
# Increase to reduce sensitivity; decrease for faster response.
# At 5-second GPS intervals: threshold=3 → 15-second confirmation window.
ENTER_THRESHOLD: int = 3
EXIT_THRESHOLD:  int = 3

# State constants — must match CourierZoneState.STATE_CHOICES in models.py
OUTSIDE = 'outside'
DWELL   = 'dwell'
INSIDE  = 'inside'


def process_reading(
    is_inside:           bool,
    current_state:       str,
    consecutive_inside:  int,
    consecutive_outside: int,
) -> Tuple[str, int, int, Optional[str]]:
    """
    Process one GPS reading for one zone and return the new state.

    This is a pure function — no side effects, no DB access.
    The evaluator is responsible for reading the current state from
    CourierZoneState and writing the returned values back.

    Args:
        is_inside:           True if the smoothed GPS point is inside the polygon
        current_state:       One of OUTSIDE / DWELL / INSIDE
        consecutive_inside:  How many consecutive inside readings so far
        consecutive_outside: How many consecutive outside readings so far

    Returns:
        (new_state, new_consecutive_inside, new_consecutive_outside, event)

        event is:
            'enter'  — courier has crossed into the zone (threshold confirmed)
            'exit'   — courier has crossed out of the zone (threshold confirmed)
            None     — no state change event (still accumulating)
    """
    if is_inside:
        consecutive_inside  += 1
        consecutive_outside  = 0   # reset exit counter — they're back inside

        if current_state == OUTSIDE:
            if consecutive_inside >= ENTER_THRESHOLD:
                # Enough consecutive inside readings — confirmed ENTER
                return INSIDE, consecutive_inside, consecutive_outside, 'enter'
            else:
                # Start accumulating — move to DWELL
                return DWELL, consecutive_inside, consecutive_outside, None

        elif current_state == DWELL:
            if consecutive_inside >= ENTER_THRESHOLD:
                # Crossed the threshold while dwelling — fire ENTER
                return INSIDE, consecutive_inside, consecutive_outside, 'enter'
            else:
                # Still accumulating — stay in DWELL
                return DWELL, consecutive_inside, consecutive_outside, None

        else:  # current_state == INSIDE
            # Already confirmed inside — no new event
            return INSIDE, consecutive_inside, consecutive_outside, None

    else:  # not inside
        consecutive_outside += 1
        consecutive_inside   = 0   # reset entry counter

        if current_state == INSIDE:
            if consecutive_outside >= EXIT_THRESHOLD:
                # Enough consecutive outside readings — confirmed EXIT
                return OUTSIDE, consecutive_inside, consecutive_outside, 'exit'
            else:
                # Brief excursion — stay INSIDE, wait for exit confirmation
                return INSIDE, consecutive_inside, consecutive_outside, None

        elif current_state == DWELL:
            # Was accumulating entry readings — outside reading resets it
            # This is a jitter false alarm — go straight back to OUTSIDE
            return OUTSIDE, consecutive_inside, consecutive_outside, None

        else:  # current_state == OUTSIDE
            # Already confirmed outside — no event
            return OUTSIDE, consecutive_inside, consecutive_outside, None