from datetime import UTC, datetime

import pytest
from django.contrib.gis.geos import Point
from django.db import IntegrityError, connection, transaction

from tracking.models import Aircraft, AircraftLatest, Position

TS = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def index_methods(table: str) -> dict[str, str]:
    """Map index name -> access method (btree, gist, brin) for a table."""
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT i.relname, am.amname
            FROM pg_index x
            JOIN pg_class i ON i.oid = x.indexrelid
            JOIN pg_class t ON t.oid = x.indrelid
            JOIN pg_am am ON am.oid = i.relam
            WHERE t.relname = %s
            """,
            [table],
        )
        return dict(cur.fetchall())


def index_defs(table: str) -> list[str]:
    with connection.cursor() as cur:
        cur.execute("SELECT indexdef FROM pg_indexes WHERE tablename = %s", [table])
        return [row[0] for row in cur.fetchall()]


@pytest.mark.django_db
def test_table_names_are_fixed_for_ingest():
    tables = set(connection.introspection.table_names())
    assert {"aircraft", "aircraft_latest", "positions"} <= tables


@pytest.mark.django_db
def test_positions_reject_duplicate_icao24_ts():
    Position.objects.create(icao24="4baa0f", ts=TS, geom=Point(29.0, 41.0, srid=4326))
    with pytest.raises(IntegrityError), transaction.atomic():
        Position.objects.create(icao24="4baa0f", ts=TS, geom=Point(29.1, 41.1, srid=4326))


@pytest.mark.django_db
def test_ingest_insert_is_idempotent_with_on_conflict_do_nothing():
    # This is the exact statement shape ingest uses (ICD §3).
    sql = """
        INSERT INTO positions (icao24, ts, geom, on_ground)
        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), false)
        ON CONFLICT (icao24, ts) DO NOTHING
    """
    with connection.cursor() as cur:
        for _ in range(3):
            cur.execute(sql, ["4baa0f", TS, 29.0, 41.0])
    assert Position.objects.count() == 1


@pytest.mark.django_db
def test_positions_indexes_gist_brin_and_unique():
    methods = set(index_methods("positions").values())
    assert {"gist", "brin", "btree"} <= methods
    defs = index_defs("positions")
    assert any("USING brin (ts)" in d for d in defs), defs
    assert any("UNIQUE" in d and "(icao24, ts)" in d for d in defs), defs


@pytest.mark.django_db
def test_aircraft_latest_has_gist_index_and_one_row_per_aircraft():
    assert "gist" in index_methods("aircraft_latest").values()

    ac = Aircraft.objects.create(icao24="4baa0f", first_seen=TS, last_seen=TS)
    AircraftLatest.objects.create(aircraft=ac, ts=TS, geom=Point(29.0, 41.0, srid=4326))
    with pytest.raises(IntegrityError), transaction.atomic():
        AircraftLatest.objects.create(aircraft=ac, ts=TS, geom=Point(29.0, 41.0, srid=4326))
    # the primary key column is named icao24 so ingest can address it directly
    assert AircraftLatest.objects.get(pk="4baa0f").aircraft_id == "4baa0f"
