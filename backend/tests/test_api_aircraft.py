import time
from datetime import UTC, datetime

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import connection

from reference.models import Province
from tracking.models import Position

from .conftest import LTFJ

pytestmark = pytest.mark.django_db


def icaos(resp):
    return [f["properties"]["icao24"] for f in resp.json()["features"]]


def test_live_returns_geojson_with_icd_aircraft_properties(api, make_aircraft):
    make_aircraft("4baa0f", 28.8, 41.2, baro_altitude=3000.0, vertical_rate=5.0, heading=90.0)
    resp = api.get("/api/aircraft/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    feature = body["features"][0]
    assert feature["geometry"] == {"type": "Point", "coordinates": [28.8, 41.2]}
    props = feature["properties"]
    assert set(props) == {
        "icao24", "callsign", "lon", "lat", "baro_alt", "geo_alt", "velocity",
        "heading", "vrate", "on_ground", "squawk", "category", "ts",
    }  # fmt: skip
    assert props["baro_alt"] == 3000.0 and props["vrate"] == 5.0 and props["geo_alt"] is None
    assert isinstance(props["ts"], int) and abs(props["ts"] - time.time()) < 5


def test_live_bbox_filter_excludes_outside_and_stale(api, make_aircraft):
    make_aircraft("aaaaa1", 28.8, 41.2)  # inside
    make_aircraft("aaaaa2", 30.5, 40.0)  # outside the bbox below
    make_aircraft("aaaaa3", 28.9, 41.0, age=61)  # inside but older than 60 s
    make_aircraft("aaaaa4", 28.0, 41.0)  # on the bbox edge: included
    resp = api.get("/api/aircraft/live?bbox=28.0,40.5,29.5,41.5")
    assert icaos(resp) == ["aaaaa1", "aaaaa4"]
    # default bbox = whole region
    assert icaos(api.get("/api/aircraft/live")) == ["aaaaa1", "aaaaa2", "aaaaa4"]


@pytest.mark.parametrize("bbox", ["28,40", "41.5,29.5,40.5,28", "x,1,2,3", "28,40,29,95"])
def test_live_invalid_bbox(api, bbox):
    resp = api.get(f"/api/aircraft/live?bbox={bbox}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_bbox"


def test_detail_has_province_and_nearest_airport(api, make_aircraft, seed_airports):
    Province.objects.create(
        name="İstanbul", iso_code="TR-34",
        geom=MultiPolygon(Polygon.from_bbox((28.0, 40.8, 29.9, 41.6)), srid=4326),
    )  # fmt: skip
    make_aircraft("4baa0f", 28.80, 41.25)  # ~5 km from LTFM, ~50 km from LTFJ
    resp = api.get("/api/aircraft/4BAA0F/")
    assert resp.status_code == 200
    props = resp.json()["properties"]
    assert props["province"] == "İstanbul"
    assert props["nearest_airport"]["ident"] == "LTFM"
    assert 4_000 < props["nearest_airport"]["distance_m"] < 5_000
    assert props["origin_country"] == "Turkey" and props["source"] == "synthetic"


def test_detail_over_sea_has_no_province(api, make_aircraft, seed_airports):
    make_aircraft("4baa0f", *LTFJ)
    props = api.get("/api/aircraft/4baa0f/").json()["properties"]
    assert props["province"] is None
    assert props["nearest_airport"]["ident"] == "LTFJ"


def test_nearest_airport_uses_metric_distance(make_aircraft, db):
    """A planar `<->` ranking is wrong at 41°N; the re-rank must fix it."""
    from reference.models import Airport
    from tracking.api import nearest_airport

    p = Point(29.0, 41.0, srid=4326)
    # EAST is 0.09° away in longitude (≈7.6 km), NRTH 0.08° in latitude (≈8.9 km):
    # planar degrees say NRTH is nearer, metres say EAST is
    Airport.objects.create(ident="EAST", type="small_airport", name="E", geom=Point(29.09, 41.0))
    Airport.objects.create(ident="NRTH", type="small_airport", name="N", geom=Point(29.0, 41.08))
    assert nearest_airport(p)["ident"] == "EAST"


def test_detail_unknown_aircraft_is_404(api):
    resp = api.get("/api/aircraft/abcdef/")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "not_found", "message": "not found", "details": {}}}


def add_positions(icao24, points):
    Position.objects.bulk_create(
        Position(icao24=icao24, ts=datetime.fromtimestamp(ts, tz=UTC), geom=Point(lon, lat))
        for ts, lon, lat in points
    )


def test_track_is_ordered_by_time(api, make_aircraft):
    make_aircraft("4baa0f", 28.9, 41.0)
    now = int(time.time())
    # inserted out of order on purpose
    add_positions(
        "4baa0f",
        [(now - 20, 28.92, 41.0), (now - 40, 28.90, 41.0), (now - 30, 28.91, 41.0),
         (now - 4000, 28.0, 41.0)],
    )  # fmt: skip
    resp = api.get(f"/api/aircraft/4baa0f/track?since={now - 60}")
    body = resp.json()
    assert body["geometry"]["type"] == "LineString"
    assert body["geometry"]["coordinates"] == [[28.9, 41.0], [28.91, 41.0], [28.92, 41.0]]
    assert body["properties"] == {
        "icao24": "4baa0f", "callsign": "THY1",
        "start_ts": now - 40, "end_ts": now - 20, "points": 3,
    }  # fmt: skip
    # default window (30 min) still leaves out the hour-old point
    assert api.get("/api/aircraft/4baa0f/track").json()["properties"]["points"] == 3


def test_track_with_one_point_has_null_geometry(api, make_aircraft):
    make_aircraft("4baa0f", 28.9, 41.0)
    add_positions("4baa0f", [(int(time.time()) - 5, 28.9, 41.0)])
    body = api.get("/api/aircraft/4baa0f/track").json()
    assert body["geometry"] is None and body["properties"]["points"] == 1


def test_track_errors(api, make_aircraft):
    assert api.get("/api/aircraft/abcdef/track").status_code == 404
    make_aircraft("4baa0f", 28.9, 41.0)
    resp = api.get("/api/aircraft/4baa0f/track?since=yesterday")
    assert resp.json()["error"]["code"] == "invalid_parameter"
    resp = api.get(f"/api/aircraft/4baa0f/track?since={int(time.time()) - 90000}")
    assert resp.json()["error"]["code"] == "window_too_large"


def test_playback_buckets_keep_latest_fix(api, make_aircraft):
    make_aircraft("aaaaa1", 28.9, 41.0)
    t0 = 1_791_187_200  # multiple of 10
    add_positions("aaaaa1", [(t0 + 1, 28.0, 41.0), (t0 + 7, 28.1, 41.0), (t0 + 12, 28.2, 41.0)])
    add_positions("bbbbb2", [(t0 + 3, 29.0, 40.0)])  # no aircraft row: callsign null
    body = api.get(f"/api/playback?start={t0}&end={t0 + 20}&bucket=10").json()
    assert body["start"] == t0 and body["bucket"] == 10
    frames = body["frames"]
    assert [f["ts"] for f in frames] == [t0, t0 + 10]
    first = {a["icao24"]: a for a in frames[0]["aircraft"]}
    assert first["aaaaa1"]["lon"] == 28.1 and first["aaaaa1"]["ts"] == t0 + 7
    assert first["bbbbb2"]["callsign"] is None
    assert [a["lon"] for a in frames[1]["aircraft"]] == [28.2]


@pytest.mark.parametrize(
    "query,code",
    [
        ("start=100&end=7301", "window_too_large"),
        ("start=200&end=100", "invalid_parameter"),
        ("start=0&end=100&bucket=0", "invalid_parameter"),
        ("start=abc&end=100", "invalid_parameter"),
    ],
)
def test_playback_validation(api, query, code):
    resp = api.get(f"/api/playback?{query}")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == code


def test_playback_window_boundaries(api, make_aircraft):
    make_aircraft("aaaaa1", 28.9, 41.0)
    t0 = 1_791_187_200
    # one fix exactly on start (inclusive) and one exactly on end (exclusive)
    add_positions("aaaaa1", [(t0, 28.0, 41.0), (t0 + 7200, 28.5, 41.0)])
    resp = api.get(f"/api/playback?start={t0}&end={t0 + 7200}&bucket=600")
    assert resp.status_code == 200
    frames = resp.json()["frames"]
    assert [f["ts"] for f in frames] == [t0]
    assert frames[0]["aircraft"][0]["ts"] == t0
    # one second over the 2 h limit, and one over the largest bucket
    resp = api.get(f"/api/playback?start={t0}&end={t0 + 7201}")
    assert resp.json()["error"]["code"] == "window_too_large"
    resp = api.get(f"/api/playback?start={t0}&end={t0 + 60}&bucket=601")
    assert resp.json()["error"]["code"] == "invalid_parameter"


def test_playback_default_window_is_last_15_minutes(api, make_aircraft):
    make_aircraft("aaaaa1", 28.9, 41.0)
    now = int(time.time())
    add_positions("aaaaa1", [(now - 1000, 28.0, 41.0), (now - 60, 28.1, 41.0)])
    body = api.get("/api/playback").json()
    assert body["end"] - body["start"] == 900
    assert [a["ts"] for f in body["frames"] for a in f["aircraft"]] == [now - 60]


def test_live_query_uses_index_friendly_bbox_operator(api, make_aircraft):
    """The bbox filter must be `geom && envelope` (answered by the GiST index), not a
    per-row function like ST_Within that only some planners can rewrite."""
    from django.test.utils import CaptureQueriesContext

    make_aircraft("aaaaa1", 28.8, 41.2)
    with CaptureQueriesContext(connection) as ctx:
        api.get("/api/aircraft/live?bbox=28,40,29.5,41.5")
    sql = " ".join(q["sql"] for q in ctx.captured_queries)
    assert '"aircraft_latest"."geom" && ' in sql
    assert len(ctx.captured_queries) == 1  # select_related: no query per aircraft
