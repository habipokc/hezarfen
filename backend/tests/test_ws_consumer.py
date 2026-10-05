import time

import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from hezarfen.asgi import application

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("close_async_db_connections"),
]

ORIGIN = [(b"origin", b"http://localhost:8800")]
BBOX = [28.0, 40.5, 29.5, 41.5]


async def connect(headers=ORIGIN):
    communicator = WebsocketCommunicator(application, "/ws/live/", headers=headers)
    connected, _ = await communicator.connect()
    assert connected
    return communicator


def ac(icao24, lon, lat):
    nulls = dict.fromkeys(
        ("callsign", "baro_alt", "geo_alt", "velocity", "heading", "vrate", "squawk", "category")
    )
    return {**nulls, "icao24": icao24, "lon": lon, "lat": lat, "on_ground": False,
            "ts": int(time.time())}  # fmt: skip


async def send_delta(upserts=(), removes=()):
    await get_channel_layer().group_send(
        "live",
        {"type": "live.delta", "ts": int(time.time()), "upserts": list(upserts),
         "removes": list(removes)},
    )  # fmt: skip


async def test_handshake_without_allowed_origin_is_rejected():
    for headers in ([], [(b"origin", b"http://evil.example")]):
        communicator = WebsocketCommunicator(application, "/ws/live/", headers=headers)
        connected, _ = await communicator.connect()
        assert not connected


async def test_only_heartbeats_before_subscribe(settings):
    settings.WS_HEARTBEAT_SECONDS = 0.05
    ws = await connect()
    await send_delta([ac("aaaaaa", 29.0, 41.0)])
    assert (await ws.receive_json_from(timeout=1))["type"] == "heartbeat"
    assert (await ws.receive_json_from(timeout=1))["type"] == "heartbeat"
    await ws.disconnect()


async def test_bad_messages_get_errors_and_the_connection_stays_open(make_aircraft):
    ws = await connect()
    for frame, code in [
        ("{nope", "invalid_json"),
        ('{"type":"hello"}', "unknown_type"),
        ('["subscribe"]', "unknown_type"),
        ('{"type":"subscribe","bbox":[30,40,28,41]}', "invalid_bbox"),
    ]:
        await ws.send_to(text_data=frame)
        reply = await ws.receive_json_from()
        assert (reply["type"], reply["code"]) == ("error", code)
    await ws.send_json_to({"type": "subscribe", "bbox": BBOX})
    assert (await ws.receive_json_from())["type"] == "snapshot"
    await ws.disconnect()


async def test_subscribe_returns_snapshot_of_live_aircraft_in_bbox(make_aircraft):
    make = sync_to_async(make_aircraft)
    await make("aaaaaa", 29.0, 41.0, callsign="THY7AB", baro_altitude=3000.0)
    await make("bbbbbb", 30.5, 41.0)  # outside the bbox
    await make("cccccc", 29.1, 41.1, age=120)  # not live any more
    ws = await connect()
    await ws.send_json_to({"type": "subscribe", "bbox": BBOX})
    snapshot = await ws.receive_json_from()
    assert snapshot["type"] == "snapshot"
    [aircraft] = snapshot["aircraft"]
    assert set(aircraft) == {
        "icao24", "callsign", "lon", "lat", "baro_alt", "geo_alt", "velocity", "heading",
        "vrate", "on_ground", "squawk", "category", "ts",
    }  # fmt: skip
    assert (aircraft["icao24"], aircraft["callsign"], aircraft["baro_alt"]) == (
        "aaaaaa",
        "THY7AB",
        3000.0,
    )
    await ws.disconnect()


async def test_delta_is_filtered_by_bbox_and_empty_deltas_are_not_sent(make_aircraft):
    await sync_to_async(make_aircraft)("aaaaaa", 29.0, 41.0)
    ws = await connect()
    await ws.send_json_to({"type": "subscribe", "bbox": BBOX})
    await ws.receive_json_from()  # snapshot with aaaaaa

    await send_delta([ac("bbbbbb", 29.2, 41.2), ac("cccccc", 31.0, 41.0)])
    delta = await ws.receive_json_from()
    assert delta["type"] == "delta"
    assert [a["icao24"] for a in delta["upserts"]] == ["bbbbbb"]
    assert delta["removes"] == []

    # aaaaaa flies out, bbbbbb times out, dddddd was never visible to this client
    await send_delta([ac("aaaaaa", 30.0, 41.0)], removes=["bbbbbb", "dddddd"])
    delta = await ws.receive_json_from()
    assert delta["upserts"] == [] and delta["removes"] == ["aaaaaa", "bbbbbb"]

    await send_delta([ac("eeeeee", 31.0, 41.0)])  # nothing for this bbox
    assert await ws.receive_nothing(timeout=0.2)
    await ws.disconnect()


async def test_geofence_events_are_not_filtered_by_bbox():
    ws = await connect()
    await ws.send_json_to({"type": "subscribe", "bbox": [26.0, 39.5, 26.5, 40.0]})
    await ws.receive_json_from()
    event = {
        "id": 7,
        "geofence": {"id": 1, "name": "LTFM 15 km"},
        "icao24": "aaaaaa",
        "callsign": "THY7AB",
        "event": "enter",
        "ts": 1,
        "lon": 28.79,
        "lat": 41.18,
    }
    await get_channel_layer().group_send("live", {"type": "live.geofence_event", "event": event})
    assert await ws.receive_json_from() == {"type": "geofence_event", **event}
    await ws.disconnect()


async def test_new_subscribe_replaces_bbox_and_sends_fresh_snapshot(make_aircraft):
    make = sync_to_async(make_aircraft)
    await make("aaaaaa", 29.0, 41.0)
    await make("bbbbbb", 27.0, 40.0)
    ws = await connect()
    await ws.send_json_to({"type": "subscribe", "bbox": BBOX})
    assert [a["icao24"] for a in (await ws.receive_json_from())["aircraft"]] == ["aaaaaa"]
    await ws.send_json_to({"type": "subscribe", "bbox": [26.5, 39.5, 27.5, 40.5]})
    assert [a["icao24"] for a in (await ws.receive_json_from())["aircraft"]] == ["bbbbbb"]
    # aaaaaa is no longer known to this client, so its removal is not forwarded
    await send_delta(removes=["aaaaaa"])
    assert await ws.receive_nothing(timeout=0.2)
    await ws.disconnect()
