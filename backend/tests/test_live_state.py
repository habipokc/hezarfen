import math

import pytest

from realtime.state import LiveState, filter_delta, merge_deltas, parse_subscribe_bbox


def ac(icao24, lon=29.0, lat=41.0, ts=100, **extra):
    return {"icao24": icao24, "lon": lon, "lat": lat, "ts": ts, **extra}


# --- LiveState: coalescing and timeouts ---------------------------------------------


def test_batches_within_a_tick_coalesce_to_latest_state():
    state = LiveState()
    state.apply([ac("aaaaaa", lon=29.0, ts=100)])
    state.apply([ac("aaaaaa", lon=29.1, ts=101), ac("bbbbbb", ts=101)])
    delta = state.flush(now=102)
    assert delta["ts"] == 102
    assert [a["icao24"] for a in delta["upserts"]] == ["aaaaaa", "bbbbbb"]
    assert delta["upserts"][0]["lon"] == 29.1
    assert delta["removes"] == []


def test_flush_without_changes_returns_none():
    state = LiveState()
    state.apply([ac("aaaaaa")])
    state.flush(now=101)
    assert state.flush(now=102) is None


def test_identical_record_is_not_upserted_again():
    state = LiveState()
    state.apply([ac("aaaaaa")])
    state.flush(now=101)
    state.apply([ac("aaaaaa")])  # replayed snapshot: same state
    assert state.flush(now=102) is None


def test_older_record_does_not_overwrite_newer():
    state = LiveState()
    state.apply([ac("aaaaaa", lon=29.5, ts=110)])
    state.apply([ac("aaaaaa", lon=29.0, ts=105)])
    assert state.flush(now=111)["upserts"][0]["lon"] == 29.5


def test_aircraft_unseen_for_window_is_removed_once():
    state = LiveState(window=60)
    state.apply([ac("aaaaaa", ts=100), ac("bbbbbb", ts=150)])
    state.flush(now=150)
    assert state.flush(now=160) is None  # exactly 60 s old is still live, as in the REST API
    assert state.flush(now=161) == {"ts": 161, "upserts": [], "removes": ["aaaaaa"]}
    assert state.flush(now=162) is None
    assert "aaaaaa" not in state


def test_removed_aircraft_that_reappears_is_upserted():
    state = LiveState(window=60)
    state.apply([ac("aaaaaa", ts=100)])
    state.flush(now=200)
    state.apply([ac("aaaaaa", ts=201)])
    assert [a["icao24"] for a in state.flush(now=202)["upserts"]] == ["aaaaaa"]


def test_seeded_aircraft_are_known_but_not_pending():
    state = LiveState(window=60)
    state.seed([ac("aaaaaa", ts=100)])
    assert state.flush(now=101) is None
    assert state.flush(now=161)["removes"] == ["aaaaaa"]


# --- merge_deltas: what a slow client receives -----------------------------------------


def test_merge_keeps_latest_upsert_per_aircraft():
    older = {"ts": 1, "upserts": [ac("aaaaaa", lon=29.0), ac("bbbbbb")], "removes": []}
    newer = {"ts": 2, "upserts": [ac("aaaaaa", lon=29.2)], "removes": []}
    merged = merge_deltas(older, newer)
    assert merged["ts"] == 2
    assert {a["icao24"]: a["lon"] for a in merged["upserts"]} == {"aaaaaa": 29.2, "bbbbbb": 29.0}


def test_merge_remove_after_upsert_wins_and_upsert_after_remove_wins():
    older = {"ts": 1, "upserts": [ac("aaaaaa")], "removes": ["bbbbbb"]}
    newer = {"ts": 2, "upserts": [ac("bbbbbb")], "removes": ["aaaaaa"]}
    merged = merge_deltas(older, newer)
    assert [a["icao24"] for a in merged["upserts"]] == ["bbbbbb"]
    assert merged["removes"] == ["aaaaaa"]


# --- filter_delta: per-client view -----------------------------------------------------

BBOX = (28.0, 40.5, 29.5, 41.5)


def test_filter_sends_only_aircraft_inside_bbox():
    known: set[str] = set()
    delta = {
        "ts": 5,
        "upserts": [ac("aaaaaa", 29.0, 41.0), ac("bbbbbb", 31.0, 41.0)],
        "removes": [],
    }
    upserts, removes = filter_delta(delta, BBOX, known)
    assert [a["icao24"] for a in upserts] == ["aaaaaa"]
    assert removes == []
    assert known == {"aaaaaa"}


def test_aircraft_leaving_bbox_becomes_a_remove():
    known = {"aaaaaa"}
    delta = {"ts": 5, "upserts": [ac("aaaaaa", 30.0, 41.0)], "removes": []}
    assert filter_delta(delta, BBOX, known) == ([], ["aaaaaa"])
    assert known == set()


def test_removes_for_aircraft_the_client_never_saw_are_dropped():
    known = {"aaaaaa"}
    delta = {"ts": 5, "upserts": [], "removes": ["aaaaaa", "cccccc"]}
    assert filter_delta(delta, BBOX, known) == ([], ["aaaaaa"])


def test_aircraft_on_bbox_edge_counts_as_inside():
    upserts, _ = filter_delta({"ts": 5, "upserts": [ac("aaaaaa", 28.0, 40.5)], "removes": []},
                              BBOX, set())  # fmt: skip
    assert len(upserts) == 1


# --- subscribe bbox validation (ICD §6.1) ------------------------------------------------


def test_valid_bbox_is_returned_as_floats():
    assert parse_subscribe_bbox([27.5, 40.4, 30, 41.6]) == (27.5, 40.4, 30.0, 41.6)


@pytest.mark.parametrize(
    "bbox",
    [
        None,
        "27,40,30,41",
        [27, 40, 30],
        [27, 40, 30, "41"],
        [27, 40, 30, True],
        [27, 40, 30, math.inf],
        [30, 40, 27, 41],
        [27, 41, 30, 41],
        [-181, 40, 30, 41],
        [27, 40, 30, 91],
    ],
)
def test_invalid_bbox_raises(bbox):
    with pytest.raises(ValueError):
        parse_subscribe_bbox(bbox)
