"""
Truck/geofencing/pip.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Winding Number Point-in-Polygon (PiP) algorithm.

WHY WINDING NUMBER OVER RAY-CASTING
──────────────────────────────────────
Ray-casting is the most commonly implemented PiP algorithm, but
it fails on:

  1. Concave polygons — a ray from the test point can exit and
     re-enter the polygon, producing incorrect crossing counts.

  2. Self-intersecting polygons — e.g., a figure-8 shaped zone
     where a delivery area wraps around a building block.

  3. Points exactly on polygon edges — undefined behaviour.

Real urban delivery zones are almost always concave. A zone
around an airport loop, a harbour district, or a city block
with internal streets will have concave boundaries.

The Winding Number algorithm counts how many times the polygon
winds around the test point:

  - winding_number == 0  →  point is OUTSIDE
  - winding_number != 0  →  point is INSIDE

Time complexity is O(n) where n is the number of polygon vertices
— identical to ray-casting, but correct for all polygon types.

COORDINATE CONVENTION
──────────────────────
All functions in this module use (lat, lng) order to match the
convention of the rest of the geofencing engine. Note that
PostGIS stores coordinates as (lng, lat) — the evaluator
converts before calling these functions.
"""

from typing import List, Tuple

Coord = Tuple[float, float]   # (lat, lng)


def _is_left(p0: Coord, p1: Coord, p2: Coord) -> float:
    """
    Compute the signed 2D cross product of vectors P0→P1 and P0→P2.

    Returns:
        > 0  if P2 is left of the line P0→P1
        = 0  if P2 is on the line
        < 0  if P2 is right of the line

    This is the Z-component of the 3D cross product:
        (P1 - P0) × (P2 - P0)
    """
    return (
        (p1[0] - p0[0]) * (p2[1] - p0[1])
        - (p2[0] - p0[0]) * (p1[1] - p0[1])
    )


def winding_number(point: Coord, polygon: List[Coord]) -> int:
    """
    Compute the winding number of polygon around point.

    The algorithm scans each edge of the polygon and accumulates a
    winding count based on upward and downward edge crossings:

      - Upward crossing (y1 <= py < y2, point left of edge): wn += 1
      - Downward crossing (y1 > py >= y2, point right of edge): wn -= 1

    A non-zero result means the polygon winds around the point.

    Args:
        point:   (lat, lng) test point
        polygon: list of (lat, lng) vertices. The polygon may be open
                 (first != last) or closed (first == last) — both work.

    Returns:
        int — 0 if outside, non-zero if inside

    Reference:
        Shimrat, M., 1962. Algorithm 112: Position of point relative
        to polygon. Communications of the ACM, 5(8), p.434.
        (Winding Number variant by W. Randolph Franklin)
    """
    px, py = point
    wn = 0
    n = len(polygon)

    # Ensure the polygon is closed for the edge loop
    verts = polygon if polygon[0] == polygon[-1] else polygon + [polygon[0]]

    for i in range(len(verts) - 1):
        x1, y1 = verts[i]
        x2, y2 = verts[i + 1]

        if y1 <= py:
            # Upward crossing: edge goes from below (or at) py to above py
            if y2 > py:
                if _is_left((x1, y1), (x2, y2), (px, py)) > 0:
                    wn += 1
        else:
            # Downward crossing: edge goes from above py to below (or at) py
            if y2 <= py:
                if _is_left((x1, y1), (x2, y2), (px, py)) < 0:
                    wn -= 1

    return wn


def point_in_polygon(point: Coord, polygon: List[Coord]) -> bool:
    """
    Returns True if point is inside polygon using the Winding Number algorithm.

    Args:
        point:   (lat, lng) test point
        polygon: list of (lat, lng) vertices (open or closed)

    Returns:
        True if point is inside the polygon (including on boundary)

    Example:
        >>> zone_verts = [(33.70, -84.45), (33.78, -84.45),
        ...               (33.78, -84.30), (33.70, -84.30)]
        >>> point_in_polygon((33.74, -84.38), zone_verts)
        True
    """
    return winding_number(point, polygon) != 0


def extract_polygon_coords(postgis_polygon) -> List[Coord]:
    """
    Convert a PostGIS/GEOS Polygon object to a list of (lat, lng) tuples
    suitable for the Winding Number algorithm.

    PostGIS stores coordinates as (lng, lat) — this function swaps them
    to (lat, lng) for the PiP functions above.

    Args:
        postgis_polygon: a django.contrib.gis.geos.Polygon instance
                         (from DeliveryZone.boundary)

    Returns:
        List of (lat, lng) tuples for the outer ring of the polygon
    """
    # coords[0] is the exterior ring; coords[0] returns (lng, lat) pairs
    outer_ring = postgis_polygon.coords[0]
    return [(lat, lng) for lng, lat in outer_ring]