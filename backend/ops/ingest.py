"""Ingest health as the backend sees it: the Go service's /metrics document (ICD IF-8).

Used by /api/stats (JSON) and the ops panel (HTML).
"""

import json
import logging
import urllib.request
from datetime import datetime

from django.conf import settings

log = logging.getLogger(__name__)


def fetch_ingest_metrics() -> dict | None:
    try:
        with urllib.request.urlopen(settings.INGEST_METRICS_URL, timeout=1) as resp:
            return json.load(resp)
    except (OSError, ValueError) as exc:
        log.warning("ingest metrics unavailable: %s", exc)
        return None


def _age(value: str | None, now: datetime) -> float | None:
    # Go encodes time.Time as RFC 3339 with up to nanoseconds; fromisoformat truncates
    return None if not value else (now - datetime.fromisoformat(value)).total_seconds()


def ingest_status(metrics: dict | None, now: datetime, live_window: int | None = None) -> str:
    """ok / stale / starting / unreachable, as in /api/stats."""
    if metrics is None:
        return "unreachable"
    age = _age(metrics.get("last_poll_at"), now)
    if age is None:
        return "starting"
    window = settings.LIVE_WINDOW_SECONDS if live_window is None else live_window
    return "ok" if age <= window else "stale"


def ingest_summary(
    metrics: dict | None,
    now: datetime,
    live_window: int | None = None,
    daily_credits: int | None = None,
) -> dict:
    """Flatten the metrics document for the ops template. Every field is optional: an older
    or newer ingest build must not break the page."""
    if metrics is None:
        return {"status": "unreachable"}
    rejected = sorted((metrics.get("rejected_total") or {}).items(), key=lambda kv: (-kv[1], kv[0]))
    credits = metrics.get("credits_remaining")
    budget = metrics.get("daily_credits") or daily_credits
    return {
        "status": ingest_status(metrics, now, live_window),
        "mode": metrics.get("mode"),
        "last_poll_age": _age(metrics.get("last_poll_at"), now),
        "uptime": _age(metrics.get("started_at"), now),
        "credits": credits,
        "credits_pct": round(100 * credits / budget) if credits is not None and budget else None,
        "batch_size": metrics.get("last_batch_size"),
        "inserted": metrics.get("last_positions_inserted"),
        "subscribers": metrics.get("last_subscribers"),
        "errors": metrics.get("error_count"),
        "cycles": metrics.get("cycles"),
        "poll_interval": metrics.get("poll_interval_seconds"),
        "rejected": rejected,
        "rejected_total": sum(count for _, count in rejected),
    }


def format_age(seconds: float | None) -> str:
    """Compact duration for tables: "59 s", "2 min 5 s", "5 h 7 min", "2 d 3 h"."""
    if seconds is None:
        return "never"
    s = int(max(seconds, 0))
    for unit, size, sub_unit, sub_size in (
        ("d", 86400, "h", 3600),
        ("h", 3600, "min", 60),
        ("min", 60, "s", 1),
    ):
        if s >= size:
            whole, rest = divmod(s, size)
            part = rest // sub_size
            return f"{whole} {unit} {part} {sub_unit}" if part else f"{whole} {unit}"
    return f"{s} s"
