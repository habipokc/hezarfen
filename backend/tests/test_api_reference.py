import json
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management import call_command

from geofencing.models import Geofence, GeofenceEvent
from ops.ingest import ingest_status
from tracking import api as tracking_api

pytestmark = pytest.mark.django_db


def wiggly_province():
    """A province outline with 2000 vertices of ~100 m wiggles."""
    import math

    ring = []
    for i in range(2000):
        a = 2 * math.pi * i / 2000
        r = 0.5 + 0.001 * math.sin(i * 7)
        ring.append((29.0 + r * math.cos(a), 40.8 + r * math.sin(a)))
    ring.append(ring[0])
    from reference.models import Province

    return Province.objects.create(
        name="Wiggly", iso_code="TR-99", geom=MultiPolygon(Polygon(ring), srid=4326)
    )


def vertex_count(feature):
    return sum(len(ring) for poly in feature["geometry"]["coordinates"] for ring in poly)


def test_provinces_are_simplified(api):
    wiggly_province()
    simple = api.get("/api/provinces/").json()["features"][0]
    full = api.get("/api/provinces/?simplify=0").json()["features"][0]
    assert simple["properties"] == {"id": simple["properties"]["id"], "name": "Wiggly",
                                    "iso_code": "TR-99"}  # fmt: skip
    assert vertex_count(full) == 2001
    assert vertex_count(simple) < 400
    assert len(json.dumps(simple)) * 4 < len(json.dumps(full))
    # 5 decimals at most
    lon = simple["geometry"]["coordinates"][0][0][0][0]
    assert len(str(lon).split(".")[1]) <= 5


@pytest.mark.parametrize("value", ["-1", "1", "abc"])
def test_provinces_bad_tolerance(api, value):
    resp = api.get(f"/api/provinces/?simplify={value}")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_parameter"


def test_airports_filter_by_type(api, seed_airports):
    from reference.models import Airport

    Airport.objects.create(
        ident="LTBU", type="medium_airport", name="Corlu", geom=Point(27.9, 41.1)
    )
    all_ = api.get("/api/airports/").json()["features"]
    assert [f["properties"]["ident"] for f in all_] == ["LTBU", "LTFJ", "LTFM"]
    large = api.get("/api/airports/?type=large_airport").json()["features"]
    assert [f["properties"]["ident"] for f in large] == ["LTFJ", "LTFM"]
    resp = api.get("/api/airports/?type=heliport")
    assert resp.status_code == 400 and "heliport" in resp.json()["error"]["message"]


def test_stats(api, make_aircraft, monkeypatch):
    make_aircraft("aaaaa1", 28.8, 41.2)
    make_aircraft("aaaaa2", 28.8, 41.2, age=120)
    fence = Geofence.objects.create(name="A", geom=Polygon.from_bbox((28, 40, 29, 41)))
    now = datetime.now(UTC)
    for minutes in (5, 30, 90):
        GeofenceEvent.objects.create(
            geofence=fence, icao24="aaaaa1", event="enter",
            ts=now - timedelta(minutes=minutes), geom=Point(28.5, 40.5),
        )  # fmt: skip
    metrics = {"mode": "synthetic", "last_poll_at": now.isoformat().replace("+00:00", "Z")}
    monkeypatch.setattr(tracking_api, "fetch_ingest_metrics", lambda: metrics)
    body = api.get("/api/stats").json()
    assert body == {
        "active_aircraft": 1,
        "events_last_hour": 2,
        "ingest": {"status": "ok", "metrics": metrics},
    }


def test_ingest_status():
    now = datetime.now(UTC)
    assert ingest_status(None, now) == "unreachable"
    assert ingest_status({"last_poll_at": None}, now) == "starting"
    # Go marshals nanoseconds; Python's fromisoformat must cope
    old = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.123456789Z")
    assert ingest_status({"last_poll_at": old}, now) == "stale"


def test_stats_without_ingest(api, settings):
    settings.INGEST_METRICS_URL = "http://127.0.0.1:9/metrics"  # discard port: refused
    body = api.get("/api/stats").json()
    assert body["ingest"] == {"status": "unreachable", "metrics": None}


def test_unknown_api_path_uses_error_format(api):
    resp = api.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_openapi_schema_is_valid(capsys):
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", "/tmp/schema.yaml")


def test_swagger_ui_and_schema_served(api):
    assert api.get("/api/docs/").status_code == 200
    schema = api.get("/api/schema/?format=json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    for p in ["/api/aircraft/live", "/api/aircraft/{icao24}/", "/api/aircraft/{icao24}/track",
              "/api/playback", "/api/geofences/", "/api/geofences/{id}/", "/api/geofence-events",
              "/api/provinces/", "/api/airports/", "/api/stats"]:  # fmt: skip
        assert p in paths, p
