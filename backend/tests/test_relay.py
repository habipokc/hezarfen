import time
from datetime import timedelta

import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.contrib.gis.geos import Point, Polygon
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from geofencing.models import Geofence, GeofenceEvent
from realtime.queries import fences_containing
from realtime.relay import Relay

# ~10 km box around Istanbul Airport (LTFM) and one around Sabiha Gokcen (LTFJ)
LTFM_BOX = (28.69, 41.22, 28.81, 41.33)
LTFJ_BOX = (29.25, 40.85, 29.37, 40.95)


def fence(name, bbox, active=True):
    return Geofence.objects.create(
        name=name, geom=Polygon.from_bbox(bbox), active=active, kind="airport_buffer"
    )


def record(icao24, lon, lat, ts=None, callsign="THY1"):
    return {
        "icao24": icao24, "callsign": callsign, "lon": lon, "lat": lat,
        "baro_alt": 1000.0, "geo_alt": 1050.0, "velocity": 80.0, "heading": 90.0,
        "vrate": 0.0, "on_ground": False, "squawk": None, "category": 4,
        "ts": ts or int(time.time()),
    }  # fmt: skip


def batch(*records):
    return {"schema": "positions.batch/v1", "source": "synthetic", "ts": int(time.time()),
            "aircraft": list(records)}  # fmt: skip


def test_batch_geofence_check_is_one_query(db):
    ltfm = fence("LTFM", LTFM_BOX)
    ltfj = fence("LTFJ", LTFJ_BOX)
    fence("old", LTFM_BOX, active=False)
    records = [
        record("aaaaaa", 28.75, 41.27),  # LTFM
        record("bbbbbb", 29.30, 40.90),  # LTFJ
        record("cccccc", 30.50, 40.50),  # nowhere
    ]
    with CaptureQueriesContext(connection) as ctx:
        pairs = fences_containing(records)
    assert len(ctx.captured_queries) == 1
    assert sorted(pairs) == [("aaaaaa", ltfm.id), ("bbbbbb", ltfj.id)]


async def listen(layer):
    channel = await layer.new_channel()
    await layer.group_add("live", channel)
    return channel


async def drain(layer, channel):
    """Messages already waiting on `channel` (the in-memory layer delivers synchronously)."""
    import asyncio

    messages = []
    while True:
        try:
            messages.append(await asyncio.wait_for(layer.receive(channel), 0.05))
        except TimeoutError:
            return messages


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("close_async_db_connections")
async def test_enter_is_stored_and_broadcast_once_then_exit():
    ltfm = await sync_to_async(fence)("LTFM 15 km", LTFM_BOX)
    layer = get_channel_layer()
    channel = await listen(layer)
    relay = Relay(layer)
    await relay.load()

    await relay.handle_batch(batch(record("aaaaaa", 28.75, 41.27, callsign="THY7AB")))
    [message] = await drain(layer, channel)
    assert message["type"] == "live.geofence_event"
    event = message["event"]
    assert event["geofence"] == {"id": ltfm.id, "name": "LTFM 15 km"}
    assert (event["icao24"], event["callsign"], event["event"]) == ("aaaaaa", "THY7AB", "enter")
    stored = await GeofenceEvent.objects.aget(id=event["id"])
    assert stored.event == "enter"

    await relay.handle_batch(batch(record("aaaaaa", 28.76, 41.28)))  # still inside
    assert await drain(layer, channel) == []
    await relay.handle_batch(batch(record("aaaaaa", 29.50, 41.28)))  # left
    [message] = await drain(layer, channel)
    assert message["event"]["event"] == "exit"
    assert await GeofenceEvent.objects.acount() == 2


def seed_inside_state(fence_obj):
    """An aircraft that entered the fence before the relay restarted, still live."""
    from tracking.models import Aircraft, AircraftLatest

    now = timezone.now()
    aircraft = Aircraft.objects.create(icao24="aaaaaa", first_seen=now, last_seen=now)
    AircraftLatest.objects.create(aircraft=aircraft, ts=now, geom=Point(28.75, 41.27, srid=4326))
    GeofenceEvent.objects.create(
        geofence=fence_obj,
        icao24="aaaaaa",
        event="enter",
        ts=now - timedelta(minutes=5),
        geom=Point(28.7, 41.25, srid=4326),
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("close_async_db_connections")
async def test_restart_rebuilds_state_and_does_not_repeat_enter():
    ltfm = await sync_to_async(fence)("LTFM", LTFM_BOX)
    await sync_to_async(seed_inside_state)(ltfm)
    layer = get_channel_layer()
    channel = await listen(layer)
    relay = Relay(layer)
    await relay.load()
    assert relay.tracker.inside_pairs() == {("aaaaaa", ltfm.id)}

    await relay.handle_batch(batch(record("aaaaaa", 28.75, 41.27)))
    assert await drain(layer, channel) == []
    assert await GeofenceEvent.objects.acount() == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("close_async_db_connections")
async def test_tick_coalesces_batches_into_one_delta():
    layer = get_channel_layer()
    channel = await listen(layer)
    relay = Relay(layer)
    await relay.load()
    now = int(time.time())
    await relay.handle_batch(batch(record("aaaaaa", 29.0, 41.0, ts=now)))
    await relay.handle_batch(batch(record("aaaaaa", 29.1, 41.0, ts=now + 1),
                                   record("bbbbbb", 29.2, 41.0, ts=now + 1)))  # fmt: skip
    await relay.tick(now + 1)
    [message] = await drain(layer, channel)
    assert message["type"] == "live.delta"
    assert [(a["icao24"], a["lon"]) for a in message["upserts"]] == [
        ("aaaaaa", 29.1),
        ("bbbbbb", 29.2),
    ]
    await relay.tick(now + 2)
    assert await drain(layer, channel) == []


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("close_async_db_connections")
async def test_geofences_changed_prunes_deactivated_fence():
    ltfm = await sync_to_async(fence)("LTFM", LTFM_BOX)
    relay = Relay(get_channel_layer())
    await relay.load()
    await relay.handle_batch(batch(record("aaaaaa", 28.75, 41.27)))
    assert relay.tracker.inside_pairs() == {("aaaaaa", ltfm.id)}

    await Geofence.objects.filter(id=ltfm.id).aupdate(active=False)
    changed = b'{"schema":"geofences.changed/v1","action":"updated"}'
    await relay.dispatch("geofences.changed", changed)
    assert relay.tracker.inside_pairs() == set()
    await relay.handle_batch(batch(record("aaaaaa", 28.75, 41.27)))
    assert await GeofenceEvent.objects.acount() == 1  # no exit for a fence that went away


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("close_async_db_connections")
async def test_batch_with_unknown_schema_is_ignored():
    relay = Relay(get_channel_layer())
    await relay.load()
    await relay.dispatch("positions.batch", b'{"schema":"positions.batch/v9","aircraft":[]}')
    await relay.dispatch("positions.batch", b"not json")
    assert len(relay.state) == 0
