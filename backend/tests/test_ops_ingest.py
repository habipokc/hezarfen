from datetime import UTC, datetime

import pytest

from ops.ingest import format_age, ingest_summary

NOW = datetime(2026, 10, 5, 12, 0, 0, tzinfo=UTC)


def metrics(**override):
    # shape of the Go /metrics document (ICD IF-8); timestamps as Go encodes them
    base = {
        "mode": "synthetic",
        "started_at": "2026-10-05T11:00:00.123456789Z",
        "last_poll_at": "2026-10-05T11:59:58Z",
        "credits_remaining": None,
        "last_batch_size": 60,
        "error_count": 0,
        "cycles": 1800,
        "poll_interval_seconds": 2,
        "last_positions_inserted": 60,
        "last_subscribers": 1,
        "rejected_total": {"stale": 1, "bbox": 3},
    }
    return base | override


def test_unreachable_without_metrics():
    assert ingest_summary(None, NOW) == {"status": "unreachable"}


def test_healthy_summary():
    s = ingest_summary(metrics(), NOW)
    assert s["status"] == "ok"
    assert s["mode"] == "synthetic"
    assert s["last_poll_age"] == pytest.approx(2.0)
    assert s["uptime"] == pytest.approx(3599.88, abs=0.01)
    assert s["batch_size"] == 60 and s["inserted"] == 60 and s["subscribers"] == 1
    assert s["errors"] == 0 and s["cycles"] == 1800 and s["poll_interval"] == 2
    assert s["credits"] is None


def test_rejections_sorted_by_count():
    s = ingest_summary(metrics(), NOW)
    assert s["rejected"] == [("bbox", 3), ("stale", 1)]
    assert s["rejected_total"] == 4


def test_starting_before_the_first_poll():
    s = ingest_summary(metrics(last_poll_at=None, rejected_total={}), NOW)
    assert s["status"] == "starting"
    assert s["last_poll_age"] is None
    assert s["rejected"] == [] and s["rejected_total"] == 0


def test_stale_when_the_last_poll_is_older_than_the_live_window():
    s = ingest_summary(metrics(last_poll_at="2026-10-05T11:58:59Z"), NOW, live_window=60)
    assert s["status"] == "stale"


def test_credits_left_as_a_share_of_the_daily_budget():
    s = ingest_summary(metrics(mode="live", credits_remaining=1000), NOW, daily_credits=4000)
    assert s["credits"] == 1000
    assert s["credits_pct"] == 25


def test_unknown_or_missing_fields_do_not_break_the_page():
    # an older or newer ingest build may send fewer fields
    s = ingest_summary({"mode": "replay", "last_poll_at": "2026-10-05T11:59:59Z"}, NOW)
    assert s["status"] == "ok" and s["mode"] == "replay"
    assert s["rejected"] == [] and s["batch_size"] is None


@pytest.mark.parametrize(
    "seconds,text",
    [
        (None, "never"),
        (0.4, "0 s"),
        (59.6, "59 s"),
        (60, "1 min"),
        (125, "2 min 5 s"),
        (3600, "1 h"),
        (3600 * 5 + 60 * 7 + 9, "5 h 7 min"),
        (86400 * 2 + 3600 * 3, "2 d 3 h"),
    ],
)
def test_format_age(seconds, text):
    assert format_age(seconds) == text
