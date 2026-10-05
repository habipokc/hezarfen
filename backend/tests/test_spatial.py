import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management import CommandError, call_command
from django.db import connection

from geofencing.models import Geofence
from reference.models import Province, province_at

from .conftest import LTFJ, LTFM

KM_PER_DEG_LAT = 111.32


def north_of(lon_lat: tuple[float, float], km: float) -> Point:
    lon, lat = lon_lat
    return Point(lon, lat + km / KM_PER_DEG_LAT, srid=4326)


@pytest.mark.django_db
def test_seed_creates_two_airport_buffers(seed_airports):
    call_command("seed_geofences")
    fences = Geofence.objects.order_by("name")
    assert [f.name for f in fences] == ["LTFJ 15 km", "LTFM 15 km"]
    assert all(f.kind == Geofence.Kind.AIRPORT_BUFFER and f.active for f in fences)
    assert all(f.geom.valid and f.geom.srid == 4326 for f in fences)


@pytest.mark.django_db
def test_seed_is_idempotent(seed_airports):
    call_command("seed_geofences")
    call_command("seed_geofences")
    assert Geofence.objects.count() == 2


@pytest.mark.django_db
def test_seed_without_reference_data_fails_clearly(db):
    with pytest.raises(CommandError, match="LTFM"):
        call_command("seed_geofences")


@pytest.mark.django_db
def test_point_10km_from_ltfm_is_inside_and_20km_is_outside(seed_airports):
    call_command("seed_geofences")
    ltfm = Geofence.objects.get(name="LTFM 15 km")

    assert Geofence.objects.filter(geom__contains=north_of(LTFM, 10), pk=ltfm.pk).exists()
    assert not Geofence.objects.filter(geom__contains=north_of(LTFM, 20)).exists()
    # Sabiha Gokcen's own position is inside its fence, not inside LTFM's
    inside = Geofence.objects.filter(geom__contains=Point(*LTFJ, srid=4326))
    assert [f.name for f in inside] == ["LTFJ 15 km"]


@pytest.mark.django_db
def test_buffer_radius_is_15km_in_every_direction(seed_airports):
    """A geography buffer is metric: every ring vertex is ~15 000 m from the centre."""
    call_command("seed_geofences")
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT min(d), max(d) FROM (
                SELECT ST_Distance(
                    (dp).geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) AS d
                FROM (SELECT ST_DumpPoints(ST_ExteriorRing(geom)) AS dp
                      FROM geofences WHERE name = 'LTFM 15 km') ring
            ) s
            """,
            list(LTFM),
        )
        shortest, longest = cur.fetchone()
    assert 14_900 < shortest <= longest < 15_100


@pytest.mark.django_db
def test_degree_buffer_is_squashed_east_west():
    """Why we don't buffer in degrees: at 41°N one degree of longitude is ~84 km, not ~111 km."""
    with connection.cursor() as cur:
        cur.execute(
            """
            WITH b AS (SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 0.1348) AS g)
            SELECT
              ST_Distance(ST_MakePoint(ST_XMin(g), %s)::geography,
                          ST_MakePoint(ST_XMax(g), %s)::geography) / 2,
              ST_Distance(ST_MakePoint(%s, ST_YMin(g))::geography,
                          ST_MakePoint(%s, ST_YMax(g))::geography) / 2
            FROM b
            """,
            [LTFM[0], LTFM[1], LTFM[1], LTFM[1], LTFM[0], LTFM[0]],
        )
        east_west, north_south = cur.fetchone()
    assert 14_900 < north_south < 15_100
    assert east_west < 11_500  # ~25% smaller: an ellipse, not a circle


@pytest.mark.django_db
def test_province_at_returns_containing_province():
    Province.objects.create(
        name="Istanbul",
        iso_code="TR-34",
        geom=MultiPolygon(Polygon.from_bbox((28.0, 40.8, 29.9, 41.6)), srid=4326),
    )
    Province.objects.create(
        name="Kocaeli",
        iso_code="TR-41",
        geom=MultiPolygon(Polygon.from_bbox((29.9, 40.5, 30.4, 41.2)), srid=4326),
    )
    assert province_at(28.98, 41.01).name == "Istanbul"
    assert province_at(30.0, 40.8).name == "Kocaeli"
    assert province_at(27.0, 38.0) is None
