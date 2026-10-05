"""Geofence polygon checks, done with shapely before anything touches the database.

shapely runs in the request process (no round trip), gives precise reasons for invalidity
and can repair rings with make_valid; PostGIS then only stores and queries clean shapes.
"""

import math

from shapely import make_valid
from shapely.geometry import Polygon, box
from shapely.ops import transform
from shapely.validation import explain_validity

MAX_VERTICES = 1000
MIN_AREA_KM2 = 0.25  # ~500 m x 500 m: smaller fences would flicker on every GPS jitter
MAX_AREA_KM2 = 20_000  # about two thirds of the Marmara bbox
M_PER_DEG_LAT = 111_320.0


class GeometryError(ValueError):
    pass


def area_km2(poly: Polygon) -> float:
    """Approximate geodesic area: degrees scaled to metres around the polygon's own latitude.

    Error is well under 1% for regional-sized shapes, which is plenty for sanity limits.
    """
    lat0 = math.radians(poly.centroid.y)
    kx = M_PER_DEG_LAT * math.cos(lat0)

    def to_metres(x, y, z=None):
        return (x * kx, y * M_PER_DEG_LAT)

    return transform(to_metres, poly).area / 1e6


def _vertices(poly: Polygon) -> int:
    return len(poly.exterior.coords) + sum(len(r.coords) for r in poly.interiors)


def validate_polygon(poly: Polygon, region: tuple[float, float, float, float]) -> Polygon:
    """Return a valid single Polygon or raise GeometryError with a human-readable reason."""
    if poly.geom_type != "Polygon":
        raise GeometryError(f"geometry must be a Polygon, got {poly.geom_type}")
    if poly.is_empty:
        raise GeometryError("polygon is empty")
    if _vertices(poly) > MAX_VERTICES:
        raise GeometryError(f"polygon has more than {MAX_VERTICES} vertices")
    minx, miny, maxx, maxy = poly.bounds
    if not (-180 <= minx and maxx <= 180 and -90 <= miny and maxy <= 90):
        raise GeometryError("coordinates must be [lon, lat] within -180..180, -90..90")

    if not poly.is_valid:
        reason = explain_validity(poly)
        fixed = make_valid(poly)
        parts = [g for g in getattr(fixed, "geoms", [fixed]) if g.geom_type == "Polygon"]
        if len(parts) != 1:
            raise GeometryError(
                f"invalid polygon ({reason}); repairing it splits it into {len(parts)} parts"
            )
        poly = parts[0]

    area = area_km2(poly)
    if area < MIN_AREA_KM2:
        raise GeometryError(f"polygon is too small ({area:.3f} km² < {MIN_AREA_KM2} km²)")
    if area > MAX_AREA_KM2:
        raise GeometryError(f"polygon is too large ({area:.0f} km² > {MAX_AREA_KM2} km²)")
    if not poly.intersects(box(*region)):
        raise GeometryError("polygon does not intersect the region bbox")
    return poly
