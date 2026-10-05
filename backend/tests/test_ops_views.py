import re
from datetime import timedelta

import pytest
import redis
from django.contrib.gis.geos import Point, Polygon
from django.test import Client
from django.utils import timezone

from geofencing.models import Geofence, GeofenceEvent
from ops import views as ops_views
from tracking.models import Position

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def no_ingest(monkeypatch):
    monkeypatch.setattr(ops_views, "fetch_ingest_metrics", lambda: None)


@pytest.fixture
def published(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "geofencing.api.publish_geofences_changed", lambda gid, action: calls.append((gid, action))
    )
    return calls


@pytest.fixture
def fence():
    return Geofence.objects.create(
        name="LTFM 15 km", kind="airport_buffer", geom=Polygon.from_bbox((28, 40, 29, 41))
    )


@pytest.fixture(autouse=True)
def clean_run_key(settings):
    client = redis.Redis.from_url(settings.REDIS_URL)
    client.delete(settings.OPS_RETENTION_KEY)
    yield
    client.delete(settings.OPS_RETENTION_KEY)


def add_events(fence, n):
    now = timezone.now()
    GeofenceEvent.objects.bulk_create(
        GeofenceEvent(
            geofence=fence,
            icao24=f"{i:06x}",
            event="enter" if i % 2 else "exit",
            ts=now - timedelta(seconds=n - i),
            geom=Point(28.5, 40.5),
        )  # fmt: skip
        for i in range(n)
    )


def text(resp):
    return resp.content.decode()


# ------------------------------------------------------------------- page and polling


def test_page_has_every_section(client, no_ingest, fence):
    resp = client.get("/ops/")
    assert resp.status_code == 200
    html = text(resp)
    for section in ('id="ingest"', 'id="events"', 'id="geofences"', 'id="retention"'):
        assert section in html
    assert "htmx.min.js" in html
    assert "LTFM 15 km" in html


def test_page_sends_the_csrf_token_with_every_htmx_request(client, no_ingest):
    html = text(client.get("/ops/"))
    match = re.search(r"hx-headers='\{\"X-CSRFToken\": \"([^\"]+)\"\}'", html)
    assert match and len(match.group(1)) > 20


def test_ops_without_trailing_slash_redirects(client):
    resp = client.get("/ops")
    assert resp.status_code == 301 and resp["Location"] == "/ops/"


@pytest.mark.parametrize("path,section", [("/ops/ingest", "ingest"), ("/ops/events", "events")])
def test_polled_partials_keep_their_trigger(client, no_ingest, path, section):
    # the partial replaces the polling element itself (outerHTML), so it must carry the
    # trigger again or polling stops after the first swap
    resp = client.get(path, **HX)
    assert resp.status_code == 200
    html = text(resp)
    assert "<html" not in html
    assert f'id="{section}"' in html
    assert 'hx-trigger="every 5s' in html


def test_ingest_unreachable(client, no_ingest):
    assert "unreachable" in text(client.get("/ops/ingest", **HX))


def test_ingest_status_from_metrics(client, monkeypatch):
    now = timezone.now().isoformat().replace("+00:00", "Z")
    metrics = {
        "mode": "live", "last_poll_at": now, "credits_remaining": 3000, "daily_credits": 4000,
        "last_batch_size": 41, "rejected_total": {"stale": 2},
    }  # fmt: skip
    monkeypatch.setattr(ops_views, "fetch_ingest_metrics", lambda: metrics)
    html = text(client.get("/ops/ingest", **HX))
    assert "live" in html and "ok" in html
    assert "3000" in html and "75%" in html
    assert "stale" in html


def test_events_are_the_latest_fifty_newest_first(client, fence):
    add_events(fence, 60)
    html = text(client.get("/ops/events", **HX))
    rows = re.findall(r'<tr class="event', html)
    assert len(rows) == 50
    newest, oldest_shown = f"{59:06x}", f"{10:06x}"
    assert html.index(newest) < html.index(oldest_shown)
    assert f"{9:06x}" not in html


def test_no_events_yet(client):
    assert "No geofence events yet" in text(client.get("/ops/events", **HX))


# ------------------------------------------------------------------- geofence switch


def test_deactivate_and_activate(client, fence, published, django_capture_on_commit_callbacks):
    url = f"/ops/geofences/{fence.id}/active"
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(url, {"active": "false"}, **HX)
    assert resp.status_code == 200
    html = text(resp)
    assert html.lstrip().startswith(f'<tr id="fence-{fence.id}"')
    assert "inactive" in html and '"active": "true"' in html  # the button now re-activates
    fence.refresh_from_db()
    assert fence.active is False
    assert published == [(fence.id, "updated")]

    with django_capture_on_commit_callbacks(execute=True):
        client.post(url, {"active": "true"}, **HX)
    fence.refresh_from_db()
    assert fence.active is True
    assert published[-1] == (fence.id, "updated")


def test_setting_the_current_state_again_changes_nothing(
    client, fence, published, django_capture_on_commit_callbacks
):
    # a double click sends the same explicit value twice: no flip back, no reload
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(f"/ops/geofences/{fence.id}/active", {"active": "true"}, **HX)
    assert resp.status_code == 200
    assert published == []


@pytest.mark.parametrize("value", ["", "yes", "1"])
def test_active_must_be_true_or_false(client, fence, value):
    resp = client.post(f"/ops/geofences/{fence.id}/active", {"active": value}, **HX)
    assert resp.status_code == 400


def test_unknown_geofence(client):
    assert client.post("/ops/geofences/999/active", {"active": "false"}).status_code == 404


def test_switch_needs_post(client, fence):
    assert client.get(f"/ops/geofences/{fence.id}/active").status_code == 405


def test_posts_need_the_csrf_token(fence, no_ingest):
    browser = Client(enforce_csrf_checks=True)
    url = f"/ops/geofences/{fence.id}/active"
    assert browser.post(url, {"active": "false"}).status_code == 403
    token = re.search(r'"X-CSRFToken": "([^"]+)"', text(browser.get("/ops/"))).group(1)
    resp = browser.post(url, {"active": "false"}, HTTP_X_CSRFTOKEN=token)
    assert resp.status_code == 200


# ------------------------------------------------------------------- retention


def test_retention_button_prunes_and_reports(client, settings):
    settings.POSITIONS_RETENTION_DAYS = 7
    now = timezone.now()
    for i, days in enumerate((1, 8, 9)):
        Position.objects.create(
            icao24="4baa0f", ts=now - timedelta(days=days, seconds=i), geom=Point(29, 41)
        )
    resp = client.post("/ops/retention", **HX)
    assert resp.status_code == 200
    html = text(resp)
    assert 'id="retention"' in html
    assert "Deleted 2 positions" in html
    assert Position.objects.count() == 1
    # and the page remembers it
    assert "manual" in text(client.get("/ops/retention", **HX))


def test_retention_block_before_any_run(client):
    html = text(client.get("/ops/retention", **HX))
    assert "never" in html


def test_retention_needs_post_to_run(client):
    Position.objects.create(
        icao24="4baa0f", ts=timezone.now() - timedelta(days=30), geom=Point(29, 41)
    )
    client.get("/ops/retention", **HX)
    assert Position.objects.count() == 1
