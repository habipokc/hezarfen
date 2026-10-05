"""Relay worker (Phase 0 placeholder).

Phase 4 turns this into the real relay: subscribe to Redis `positions.batch`,
run geofence checks and broadcast deltas over Channels. For now it only proves the
process can reach Redis and stays alive, which the compose healthcheck observes
through the heartbeat file.
"""

import logging
import signal
import time
from pathlib import Path

import redis
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger("relay")

HEARTBEAT_FILE = Path("/tmp/relay-heartbeat")
HEARTBEAT_INTERVAL_SECONDS = 5


class Command(BaseCommand):
    help = "Relay positions from Redis to WebSocket clients (placeholder)."

    def handle(self, *args, **options):
        stopping = False

        def stop(signum, frame):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

        client = redis.Redis.from_url(settings.REDIS_URL)
        logger.info("relay started (placeholder), redis=%s", settings.REDIS_URL)
        while not stopping:
            try:
                client.ping()
                HEARTBEAT_FILE.touch()
            except redis.RedisError as exc:
                # no heartbeat -> healthcheck turns unhealthy, which is what we want
                logger.warning("redis unavailable: %s", exc)
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
        logger.info("relay stopped")
