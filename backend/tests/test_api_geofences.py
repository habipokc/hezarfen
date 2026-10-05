import json
import time
from datetime import UTC, datetime

import pytest
import redis
from django.contrib.gis.geos import Point, Polygon

from geofencing.models import Geofence, GeofenceEvent
from tracking.models import Aircraft

pytestmark = pytest.mark.django_db


def feature(coords, name="Test fence", active=True):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": {"name": name, "active": active},
    }


SQUARE = [[28.9, 41.0], [29.0, 41.0], [29.0, 41.1], [28.9, 41.1], [28.9, 41.0]]
BOWTIE = [[28.8, 40.9], [29.0, 41.1], [29.0, 40.9], [28.8, 41.1], [28.8, 40.9]]


@pytest.fixture
def published(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "geofencing.api.publish_geofences_changed", lambda gid, action: calls.append((gid, action))
    )
    return calls


def test_create_list_patch_delete(api, published, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        resp = api.post("/api/geofences/", feature(SQUARE), format="json")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    fid = body["properties"]["id"]
    assert body["type"] == "Feature" and body["geometry"]["type"] == "Polygon"
    assert body["properties"]["kind"] == "user_drawn"
    assert isinstance(body["properties"]["created_at"], int)
    assert published == [(fid, "created")]

    listed = api.get("/api/geofences/").json()
    assert listed["type"] == "FeatureCollection" and len(listed["features"]) == 1

    with django_capture_on_commit_callbacks(execute=True):
        resp = api.patch(f"/api/geofences/{fid}/", {"properties": {"active": False}}, format="json")
    assert resp.status_code == 200 and resp.json()["properties"]["active"] is False
    assert api.get("/api/geofences/?active=true").json()["features"] == []
    assert len(api.get("/api/geofences/?active=false").json()["features"]) == 1

    with django_capture_on_commit_callbacks(execute=True):
        assert api.delete(f"/api/geofences/{fid}/").status_code == 204
    assert published[1:] == [(fid, "updated"), (fid, "deleted")]
    assert api.get(f"/api/geofences/{fid}/").status_code == 404


def test_kind_cannot_be_set_by_client(api, published):
    body = feature(SQUARE)
    body["properties"]["kind"] = "airport_buffer"
    resp = api.post("/api/geofences/", body, format="json")
    assert resp.json()["properties"]["kind"] == "user_drawn"


@pytest.mark.parametrize(
    "coords,needle",
    [
        (BOWTIE, "2 parts"),
        ([[35.0, 39.0], [35.1, 39.0], [35.1, 39.1], [35.0, 39.0]], "region"),
        ([[28.9, 41.0], [28.901, 41.0], [28.901, 41.001], [28.9, 41.0]], "too small"),
    ],
)
def test_invalid_geometry_is_rejected(api, published, coords, needle):
    resp = api.post("/api/geofences/", feature(coords), format="json")
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "invalid_geometry"
    assert needle in err["message"] and "geom" in err["details"]
    assert Geofence.objects.count() == 0 and published == []


def test_non_polygon_and_missing_name(api, published):
    point = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [29, 41]},
             "properties": {"name": "p"}}  # fmt: skip
    resp = api.post("/api/geofences/", point, format="json")
    assert resp.status_code == 400
    body = feature(SQUARE)
    del body["properties"]["name"]
    resp = api.post("/api/geofences/", body, format="json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_parameter"
    assert "name" in resp.json()["error"]["details"]


def test_malformed_json_body(api):
    resp = api.generic("POST", "/api/geofences/", "{nope", content_type="application/json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "parse_error"


def test_put_is_not_allowed(api):
    resp = api.put("/api/geofences/1/", feature(SQUARE), format="json")
    assert resp.status_code == 405
    assert resp.json()["error"]["code"] == "method_not_allowed"


def test_changed_message_reaches_redis(api, settings, django_capture_on_commit_callbacks):
    """Real publish on a test channel (pub/sub channels are shared across Redis DBs)."""
    settings.GEOFENCES_CHANGED_CHANNEL = "test.geofences.changed"
    pubsub = redis.Redis.from_url(settings.REDIS_URL).pubsub()
    pubsub.subscribe("test.geofences.changed")
    pubsub.get_message(timeout=1)  # subscribe confirmation
    with django_capture_on_commit_callbacks(execute=True):
        fid = api.post("/api/geofences/", feature(SQUARE), format="json").json()["properties"]["id"]
    msg = pubsub.get_message(timeout=2)
    pubsub.close()
    data = json.loads(msg["data"])
    assert data["schema"] == "geofences.changed/v1"
    assert data["geofence_id"] == fid and data["action"] == "created"
    assert abs(data["ts"] - time.time()) < 5


def make_events(n, fence, start=1_791_187_200):
    GeofenceEvent.objects.bulk_create(
        GeofenceEvent(
            geofence=fence, icao24="4baa0f", event="enter" if i % 2 == 0 else "exit",
            ts=datetime.fromtimestamp(start + i, tz=UTC), geom=Point(28.9, 41.0),
        )
        for i in range(n)
    )  # fmt: skip


def test_events_filter_and_cursor_pagination(api):
    poly = Polygon.from_bbox((28.9, 41.0, 29.0, 41.1))
    a = Geofence.objects.create(name="A", geom=poly)
    b = Geofence.objects.create(name="B", geom=poly)
    t = datetime.fromtimestamp(1_791_187_200, tz=UTC)
    Aircraft.objects.create(icao24="4baa0f", callsign="THY7AB", first_seen=t, last_seen=t)
    make_events(150, a)
    make_events(5, b, start=1_791_190_000)

    page = api.get(f"/api/geofence-events?geofence={a.id}").json()
    assert len(page["results"]) == 100 and page["previous"] is None and page["next"]
    first = page["results"][0]
    assert first == {
        "id": first["id"], "geofence": {"id": a.id, "name": "A"}, "icao24": "4baa0f",
        "callsign": "THY7AB", "event": "exit", "ts": 1_791_187_349, "lon": 28.9, "lat": 41.0,
    }  # fmt: skip
    rest = api.get(page["next"]).json()
    assert len(rest["results"]) == 50 and rest["next"] is None
    seen = [e["ts"] for e in page["results"] + rest["results"]]
    assert seen == sorted(seen, reverse=True) and len(set(seen)) == 150

    recent = api.get("/api/geofence-events?since=1791190002").json()["results"]
    assert [e["geofence"]["name"] for e in recent] == ["B", "B", "B"]
    assert api.get("/api/geofence-events?geofence=x").status_code == 400
