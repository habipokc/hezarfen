import asyncio

from realtime.outbox import DELTA, MESSAGE, SNAPSHOT, Outbox


def delta(ts, upserts=(), removes=()):
    return {
        "ts": ts,
        "upserts": [{"icao24": i, "ts": ts} for i in upserts],
        "removes": list(removes),
    }


def test_empty_outbox_pops_none():
    assert Outbox().pop() is None


def test_pending_deltas_merge_into_one():
    box = Outbox()
    box.push_delta(delta(1, ["aaaaaa"]))
    box.push_delta(delta(2, ["bbbbbb"]))
    kind, merged = box.pop()
    assert kind == DELTA
    assert merged["ts"] == 2
    assert {a["icao24"] for a in merged["upserts"]} == {"aaaaaa", "bbbbbb"}
    assert box.pop() is None


def test_snapshot_first_then_messages_then_delta():
    box = Outbox()
    box.push_delta(delta(1, ["aaaaaa"]))
    box.push({"type": "geofence_event", "id": 1})
    box.push({"type": "heartbeat", "ts": 1})
    box.request_snapshot()
    box.push_delta(delta(2, ["bbbbbb"]))
    assert box.pop() == (SNAPSHOT, None)
    assert box.pop() == (MESSAGE, {"type": "geofence_event", "id": 1})
    assert box.pop() == (MESSAGE, {"type": "heartbeat", "ts": 1})
    kind, d = box.pop()
    # the snapshot supersedes the delta queued before it, not the one after it
    assert kind == DELTA and [a["icao24"] for a in d["upserts"]] == ["bbbbbb"]


def test_messages_are_never_dropped_until_the_cap():
    box = Outbox(max_messages=3)
    assert all(box.push({"id": i}) for i in range(3))
    assert box.push({"id": 3}) is False  # caller closes the connection
    assert [box.pop()[1]["id"] for _ in range(4)] == [0, 1, 2, 3]


def test_get_waits_until_something_is_pushed():
    async def scenario():
        box = Outbox()
        waiter = asyncio.create_task(box.get())
        await asyncio.sleep(0)
        assert not waiter.done()
        box.push({"type": "heartbeat"})
        return await asyncio.wait_for(waiter, 1)

    assert asyncio.run(scenario()) == (MESSAGE, {"type": "heartbeat"})
