"""Periodic maintenance worker: position retention every RETENTION_INTERVAL_SECONDS.

Runs as its own compose service (`maintenance`), not inside the relay: a large DELETE would
otherwise share the relay's single database thread with the geofence checks.
"""

import logging
import signal
import sys
import threading
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from ops.schedule import run_every
from tracking.retention import prune_positions, record_run

logger = logging.getLogger("maintenance")

# touched after every run; `--check` (the compose healthcheck) reads its age
HEARTBEAT_FILE = Path("/tmp/maintenance-heartbeat")
# let the stack settle before the first delete after a (re)start
FIRST_DELAY_SECONDS = 30
# a run may take a while on a big table before the heartbeat counts as stale
RUN_GRACE_SECONDS = 600


def allowed_silence() -> float:
    return FIRST_DELAY_SECONDS + settings.RETENTION_INTERVAL_SECONDS + RUN_GRACE_SECONDS


def retention() -> None:
    # a worker has no request cycle that would recycle a connection broken since the last run
    close_old_connections()
    record_run(prune_positions(), trigger="schedule")


class Command(BaseCommand):
    help = "Run periodic maintenance (position retention) until SIGTERM."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="healthcheck: exit 0 if alive")

    def handle(self, *args, check=False, **options):
        if check:
            try:
                age = time.time() - HEARTBEAT_FILE.stat().st_mtime
            except OSError:
                sys.exit(1)
            sys.exit(0 if age < allowed_silence() else 1)

        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
        interval = settings.RETENTION_INTERVAL_SECONDS
        logger.info(
            "maintenance starting: retention %d days, every %d s",
            settings.POSITIONS_RETENTION_DAYS, interval,
        )  # fmt: skip
        HEARTBEAT_FILE.touch()
        run_every(
            retention, interval, stop, first_delay=FIRST_DELAY_SECONDS,
            after_run=HEARTBEAT_FILE.touch,
        )  # fmt: skip
        logger.info("maintenance stopped")
