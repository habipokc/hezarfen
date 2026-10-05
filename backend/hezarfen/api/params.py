"""Query parameter parsing shared by the API views. Pure functions: no Django, no DB."""

import math

from .errors import ApiError

BBox = tuple[float, float, float, float]

BBOX_HINT = "bbox must be minLon,minLat,maxLon,maxLat (lon -180..180, lat -90..90, min < max)"


def parse_bbox(raw: str) -> BBox:
    parts = raw.split(",")
    if len(parts) != 4:
        raise ApiError("invalid_bbox", BBOX_HINT, {"bbox": raw})
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError:
        raise ApiError("invalid_bbox", BBOX_HINT, {"bbox": raw}) from None
    values = (min_lon, min_lat, max_lon, max_lat)
    if not all(math.isfinite(v) for v in values):
        raise ApiError("invalid_bbox", BBOX_HINT, {"bbox": raw})
    lons_ok = -180 <= min_lon < max_lon <= 180
    lats_ok = -90 <= min_lat < max_lat <= 90
    if not (lons_ok and lats_ok):
        raise ApiError("invalid_bbox", BBOX_HINT, {"bbox": raw})
    return values


def parse_int(raw: str, name: str, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(raw.strip())
    except ValueError:
        raise ApiError(
            "invalid_parameter", f"{name} must be an integer", {"parameter": name}
        ) from None
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        bounds = f"between {minimum} and {maximum}" if maximum is not None else f">= {minimum}"
        raise ApiError("invalid_parameter", f"{name} must be {bounds}", {"parameter": name})
    return value


def parse_unix(raw: str, name: str) -> int:
    """Unix seconds (non-negative integer)."""
    try:
        return parse_int(raw, name, minimum=0)
    except ApiError:
        raise ApiError(
            "invalid_parameter", f"{name} must be Unix seconds (integer)", {"parameter": name}
        ) from None


_TRUE = {"true", "1"}
_FALSE = {"false", "0"}


def parse_bool(raw: str, name: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ApiError("invalid_parameter", f"{name} must be true or false", {"parameter": name})


def parse_csv_choices(raw: str, name: str, allowed: set[str]) -> list[str]:
    values = [v.strip() for v in raw.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown or not values:
        given = ", ".join(unknown) or "(empty)"
        raise ApiError(
            "invalid_parameter",
            f"unknown {name}: {given}; allowed: {', '.join(sorted(allowed))}",
            {"parameter": name},
        )
    return values
