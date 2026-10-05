import pytest
from shapely.geometry import Polygon, box

from geofencing.validation import GeometryError, area_km2, validate_polygon

REGION = (26.0, 39.5, 31.5, 42.0)


def square(lon: float, lat: float, half: float) -> Polygon:
    return box(lon - half, lat - half, lon + half, lat + half)


def test_valid_polygon_is_returned_unchanged():
    p = square(28.9, 41.0, 0.05)
    assert validate_polygon(p, REGION).equals(p)


def test_area_is_metric_not_degrees():
    # 0.1° x 0.1° at 41°N: 11.13 km north-south x ~8.40 km east-west
    a = area_km2(square(28.9, 41.0, 0.05))
    assert 92 < a < 95


def test_bowtie_is_rejected_when_it_splits():
    bowtie = Polygon([(28.8, 40.9), (29.0, 41.1), (29.0, 40.9), (28.8, 41.1), (28.8, 40.9)])
    assert not bowtie.is_valid
    with pytest.raises(GeometryError, match="2 parts"):
        validate_polygon(bowtie, REGION)


def test_fixable_polygon_is_repaired():
    # duplicate closing spike: invalid, but make_valid yields one polygon
    spiky = Polygon(
        [(28.8, 40.9), (29.0, 40.9), (29.0, 41.1), (29.0, 41.2), (29.0, 41.1), (28.8, 41.1)]
    )
    assert not spiky.is_valid
    fixed = validate_polygon(spiky, REGION)
    assert fixed.is_valid and fixed.geom_type == "Polygon"


def test_too_small_and_too_large():
    with pytest.raises(GeometryError, match="too small"):
        validate_polygon(square(28.9, 41.0, 0.001), REGION)
    with pytest.raises(GeometryError, match="too large"):
        validate_polygon(box(26.5, 39.6, 31.0, 41.9), REGION)


def test_must_intersect_region():
    with pytest.raises(GeometryError, match="region"):
        validate_polygon(square(35.0, 39.0, 0.1), REGION)


def test_vertex_limit():
    import math

    ring = [
        (
            28.9 + 0.1 * math.cos(2 * math.pi * i / 2000),
            41.0 + 0.1 * math.sin(2 * math.pi * i / 2000),
        )
        for i in range(2000)
    ]
    with pytest.raises(GeometryError, match="vertices"):
        validate_polygon(Polygon(ring), REGION)


def test_holes_are_kept():
    shell = square(28.9, 41.0, 0.1)
    hole = square(28.9, 41.0, 0.02)
    donut = Polygon(shell.exterior.coords, [hole.exterior.coords])
    assert len(validate_polygon(donut, REGION).interiors) == 1
