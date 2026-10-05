"""Position history retention: delete rows older than POSITIONS_RETENTION_DAYS.

Run by the `maintenance` service every RETENTION_INTERVAL_SECONDS, by the ops panel button
and by `manage.py prune_positions`. The last run is kept in Redis for the ops panel.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import redis
from django.conf import settings
from django.db import connection
from django.utils import timezone

log = logging.getLogger(__name__)

# Small transactions: ingest inserts into the same table every cycle, and one DELETE of a
# day of history (millions of rows) would hold its locks and WAL for the whole run.
BATCH_SIZE = 20_000

# The inner SELECT finds old rows through the BRIN index on ts; deleting by primary key
# then touches exactly those rows. Postgres has no DELETE ... LIMIT.
DELETE_BATCH = """
    DELETE FROM positions
    WHERE id IN (SELECT id FROM positions WHERE ts < %s LIMIT %s)
"""


@dataclass(frozen=True)
class PruneResult:
    deleted: int
    days: int
    cutoff: datetime
    seconds: float
    batches: int


def prune_positions(days: int | None = None, batch_size: int = BATCH_SIZE) -> PruneResult:
    days = settings.POSITIONS_RETENTION_DAYS if days is None else days
    cutoff = timezone.now() - timedelta(days=days)
    started = time.monotonic()
    deleted = batches = 0
    while True:
        # autocommit: every batch is its own transaction
        with connection.cursor() as cursor:
            cursor.execute(DELETE_BATCH, [cutoff, batch_size])
            count = cursor.rowcount
        if count == 0:
            break
        deleted += count
        batches += 1
        if count < batch_size:
            break
    result = PruneResult(deleted, days, cutoff, time.monotonic() - started, batches)
    log.info(
        "retention: deleted %d positions older than %d days in %d batches (%.2f s)",
        deleted, days, batches, result.seconds,
    )  # fmt: skip
    return result


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)


def record_run(result: PruneResult, trigger: str) -> None:
    """Remember the run for the ops panel. Best effort: the rows are already gone."""
    data = {
        "at": int(time.time()),
        "trigger": trigger,
        "deleted": result.deleted,
        "days": result.days,
        "cutoff": int(result.cutoff.timestamp()),
        "seconds": round(result.seconds, 3),
    }
    try:
        _client().set(settings.OPS_RETENTION_KEY, json.dumps(data))
    except redis.RedisError as exc:
        log.warning("retention run not recorded: %s", exc)


def last_run() -> dict | None:
    try:
        raw = _client().get(settings.OPS_RETENTION_KEY)
    except redis.RedisError as exc:
        log.warning("last retention run unavailable: %s", exc)
        return None
    if raw is None:
        return None
    data = json.loads(raw)
    for key in ("at", "cutoff"):
        data[key] = datetime.fromtimestamp(data[key], tz=UTC)
    return data
