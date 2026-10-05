import os
import time

import pytest
from django.core.management import call_command

from ops.management.commands import maintenance
from tracking.retention import last_run


@pytest.fixture
def heartbeat(tmp_path, monkeypatch):
    path = tmp_path / "heartbeat"
    monkeypatch.setattr(maintenance, "HEARTBEAT_FILE", path)
    return path


def test_check_fails_without_a_heartbeat(heartbeat):
    with pytest.raises(SystemExit) as exc:
        call_command("maintenance", "--check")
    assert exc.value.code == 1


def test_check_passes_with_a_fresh_heartbeat(heartbeat):
    heartbeat.touch()
    with pytest.raises(SystemExit) as exc:
        call_command("maintenance", "--check")
    assert exc.value.code == 0


def test_check_fails_when_the_loop_is_stuck(heartbeat, settings):
    settings.RETENTION_INTERVAL_SECONDS = 60
    heartbeat.touch()
    old = time.time() - maintenance.allowed_silence() - 1
    os.utime(heartbeat, (old, old))
    with pytest.raises(SystemExit) as exc:
        call_command("maintenance", "--check")
    assert exc.value.code == 1


# transaction=True: close_old_connections() closes a connection inside an atomic block,
# which is where ordinary django_db tests run
@pytest.mark.django_db(transaction=True)
def test_a_scheduled_run_is_recorded(heartbeat, run_key_cleanup):
    maintenance.retention()
    assert last_run()["trigger"] == "schedule"


@pytest.fixture
def run_key_cleanup(settings):
    import redis

    client = redis.Redis.from_url(settings.REDIS_URL)
    client.delete(settings.OPS_RETENTION_KEY)
    yield
    client.delete(settings.OPS_RETENTION_KEY)
