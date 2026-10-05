"""`/ws/live/` (ICD §6): snapshot on subscribe, bbox-filtered deltas, geofence events."""

import asyncio
import json
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .outbox import DELTA, SNAPSHOT, Outbox
from .queries import live_aircraft
from .state import filter_delta, parse_subscribe_bbox

logger = logging.getLogger("realtime")

CLOSE_TRY_AGAIN_LATER = 1013  # RFC 6455 registry: server overloaded / client too slow


def dumps(message: dict) -> str:
    return json.dumps(message, separators=(",", ":"))


class LiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.bbox = None
        self.known: set[str] = set()  # icao24s this client currently holds
        self.outbox = Outbox(max_messages=settings.WS_MAX_QUEUED_MESSAGES)
        self.joined = False
        await self.accept()
        # the only coroutine that awaits the socket; everything else goes through the outbox
        self.tasks = [
            asyncio.create_task(self._sender()),
            asyncio.create_task(self._heartbeat()),
        ]

    async def disconnect(self, code):
        for task in getattr(self, "tasks", []):
            task.cancel()
        if getattr(self, "joined", False):
            await self.channel_layer.group_discard(settings.LIVE_GROUP, self.channel_name)

    # --- client -> server -----------------------------------------------------------

    async def receive(self, text_data=None, bytes_data=None):
        try:
            message = json.loads(text_data if text_data is not None else bytes_data)
        except ValueError, TypeError:
            await self._error("invalid_json", "message must be a JSON object")
            return
        if not isinstance(message, dict) or message.get("type") != "subscribe":
            await self._error("unknown_type", "the only client message is 'subscribe'")
            return
        try:
            self.bbox = parse_subscribe_bbox(message.get("bbox"))
        except ValueError as exc:
            await self._error("invalid_bbox", str(exc))
            return
        if not self.joined:
            await self.channel_layer.group_add(settings.LIVE_GROUP, self.channel_name)
            self.joined = True
        self.outbox.request_snapshot()

    # --- channel layer -> client (handlers must not await the socket) --------------

    async def live_delta(self, event):
        self.outbox.push_delta(
            {"ts": event["ts"], "upserts": event["upserts"], "removes": event["removes"]}
        )

    async def live_geofence_event(self, event):
        await self._queue({"type": "geofence_event", **event["event"]})

    # --- internals -------------------------------------------------------------------

    async def _queue(self, message: dict) -> None:
        if not self.outbox.push(message):
            logger.warning("client %s too slow, closing", self.channel_name)
            await self.close(code=CLOSE_TRY_AGAIN_LATER)

    async def _error(self, code: str, message: str) -> None:
        await self._queue({"type": "error", "code": code, "message": message})

    async def _heartbeat(self):
        while True:
            await asyncio.sleep(settings.WS_HEARTBEAT_SECONDS)
            await self._queue({"type": "heartbeat", "ts": int(time.time())})

    async def _sender(self):
        try:
            while True:
                kind, payload = await self.outbox.get()
                if kind == SNAPSHOT:
                    await self._send_snapshot()
                elif kind == DELTA:
                    upserts, removes = filter_delta(payload, self.bbox, self.known)
                    if upserts or removes:  # empty deltas are not sent (ICD §6.2)
                        await self.send(
                            dumps(
                                {
                                    "type": "delta",
                                    "ts": payload["ts"],
                                    "upserts": upserts,
                                    "removes": removes,
                                }
                            )
                        )
                else:
                    await self.send(dumps(payload))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("sender failed for %s", self.channel_name)
            await self.close(code=1011)

    async def _send_snapshot(self):
        aircraft = await database_sync_to_async(live_aircraft)(self.bbox)
        self.known = {a["icao24"] for a in aircraft}
        await self.send(dumps({"type": "snapshot", "ts": int(time.time()), "aircraft": aircraft}))
