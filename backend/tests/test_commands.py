from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from reference.models import Airport, Province
from tracking.models import Position


def make_stage_tables(airports: list[tuple], provinces: list[tuple]) -> None:
    """Create staging tables shaped like the ones ogr2ogr writes."""
    with connection.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE stage_airports (
                fid serial PRIMARY KEY, ident varchar, type varchar, name varchar,
                elevation_ft integer, iso_country varchar, municipality varchar,
                iata_code varchar, gps_code varchar, geom geometry(Point, 4326));
            CREATE TABLE stage_provinces (
                fid serial PRIMARY KEY, name varchar, name_tr varchar, iso_3166_2 varchar,
                geom geometry(MultiPolygon, 4326));
            """
        )
        for ident, name, elev_ft, lon, lat in airports:
            cur.execute(
                """INSERT INTO stage_airports
                   (ident, type, name, elevation_ft, iso_country, municipality, iata_code,
                    gps_code, geom)
                   VALUES (%s, 'large_airport', %s, %s, 'TR', 'Istanbul', '', %s,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326))""",
                [ident, name, elev_ft, ident, lon, lat],
            )
        for name, name_tr, iso, bbox in provinces:
            cur.execute(
                """INSERT INTO stage_provinces (name, name_tr, iso_3166_2, geom)
                   VALUES (%s, %s, %s, ST_Multi(ST_MakeEnvelope(%s, %s, %s, %s, 4326)))""",
                [name, name_tr, iso, *bbox],
            )


def stage_tables_exist() -> bool:
    return bool({"stage_airports", "stage_provinces"} & set(connection.introspection.table_names()))


@pytest.mark.django_db
def test_import_reference_upserts_and_converts_feet_to_metres():
    make_stage_tables(
        [("LTFM", "Istanbul Airport", 325, 28.75, 41.27)],
        [("Istanbul", "İstanbul", "TR-34", (28.0, 40.8, 29.9, 41.6))],
    )
    call_command("import_reference")

    ltfm = Airport.objects.get(ident="LTFM")
    assert ltfm.elevation_m == pytest.approx(99.06)
    assert ltfm.iata_code is None  # empty CSV cell -> NULL
    assert Province.objects.get(iso_code="TR-34").name == "İstanbul"  # name_tr preferred
    assert not stage_tables_exist()


@pytest.mark.django_db
def test_import_reference_is_a_mirror_update_and_delete():
    Airport.objects.create(ident="XXXX", type="small_airport", name="Gone", geom=Point(0, 0))
    make_stage_tables([("LTFM", "Old name", 325, 28.75, 41.27)], [])
    call_command("import_reference")
    make_stage_tables([("LTFM", "Istanbul Airport", 325, 28.75, 41.27)], [])
    call_command("import_reference")

    assert list(Airport.objects.values_list("ident", "name")) == [("LTFM", "Istanbul Airport")]


@pytest.mark.django_db
def test_prune_positions_deletes_rows_older_than_retention():
    now = timezone.now()
    for age_days in (1, 6, 8, 30):
        Position.objects.create(
            icao24="4baa0f", ts=now - timedelta(days=age_days), geom=Point(29, 41, srid=4326)
        )
    call_command("prune_positions")  # default POSITIONS_RETENTION_DAYS=7
    assert Position.objects.count() == 2

    call_command("prune_positions", days=3)
    assert Position.objects.count() == 1
