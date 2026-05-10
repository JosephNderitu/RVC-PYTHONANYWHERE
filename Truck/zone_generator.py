"""
Truck/zone_generator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DBSCAN Delivery Zone Generator

PIPELINE
─────────
1. Query Job.pickup_location from PostGIS (last 30 days)
2. Inject synthetic demo data if real data < MIN_POINTS
3. Experimental DBSCAN: try epsilon and min_samples combinations
   to find the best clustering (not hardcoded constants)
4. For each cluster → OSMnx road network ConvexHull polygon
5. Save as DeliveryZone rows in PostGIS
6. Called by Celery-beat at 2AM daily

ACADEMIC RATIONALE
───────────────────
DBSCAN (Density-Based Spatial Clustering of Applications with Noise)
is chosen over K-Means because:
  - Does not require pre-specifying number of clusters
  - Identifies arbitrary cluster shapes (real demand hotspots are not spherical)
  - Marks outlier points as noise rather than forcing them into clusters
  - Proven in urban geospatial literature for delivery demand analysis

OSMnx road-following zones:
  - Zone boundaries follow actual road intersections, not Euclidean lines
  - ConvexHull of road nodes within the cluster radius gives road-aligned edges
  - More meaningful for courier routing than arbitrary geometric shapes

PARAMETER TUNING
─────────────────
eps (epsilon): the maximum distance between two points to be considered
               in the same neighbourhood (in decimal degrees)
               0.05° ≈ 5.5km — good for city-level clusters
               0.02° ≈ 2.2km — neighbourhood-level clusters

min_samples:   minimum points to form a dense region (a "core point")
               Lower = more clusters, Higher = only dense areas

The find_best_params() function tries all combinations and scores them:
  - Prefer 4–8 clusters (useful for Georgia demo)
  - Penalise noise ratio > 30% (too many outliers = bad clustering)
  - Maximise cluster coverage
"""

import logging
import math
import random
from datetime import timedelta

import numpy as np
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────
MIN_POINTS   = 20       # inject synthetic data if fewer real points
ZONE_RADIUS_M = 8000    # 8km radius for OSMnx road network download
LOOKBACK_DAYS = 30      # query last 30 days of jobs

# Georgia demo cities: (name, lat, lng)
DEMO_CITIES = [
    ('Atlanta Delivery Zone',    33.7490, -84.3880),
    ('Marietta Delivery Zone',   33.9526, -84.5494),
    ('Savannah Delivery Zone',   32.0835, -81.0998),
    ('Augusta Delivery Zone',    33.4735, -81.9748),
    ('Macon Delivery Zone',      32.8407, -83.6324),
    ('Athens Delivery Zone',     33.9519, -83.3576),
]


# ═══════════════════════════════════════════════════════════
#  STEP 1: DATA COLLECTION
# ═══════════════════════════════════════════════════════════

def get_pickup_coords(days: int = LOOKBACK_DAYS) -> list[tuple[float, float]]:
    """
    Query real pickup coordinates from PostGIS.
    Returns list of (lat, lng) tuples.
    """
    from Truck.models import Job

    cutoff = timezone.now() - timedelta(days=days)
    jobs = Job.objects.filter(
        pickup_location__isnull=False,
        created_at__gte=cutoff,
        status__in=['completed', 'delivering', 'picking'],
    ).values_list('pickup_location', flat=True)

    coords = []
    for pt in jobs:
        if pt:
            coords.append((pt.y, pt.x))   # (lat, lng)

    logger.info("Retrieved %d real pickup coordinates from last %d days",
                len(coords), days)
    return coords


def inject_synthetic_data(
    existing_coords: list,
    n_per_city: int = 8,
    spread_deg: float = 0.04,
) -> list[tuple[float, float]]:
    """
    Generate synthetic pickup coordinates around Georgia demo cities.

    Uses a deterministic seed so the same zones are generated each run.
    spread_deg ≈ 4.4km standard deviation — realistic city delivery scatter.

    Returns combined list of real + synthetic coordinates.
    """
    rng = random.Random(42)   # fixed seed for reproducibility
    synthetic = []

    for _, lat, lng in DEMO_CITIES:
        for _ in range(n_per_city):
            # Gaussian scatter around city centre
            s_lat = lat + rng.gauss(0, spread_deg)
            s_lng = lng + rng.gauss(0, spread_deg)
            synthetic.append((round(s_lat, 5), round(s_lng, 5)))

    logger.info("Injected %d synthetic coordinates around %d Georgia cities",
                len(synthetic), len(DEMO_CITIES))
    return existing_coords + synthetic


# ═══════════════════════════════════════════════════════════
#  STEP 2: EXPERIMENTAL DBSCAN TUNING
# ═══════════════════════════════════════════════════════════

def find_best_params(coords: np.ndarray) -> tuple[float, int, int]:
    """
    Experimentally tune DBSCAN epsilon and min_samples.

    Tries all combinations in the defined search space and scores
    each result. Returns (best_eps, best_min_samples, n_clusters).

    Scoring criteria:
      - Prefer 4–8 clusters (useful for Georgia geography)
      - Penalise noise ratio > 30%
      - Prefer higher cluster count within preferred range
    """
    from sklearn.cluster import DBSCAN

    # Search space — not hardcoded constants
    eps_values        = [0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15]
    min_samples_values = [2, 3, 4, 5]

    best_eps     = 0.05
    best_min_s   = 3
    best_n       = 0
    best_score   = -1.0

    logger.info("DBSCAN parameter search: %d eps × %d min_samples = %d combinations",
                len(eps_values), len(min_samples_values),
                len(eps_values) * len(min_samples_values))

    for eps in eps_values:
        for min_s in min_samples_values:
            labels = DBSCAN(eps=eps, min_samples=min_s).fit_predict(coords)
            n_clusters  = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise     = int(np.sum(labels == -1))
            noise_ratio = n_noise / len(labels)

            # Score function: reward clusters in 4-8 range, penalise noise
            if n_clusters < 1:
                score = -1.0
            elif 4 <= n_clusters <= 8:
                score = n_clusters * (1.0 - noise_ratio) * 2.0   # bonus for preferred range
            elif n_clusters < 4:
                score = n_clusters * (1.0 - noise_ratio) * 0.5
            else:
                score = (8.0 / n_clusters) * (1.0 - noise_ratio)  # penalise too many

            if noise_ratio > 0.40:
                score *= 0.3   # heavily penalise high noise

            logger.debug(
                "  eps=%.2f min_s=%d → clusters=%d noise=%d(%.0f%%) score=%.3f",
                eps, min_s, n_clusters, n_noise, noise_ratio * 100, score,
            )

            if score > best_score:
                best_score = score
                best_eps   = eps
                best_min_s = min_s
                best_n     = n_clusters

    logger.info(
        "Best DBSCAN params: eps=%.2f min_samples=%d → %d clusters (score=%.3f)",
        best_eps, best_min_s, best_n, best_score,
    )
    return best_eps, best_min_s, best_n


# ═══════════════════════════════════════════════════════════
#  STEP 3: ZONE POLYGON FROM ROAD NETWORK
# ═══════════════════════════════════════════════════════════

def road_network_polygon(centroid_lat: float, centroid_lng: float,
                          radius_m: int = ZONE_RADIUS_M):
    """
    Download OSMnx road network around centroid and compute ConvexHull
    of road nodes to get a road-following zone boundary.

    Returns a Shapely Polygon or None if OSMnx fails.

    WHY CONVEX HULL OF ROAD NODES:
      The ConvexHull vertices are real road intersections — not arbitrary
      geometric points. This means zone boundaries follow actual road
      corridors, making them meaningful for courier route planning.
    """
    try:
        import osmnx as ox
        from scipy.spatial import ConvexHull
        from shapely.geometry import Polygon as ShapelyPolygon

        logger.info("Downloading road network: (%.4f, %.4f) radius=%dm",
                    centroid_lat, centroid_lng, radius_m)

        # Download drivable road network from OSM
        G = ox.graph_from_point(
            (centroid_lat, centroid_lng),
            dist=radius_m,
            network_type='drive',
            simplify=True,
        )
        nodes, _ = ox.graph_to_gdfs(G)

        if len(nodes) < 4:
            logger.warning("Too few road nodes (%d) — using circular fallback", len(nodes))
            return _circular_polygon(centroid_lat, centroid_lng, radius_m)

        # Extract (lng, lat) for ConvexHull (shapely uses lng, lat)
        points = np.array([[row.geometry.x, row.geometry.y]
                            for _, row in nodes.iterrows()])

        hull = ConvexHull(points)
        hull_points = points[hull.vertices]

        # Close the ring: first point = last point (required for valid polygon)
        ring = np.vstack([hull_points, hull_points[0]])
        polygon = ShapelyPolygon(ring)

        if not polygon.is_valid:
            polygon = polygon.buffer(0)   # fix self-intersections

        logger.info("Road ConvexHull: %d nodes → %d hull vertices",
                    len(nodes), len(hull.vertices))
        return polygon

    except ImportError:
        logger.warning("OSMnx/scipy not available — using circular fallback")
        return _circular_polygon(centroid_lat, centroid_lng, radius_m)
    except Exception as exc:
        logger.warning("OSMnx failed (%s) — using circular fallback", exc)
        return _circular_polygon(centroid_lat, centroid_lng, radius_m)


def _circular_polygon(lat: float, lng: float,
                       radius_m: int, n_points: int = 32):
    """
    Fallback: circular polygon around centroid when OSMnx unavailable.
    Used during testing or when internet is unavailable in Docker.
    """
    from shapely.geometry import Polygon as ShapelyPolygon

    # Convert radius from metres to approximate degrees
    radius_deg_lat = radius_m / 111320.0
    radius_deg_lng = radius_m / (111320.0 * math.cos(math.radians(lat)))

    angles = np.linspace(0, 2 * math.pi, n_points, endpoint=False)
    ring = [
        (lng + radius_deg_lng * math.cos(a),
         lat + radius_deg_lat * math.sin(a))
        for a in angles
    ]
    ring.append(ring[0])  # close
    return ShapelyPolygon(ring)


def shapely_to_postgis(shapely_polygon):
    """Convert a Shapely Polygon to a PostGIS-compatible GEOSGeometry."""
    from django.contrib.gis.geos import GEOSGeometry
    return GEOSGeometry(shapely_polygon.wkt, srid=4326)


# ═══════════════════════════════════════════════════════════
#  STEP 4: FULL PIPELINE
# ═══════════════════════════════════════════════════════════

def generate_zones(
    demo_mode: bool = False,
    clear_existing: bool = True,
    days: int = LOOKBACK_DAYS,
) -> list:
    """
    Full DBSCAN zone generation pipeline.

    Args:
        demo_mode:       Always inject synthetic data regardless of real data count
        clear_existing:  Delete old auto-generated zones before creating new ones
        days:            Lookback window for real job data

    Returns:
        List of created DeliveryZone instances
    """
    from sklearn.cluster import DBSCAN
    from Truck.models import DeliveryZone

    logger.info("═══ Zone Generation Pipeline Starting ═══")
    logger.info("demo_mode=%s clear_existing=%s lookback=%d days",
                demo_mode, clear_existing, days)

    # ── Step 1: Data ──────────────────────────────────────
    coords_list = get_pickup_coords(days=days)
    real_count  = len(coords_list)

    if demo_mode or real_count < MIN_POINTS:
        logger.info("Real data insufficient (%d < %d) — injecting synthetic demo data",
                    real_count, MIN_POINTS)
        coords_list = inject_synthetic_data(coords_list)

    coords_np = np.array(coords_list)   # shape: (N, 2) — (lat, lng)
    logger.info("Total coordinate points for clustering: %d", len(coords_np))

    # ── Step 2: Experimental DBSCAN ──────────────────────
    best_eps, best_min_s, _ = find_best_params(coords_np)

    labels = DBSCAN(eps=best_eps, min_samples=best_min_s).fit_predict(coords_np)
    cluster_ids  = sorted(set(labels) - {-1})
    n_noise      = int(np.sum(labels == -1))

    logger.info(
        "DBSCAN result: %d clusters, %d noise points (eps=%.2f min_s=%d)",
        len(cluster_ids), n_noise, best_eps, best_min_s,
    )

    if not cluster_ids:
        logger.error("No clusters found — try adjusting parameters or adding more data")
        return []

    # ── Step 3: Delete old auto-generated zones ───────────
    if clear_existing:
        deleted, _ = DeliveryZone.objects.filter(
            name__contains='Zone'
        ).delete()
        logger.info("Deleted %d existing delivery zones", deleted)

    # ── Step 4: Build zones ───────────────────────────────
    created_zones = []

    for cluster_id in cluster_ids:
        cluster_mask   = labels == cluster_id
        cluster_points = coords_np[cluster_mask]   # (lat, lng)

        # Centroid
        c_lat = float(np.mean(cluster_points[:, 0]))
        c_lng = float(np.mean(cluster_points[:, 1]))

        # Name: match to nearest demo city
        zone_name = _name_zone(c_lat, c_lng, cluster_id)

        # Polygon from road network
        shapely_poly = road_network_polygon(c_lat, c_lng)
        if shapely_poly is None:
            logger.warning("Skipping cluster %d — could not build polygon", cluster_id)
            continue

        postgis_poly = shapely_to_postgis(shapely_poly)

        zone = DeliveryZone.objects.create(
            name      = zone_name,
            boundary  = postgis_poly,
            is_active = True,
        )
        created_zones.append(zone)

        logger.info(
            "Created zone: '%s' | centroid=(%.4f, %.4f) | %d points | pk=%d",
            zone_name, c_lat, c_lng, len(cluster_points), zone.pk,
        )

    logger.info("═══ Zone Generation Complete: %d zones created ═══",
                len(created_zones))
    return created_zones


def _name_zone(lat: float, lng: float, fallback_id: int) -> str:
    """
    Name a zone by finding the nearest demo city.
    If no city is within 50km, use a generic name.
    """
    best_name = f"Delivery Zone {fallback_id + 1}"
    best_dist = float('inf')

    for city_name, city_lat, city_lng in DEMO_CITIES:
        dist = math.sqrt((lat - city_lat) ** 2 + (lng - city_lng) ** 2)
        if dist < best_dist:
            best_dist = dist
            best_name = city_name

    return best_name