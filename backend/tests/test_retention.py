from datetime import timedelta

import pytest
import redis
from django.contrib.gis.geos import Point
from django.utils import timezone

from tracking.models import Position
from tracking.retention import PruneResult, last_run, prune_positions, record_run


def add_positions(*ages_days):
    now = timezone.now()
    # (icao24, ts) is unique: a second apart for equal ages
    Position.objects.bulk_create(
        Position(
            icao24="4baa0f",
            ts=now - timedelta(days=d, seconds=i),
            geom=Point(29, 41, srid=4326),
        )
        for i, d in enumerate(ages_days)
    )


@pytest.fixture
def run_key(settings):
    """Empty before and after (conftest points the key away from the stack's own)."""
    client = redis.Redis.from_url(settings.REDIS_URL)
    client.delete(settings.OPS_RETENTION_KEY)
    yield settings.OPS_RETENTION_KEY
    client.delete(settings.OPS_RETENTION_KEY)


@pytest.mark.django_db
def test_deletes_only_rows_older_than_the_retention():
    add_positions(1, 6, 8, 30)
    result = prune_positions(days=7)
    assert result.deleted == 2
    assert Position.objects.count() == 2
    assert not Position.objects.filter(ts__lt=result.cutoff).exists()
    assert result.days == 7
    assert timezone.now() - timedelta(days=7) - result.cutoff < timedelta(seconds=5)


@pytest.mark.django_db
def test_deletes_in_batches_until_nothing_is_left():
    add_positions(*[10] * 7, 1)
    result = prune_positions(days=7, batch_size=3)  # 3 + 3 + 1
    assert result.deleted == 7
    assert result.batches == 3
    assert Position.objects.count() == 1


@pytest.mark.django_db
def test_nothing_to_delete(settings):
    settings.POSITIONS_RETENTION_DAYS = 7
    add_positions(1)
    result = prune_positions()
    assert result.deleted == 0 and result.batches == 0 and result.days == 7


def test_last_run_round_trip(run_key):
    assert last_run() is None
    result = PruneResult(deleted=12, days=7, cutoff=timezone.now(), seconds=0.25, batches=1)
    record_run(result, trigger="manual")
    got = last_run()
    assert got["deleted"] == 12 and got["days"] == 7 and got["trigger"] == "manual"
    assert got["seconds"] == 0.25
    assert abs((got["at"] - timezone.now()).total_seconds()) < 5
    assert got["cutoff"] == result.cutoff.replace(microsecond=0)


def test_last_run_survives_a_redis_outage(settings):
    settings.REDIS_URL = "redis://127.0.0.1:9/0"  # discard port: refused
    result = PruneResult(deleted=1, days=7, cutoff=timezone.now(), seconds=0.1, batches=1)
    record_run(result, trigger="schedule")  # must not raise: the delete already happened
    assert last_run() is None
