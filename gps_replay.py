#!/usr/bin/env python3
"""
gps_replay.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RVC GPS Simulation Script — Kenya → Georgia USA

Simulates a courier driving a Georgia road route from your Nairobi
laptop. Extracts real road coordinates from your running OSRM
container, saves them as JSON, then replays them to the courier
location API at controlled speed.

The system cannot distinguish this from a real courier's phone.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUICKSTART
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1 — Extract all routes from OSRM (run once):
    python gps_replay.py --extract

Step 2 — List available routes:
    python gps_replay.py --list

Step 3 — Replay a route:
    python gps_replay.py \\
        --route atlanta_savannah \\
        --speed 10 \\
        --username courier@rvc.com \\
        --password yourpassword \\
        --job-id 1

Step 4 — Geofence demo (slow, pauses before zone):
    python gps_replay.py \\
        --route atlanta_marietta \\
        --speed 2 \\
        --pause-at 120 \\
        --username courier@rvc.com \\
        --password yourpassword \\
        --job-id 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPEED GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Atlanta → Savannah has ~900 coordinate pairs.
Sleep interval = 0.5 / speed seconds per coordinate.

  speed=1   → ~450s  (7.5 min) — realistic real-time
  speed=2   → ~225s  (3.7 min) — good for geofence focus demo
  speed=5   → ~90s   (1.5 min) — recommended for full demo
  speed=10  → ~45s              — quick walkthrough
  speed=30  → ~15s              — stress test only

Atlanta → Marietta has ~200 coordinate pairs.
  speed=2   → ~50s   — perfect for geofence demo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRESENTATION SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open 3 browser tabs before starting the script:
  Tab 1: http://localhost:8000/customer/jobs/{job_id}/
          Customer tracking map — watch courier marker move
  Tab 2: http://localhost:8000/admin/Truck/geofenceevent/
          Django admin — watch GeofenceEvent rows appear live
  Tab 3: http://localhost:8000/admin/Truck/courierlocationhistory/
          Confirm GPS history is being logged

Run the script in PowerShell — panelists see the marker move in Tab 1,
and GeofenceEvent rows appear in Tab 2 when crossing zone boundaries.
"""

import argparse
import json
import os
import sys
import time
import requests
from pathlib import Path
from typing import Optional

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_URL  = "http://localhost:8000"
OSRM_URL  = "http://localhost:5000"
ROUTES_DIR = Path(__file__).parent / "routes"

# ── Predefined routes ──────────────────────────────────────────────────────────
# Coordinates are (longitude, latitude) — OSRM convention
ROUTE_DEFINITIONS = {
    "atlanta_savannah": {
        "from_lng":    -84.3880,
        "from_lat":     33.7490,
        "to_lng":      -81.0998,
        "to_lat":       32.0835,
        "description": "Atlanta CBD → Savannah, GA  (~248 miles via I-16)",
        "demo_notes":  "Full route demo. Use speed=5 for ~90 second playback.",
    },
    "atlanta_marietta": {
        "from_lng":    -84.3880,
        "from_lat":     33.7490,
        "to_lng":      -84.5494,
        "to_lat":       33.9526,
        "description": "Atlanta CBD → Marietta, GA  (~20 miles, quick demo)",
        "demo_notes":  "Quick demo. Use speed=2 for ~50 second playback. Good for geofence crossing demo.",
    },
    "atlanta_athens": {
        "from_lng":    -84.3880,
        "from_lat":     33.7490,
        "to_lng":      -83.3576,
        "to_lat":       33.9519,
        "description": "Atlanta CBD → Athens, GA  (~70 miles via US-78)",
        "demo_notes":  "Medium route. Use speed=3 for ~90 second playback.",
    },
    "savannah_brunswick": {
        "from_lng":    -81.0998,
        "from_lat":     32.0835,
        "to_lng":      -81.4915,
        "to_lat":       31.1499,
        "description": "Savannah → Brunswick, GA  (~70 miles via I-95)",
        "demo_notes":  "Coastal route. Good for demonstrating geofencing near Savannah delivery zone.",
    },
}

# ── ANSI colours for terminal output ──────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
CLEAR  = "\r\033[K"   # carriage return + clear line


def cprint(colour: str, msg: str, end: str = "\n"):
    print(f"{colour}{msg}{RESET}", end=end)


# ═══════════════════════════════════════════════════════════
#  ROUTE EXTRACTION
# ═══════════════════════════════════════════════════════════

def extract_route(route_name: str) -> list[tuple[float, float]]:
    """
    Query OSRM for full road geometry and save coordinates to JSON.

    Returns list of (lat, lng) tuples following the actual road.
    """
    if route_name not in ROUTE_DEFINITIONS:
        cprint(RED, f"Unknown route: {route_name}")
        cprint(YELLOW, f"Available routes: {', '.join(ROUTE_DEFINITIONS.keys())}")
        sys.exit(1)

    defn = ROUTE_DEFINITIONS[route_name]
    url  = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{defn['from_lng']},{defn['from_lat']};"
        f"{defn['to_lng']},{defn['to_lat']}"
        f"?overview=full&geometries=geojson"
    )

    cprint(BLUE, f"\n  Extracting '{route_name}' from OSRM...")
    cprint(CYAN, f"  URL: {url}")

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        cprint(RED, "\n  ERROR: Cannot connect to OSRM at http://localhost:5000")
        cprint(YELLOW, "  Make sure Docker is running: docker compose up -d")
        sys.exit(1)
    except Exception as e:
        cprint(RED, f"\n  ERROR: OSRM request failed: {e}")
        sys.exit(1)

    if data.get("code") != "Ok":
        cprint(RED, f"\n  ERROR: OSRM returned code '{data.get('code')}'")
        cprint(YELLOW, f"  Full response: {json.dumps(data, indent=2)[:400]}")
        sys.exit(1)

    # OSRM GeoJSON returns [lng, lat] pairs — swap to [lat, lng] for our API
    raw_coords = data["routes"][0]["geometry"]["coordinates"]
    coords = [(lat, lng) for lng, lat in raw_coords]

    distance_m = data["routes"][0]["distance"]
    duration_s = data["routes"][0]["duration"]
    distance_miles = distance_m / 1609.344

    cprint(GREEN, f"  ✓ {len(coords)} coordinate pairs extracted")
    cprint(GREEN, f"  ✓ Distance:  {distance_miles:.2f} miles  ({distance_m/1000:.1f} km)")
    cprint(GREEN, f"  ✓ Duration:  {int(duration_s//3600)}h {int((duration_s%3600)//60)}m (real-time)")

    # Save to JSON
    ROUTES_DIR.mkdir(exist_ok=True)
    route_file = ROUTES_DIR / f"{route_name}.json"
    payload = {
        "route_name":    route_name,
        "description":  defn["description"],
        "distance_miles": round(distance_miles, 2),
        "duration_min":   round(duration_s / 60, 1),
        "coord_count":   len(coords),
        "coordinates":   coords,   # list of [lat, lng]
    }
    route_file.write_text(json.dumps(payload, indent=2))
    cprint(GREEN, f"  ✓ Saved to {route_file}")

    return coords


def extract_all_routes():
    """Extract all defined routes from OSRM and save to the routes/ folder."""
    cprint(BOLD, "\n━━━ RVC GPS Route Extraction ━━━")
    cprint(CYAN, f"  OSRM: {OSRM_URL}")
    cprint(CYAN, f"  Output: {ROUTES_DIR}/\n")

    for name in ROUTE_DEFINITIONS:
        extract_route(name)

    cprint(BOLD + GREEN, "\n✓ All routes extracted successfully.")
    cprint(YELLOW, "\nTo replay a route:")
    cprint(CYAN,   "  python gps_replay.py --route atlanta_savannah --speed 5 \\")
    cprint(CYAN,   "      --username courier@rvc.com --password yourpassword --job-id 1")


# ═══════════════════════════════════════════════════════════
#  AUTHENTICATION
# ═══════════════════════════════════════════════════════════

def login(session: requests.Session, username: str, password: str) -> bool:
    """
    Log in to the Django application and populate session cookie.

    Uses the standard sign_in form endpoint. The session cookie
    is automatically stored in the requests.Session and sent
    with all subsequent requests.
    """
    sign_in_url = f"{BASE_URL}/sign_in/"

    # Step 1: GET the login page to obtain CSRF token from cookie
    try:
        resp = session.get(sign_in_url, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        cprint(RED, f"\n  ERROR: Cannot connect to Django at {BASE_URL}")
        cprint(YELLOW, "  Make sure Docker is running: docker compose up -d")
        sys.exit(1)

    # Extract CSRF token from cookies (Django sets csrftoken cookie on GET)
    csrf_token = session.cookies.get('csrftoken') or session.cookies.get('rvc_csrftoken')
    if not csrf_token:
        # Try to extract from the HTML form as fallback
        import re
        match = re.search(r'csrfmiddlewaretoken.*?value=["\']([^"\']+)["\']', resp.text)
        csrf_token = match.group(1) if match else ''

    # Step 2: POST credentials
    resp = session.post(
        sign_in_url,
        data={
            'username':          username,
            'password':          password,
            'csrfmiddlewaretoken': csrf_token,
        },
        headers={'Referer': sign_in_url},
        timeout=10,
        allow_redirects=True,
    )

    # Check if login succeeded — Django redirects to / or next page on success
    # A failed login stays on /sign_in/ or shows error
    if resp.url.endswith('/sign_in/') and 'error' in resp.text.lower():
        return False

    # Verify we have a session cookie
    session_cookie = (
        session.cookies.get('rvc_sessionid')      # custom session name from settings.py
        or session.cookies.get('sessionid')        # default Django session name
    )
    return bool(session_cookie)


# ═══════════════════════════════════════════════════════════
#  GPS REPLAY
# ═══════════════════════════════════════════════════════════

def load_route(route_name: str) -> dict:
    """Load route from saved JSON file. Extract from OSRM if not found."""
    route_file = ROUTES_DIR / f"{route_name}.json"

    if not route_file.exists():
        cprint(YELLOW, f"\n  Route '{route_name}' not found in {ROUTES_DIR}/")
        cprint(CYAN,   "  Extracting from OSRM now...")
        extract_route(route_name)

    return json.loads(route_file.read_text())


def replay_route(
    session:      requests.Session,
    route_name:   str,
    speed:        float,
    job_id:       Optional[int],
    pause_at:     Optional[int],
    start_from:   int,
):
    """
    Replay a saved route by POSTing each coordinate to the GPS update API.

    Args:
        session:    Authenticated requests.Session
        route_name: Route key (e.g. 'atlanta_savannah')
        speed:      Time compression multiplier (1=realtime, 10=10x faster)
        job_id:     Django Job ID to attach the GPS updates to (optional display)
        pause_at:   Coordinate index at which to pause and wait for keypress
        start_from: Coordinate index to start from (skip beginning)
    """
    route_data  = load_route(route_name)
    coords      = route_data["coordinates"]  # list of [lat, lng]
    total       = len(coords)
    interval    = 0.5 / speed   # seconds between updates

    update_url  = f"{BASE_URL}/courier/api/courier-location/update/"
    csrf_token  = session.cookies.get('csrftoken') or session.cookies.get('rvc_csrftoken') or ''

    cprint(BOLD, f"\n━━━ RVC GPS Replay ━━━")
    cprint(CYAN,   f"  Route:      {route_data['description']}")
    cprint(CYAN,   f"  Distance:   {route_data['distance_miles']} miles")
    cprint(CYAN,   f"  Coords:     {total} points  (starting from #{start_from})")
    cprint(CYAN,   f"  Speed:      {speed}x  (interval: {interval:.3f}s per point)")
    if job_id:
        cprint(CYAN, f"  Job ID:     {job_id}")
    if pause_at:
        cprint(YELLOW, f"  ⏸  Will pause at coordinate #{pause_at}")
    cprint(CYAN,   f"  Endpoint:   {update_url}")
    cprint(BLUE,   f"\n  Press Ctrl+C at any time to stop.\n")

    success_count = 0
    error_count   = 0
    paused        = False
    start_time    = time.time()

    coords_to_replay = coords[start_from:]

    for i, (lat, lng) in enumerate(coords_to_replay, start=start_from):

        # ── Pause at specified index ───────────────────────────────────────
        if pause_at and i == pause_at and not paused:
            paused = True
            cprint(YELLOW, f"\n\n  ⏸  PAUSED at coordinate #{i}/{total}")
            cprint(YELLOW, f"     Courier is approaching the zone boundary.")
            cprint(YELLOW, f"     Position: lat={lat:.6f}  lng={lng:.6f}")
            cprint(CYAN,   f"     Open Tab 2 (Django admin GeofenceEvent) and watch for rows.")
            input(f"\n  Press ENTER to continue playback and cross the boundary...\n")
            cprint(GREEN,  f"  ▶  Resuming playback...\n")

        # ── POST GPS coordinate ────────────────────────────────────────────
        try:
            resp = session.post(
                update_url,
                json={"lat": lat, "lng": lng},
                headers={"X-CSRFToken": csrf_token},
                timeout=5,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("success"):
                success_count += 1
                status_char = GREEN + "●" + RESET
            elif resp.status_code == 403:
                # 403 usually means no active job — show warning but continue
                status_char = YELLOW + "○" + RESET
                if error_count == 0:
                    cprint(YELLOW, f"\n  ⚠  403 Forbidden — check job-id and courier login")
                error_count += 1
            else:
                status_char = RED + "✗" + RESET
                error_count += 1

        except requests.exceptions.Timeout:
            status_char = RED + "T" + RESET
            error_count += 1
        except Exception as e:
            status_char = RED + "E" + RESET
            error_count += 1

        # ── Progress display ───────────────────────────────────────────────
        pct      = (i - start_from + 1) / len(coords_to_replay) * 100
        elapsed  = time.time() - start_time
        eta      = (elapsed / max(i - start_from + 1, 1)) * (len(coords_to_replay) - (i - start_from + 1))
        bar_fill = int(pct / 5)
        bar      = "█" * bar_fill + "░" * (20 - bar_fill)

        print(
            f"{CLEAR}  {status_char}  [{bar}] {pct:5.1f}%  "
            f"coord {i+1}/{total}  "
            f"lat={lat:.5f}  lng={lng:.5f}  "
            f"ETA {int(eta)}s  "
            f"✓{success_count} ✗{error_count}",
            end="",
            flush=True,
        )

        time.sleep(interval)

    # ── Summary ────────────────────────────────────────────────────────────
    elapsed_total = time.time() - start_time
    print()   # newline after progress bar
    cprint(BOLD, f"\n━━━ Replay Complete ━━━")
    cprint(GREEN,  f"  ✓ Successful updates:  {success_count}")
    if error_count:
        cprint(YELLOW, f"  ⚠ Failed updates:      {error_count}")
    cprint(CYAN,   f"  ⏱ Total time:          {elapsed_total:.1f}s")
    cprint(CYAN,   f"  ⚡ Average rate:        {success_count/elapsed_total:.1f} updates/sec")
    cprint(BLUE,   f"\n  Check Tab 2 (Django admin) for GeofenceEvent rows.")


# ═══════════════════════════════════════════════════════════
#  LIST ROUTES
# ═══════════════════════════════════════════════════════════

def list_routes():
    """Show all available routes and whether they have been extracted."""
    cprint(BOLD, "\n━━━ Available Routes ━━━\n")

    for name, defn in ROUTE_DEFINITIONS.items():
        route_file = ROUTES_DIR / f"{name}.json"
        if route_file.exists():
            data = json.loads(route_file.read_text())
            status = f"{GREEN}✓ extracted  ({data['coord_count']} pts, {data['distance_miles']} mi){RESET}"
        else:
            status = f"{YELLOW}⚠ not extracted yet  (run --extract){RESET}"

        print(f"  {BOLD}{CYAN}{name}{RESET}")
        print(f"     {defn['description']}")
        print(f"     {defn['demo_notes']}")
        print(f"     Status: {status}")
        print()


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    global BASE_URL, OSRM_URL
    parser = argparse.ArgumentParser(
        description="RVC GPS Replay Script — Simulate courier driving in Georgia from Nairobi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Extract all routes from OSRM (run once):
  python gps_replay.py --extract

  # List available routes:
  python gps_replay.py --list

  # Full Atlanta→Savannah demo at 5x speed (~90 seconds):
  python gps_replay.py --route atlanta_savannah --speed 5 \\
      --username courier@rvc.com --password pass123 --job-id 1

  # Geofence demo: Atlanta→Marietta at 2x speed, pause at coord 120:
  python gps_replay.py --route atlanta_marietta --speed 2 --pause-at 120 \\
      --username courier@rvc.com --password pass123 --job-id 1

  # Resume from coordinate 200 (skip the beginning):
  python gps_replay.py --route atlanta_savannah --speed 5 --start-from 200 \\
      --username courier@rvc.com --password pass123 --job-id 1
        """,
    )

    # Mode flags
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--extract", action="store_true",
                      help="Extract all routes from OSRM and save to routes/ folder")
    mode.add_argument("--extract-route", metavar="ROUTE",
                      help="Extract a single route from OSRM")
    mode.add_argument("--list", action="store_true",
                      help="List all available routes")

    # Replay options
    parser.add_argument("--route",    metavar="NAME",
                        help="Route to replay (e.g. atlanta_savannah)")
    parser.add_argument("--speed",    type=float, default=5.0,
                        help="Speed multiplier (default: 5). Higher = faster.")
    parser.add_argument("--job-id",   type=str, metavar="ID",
                        help="Django Job ID (for display only — the courier's active job must exist in DB)")
    parser.add_argument("--pause-at", type=int, metavar="INDEX",
                        help="Pause at this coordinate index and wait for keypress")
    parser.add_argument("--start-from", type=int, default=0, metavar="INDEX",
                        help="Start replay from this coordinate index (default: 0)")

    # Auth
    parser.add_argument("--username", default="",
                        help="Courier Django username")
    parser.add_argument("--password", default="",
                        help="Courier Django password")

    # Config overrides
    parser.add_argument("--base-url",  default=BASE_URL,
                        help=f"Django base URL (default: {BASE_URL})")
    parser.add_argument("--osrm-url",  default=OSRM_URL,
                        help=f"OSRM base URL (default: {OSRM_URL})")

    args = parser.parse_args()

    # Apply URL overrides
    BASE_URL = args.base_url
    OSRM_URL = args.osrm_url

    # ── Dispatch ──────────────────────────────────────────────────────────
    if args.extract:
        extract_all_routes()
        return

    if args.extract_route:
        extract_route(args.extract_route)
        return

    if args.list:
        list_routes()
        return

    # Default mode: replay
    if not args.route:
        parser.print_help()
        cprint(YELLOW, "\nTip: run with --list to see available routes")
        cprint(YELLOW, "     run with --extract to extract routes from OSRM first")
        sys.exit(0)

    if not args.username or not args.password:
        cprint(RED, "\nERROR: --username and --password are required for replay")
        cprint(YELLOW, "  Example: --username courier@rvc.com --password yourpassword")
        sys.exit(1)

    # ── Login ─────────────────────────────────────────────────────────────
    session = requests.Session()
    session.headers.update({"User-Agent": "RVC-GPS-Replay/1.0"})

    cprint(BOLD, f"\n━━━ RVC GPS Replay ━━━")
    cprint(CYAN,  f"  Logging in as '{args.username}' at {BASE_URL}...")

    if not login(session, args.username, args.password):
        cprint(RED, "\n  ERROR: Login failed.")
        cprint(YELLOW, "  Check username/password and make sure Docker is running.")
        cprint(YELLOW, "  Also verify the courier account exists in Django admin.")
        sys.exit(1)

    cprint(GREEN, f"  ✓ Logged in successfully\n")

    # ── Replay ────────────────────────────────────────────────────────────
    try:
        replay_route(
            session    = session,
            route_name = args.route,
            speed      = args.speed,
            job_id     = args.job_id,
            pause_at   = args.pause_at,
            start_from = args.start_from,
        )
    except KeyboardInterrupt:
        cprint(YELLOW, f"\n\n  ⏹  Replay interrupted by user.")
        cprint(CYAN,   f"  To resume from the last position, use --start-from N")
        sys.exit(0)


if __name__ == "__main__":
    main()
