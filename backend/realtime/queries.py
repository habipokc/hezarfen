"""Database access for the real-time layer. Synchronous; async callers wrap it in a thread."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.db import connection
from django.db.models import F
from django.utils import timezone

from geofencing.models import Geofence, GeofenceEvent
from tracking.models import AircraftLatest

from .state import Aircraft, BBox

# How far back the relay looks for a fence's last event when rebuilding its state.
REBUILD_LOOKBACK = timedelta(hours=24)


def live_aircraft(bbox: BBox | None = None) -> list[Aircraft]:
    """ICD Aircraft objects seen in the live window, optionally inside a bbox (snapshot)."""
    since = timezone.now() - timedelta(seconds=settings.LIVE_WINDOW_SECONDS)
    qs = AircraftLatest.objects.filter(ts__gte=since)
    if bbox is not None:
        qs = qs.filter(geom__bboverlaps=Polygon.from_bbox(bbox))
    rows = qs.order_by("aircraft_id").values(
        "aircraft_id", "geom", "baro_altitude", "geo_altitude", "velocity", "heading",
        "vertical_rate", "on_ground", "squawk", "ts",
        callsign=F("aircraft__callsign"), category=F("aircraft__category"),
    )  # fmt: skip
    return [
        {
            "icao24": r["aircraft_id"],
            "callsign": r["callsign"],
            "lon": r["geom"].x,
            "lat": r["geom"].y,
            "baro_alt": r["baro_altitude"],
            "geo_alt": r["geo_altitude"],
            "velocity": r["velocity"],
            "heading": r["heading"],
            "vrate": r["vertical_rate"],
            "on_ground": r["on_ground"],
            "squawk": r["squawk"],
            "category": r["category"],
            "ts": int(r["ts"].timestamp()),
        }
        for r in rows
    ]


# One round trip for the whole batch: the positions travel as three parallel arrays
# (the same unnest pattern ingest uses for its inserts), and the GiST index on
# geofences.geom narrows each point to the fences whose bounding box contains it before
# ST_Contains does the exact test.
CONTAINS_SQL = """
SELECT b.icao24, g.id
FROM unnest(%s::text[], %s::float8[], %s::float8[]) AS b(icao24, lon, lat)
JOIN geofences g
  ON g.active AND ST_Contains(g.geom, ST_SetSRID(ST_MakePoint(b.lon, b.lat), 4326))
"""


def fences_containing(records: Sequence[Aircraft]) -> list[tuple[str, int]]:
    if not records:
        return []
    with connection.cursor() as cur:
        cur.execute(
            CONTAINS_SQL,
            [
                [r["icao24"] for r in records],
                [r["lon"] for r in records],
                [r["lat"] for r in records],
            ],
        )
        return [(icao24, fence_id) for icao24, fence_id in cur.fetchall()]


def active_fence_names() -> dict[int, str]:
    return dict(Geofence.objects.filter(active=True).values_list("id", "name"))


# Last event per (fence, aircraft); the pair is still "inside" if that event is an enter.
# Only aircraft still in the live window matter: anything older has timed out and the
# relay would have forgotten it anyway.
INSIDE_FROM_EVENTS_SQL = """
SELECT icao24, geofence_id FROM (
    SELECT DISTINCT ON (e.geofence_id, e.icao24) e.geofence_id, e.icao24, e.event
    FROM geofence_events e
    JOIN geofences g ON g.id = e.geofence_id AND g.active
    JOIN aircraft_latest a ON a.icao24 = e.icao24 AND a.ts >= %s
    WHERE e.ts >= %s
    ORDER BY e.geofence_id, e.icao24, e.ts DESC, e.id DESC
) last
WHERE event = 'enter'
"""


def inside_pairs_from_events() -> list[tuple[str, int]]:
    now = timezone.now()
    live_since = now - timedelta(seconds=settings.LIVE_WINDOW_SECONDS)
    with connection.cursor() as cur:
        cur.execute(INSIDE_FROM_EVENTS_SQL, [live_since, now - REBUILD_LOOKBACK])
        return [(icao24, fence_id) for icao24, fence_id in cur.fetchall()]


def store_events(events: Sequence[tuple[Aircraft, int, str]]) -> list[GeofenceEvent]:
    """Insert (aircraft record, fence id, enter|exit) rows; returns them with ids."""
    rows = [
        GeofenceEvent(
            geofence_id=fence_id,
            icao24=record["icao24"],
            event=kind,
            ts=datetime.fromtimestamp(record["ts"], tz=UTC),
            geom=Point(record["lon"], record["lat"], srid=4326),
        )
        for record, fence_id, kind in events
    ]
    return GeofenceEvent.objects.bulk_create(rows)
