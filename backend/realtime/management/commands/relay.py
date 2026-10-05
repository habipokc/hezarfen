"""Run the relay worker (see realtime/relay.py)."""

import asyncio
import logging
import signal
from pathlib import Path

from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand

from realtime.relay import Relay

logger = logging.getLogger("relay")

# the compose healthcheck checks this file's age; it is touched every second while the
# relay is subscribed to Redis
HEARTBEAT_FILE = Path("/tmp/relay-heartbeat")


class Command(BaseCommand):
    help = "Relay positions.batch from Redis to WebSocket clients and detect geofence events."

    def handle(self, *args, **options):
        asyncio.run(self.main())

    async def main(self):
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        logger.info("relay starting")
        await Relay(get_channel_layer(), HEARTBEAT_FILE).run(stop)
        logger.info("relay stopped")
