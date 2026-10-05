"""The relay: Redis `positions.batch` in, Channels group `live` out (ICD §4, §5).

One asyncio loop with two jobs:
- the reader applies each batch to `LiveState` and runs the geofence check for it;
- the ticker flushes `LiveState` once per second, so however many batches arrived in that
  second, clients get at most one delta (coalescing).
State lives in memory; on start it is rebuilt from PostGIS, never from Redis (pub/sub keeps
nothing).
"""

import asyncio
import json
import logging
import time
from pathlib import Path

import redis.asyncio as aioredis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import DatabaseError, close_old_connections
from redis.exceptions import RedisError

from geofencing.tracker import GeofenceTracker

from . import queries
from .state import Aircraft, LiveState

logger = logging.getLogger("relay")

BATCH_SCHEMA = "positions.batch/v1"


def db(fn):
    """Run blocking ORM code off the event loop, on a connection that is still usable."""

    def call(*args):
        # a long-running worker has no request cycle to recycle broken connections
        close_old_connections()
        return fn(*args)

    return sync_to_async(call, thread_sensitive=True)


class Relay:
    def __init__(self, layer, heartbeat_file: Path | None = None):
        self.layer = layer
        self.heartbeat_file = heartbeat_file
        self.state = LiveState(window=settings.LIVE_WINDOW_SECONDS)
        self.tracker = GeofenceTracker()
        self.fence_names: dict[int, str] = {}
        self.connected = False

    async def load(self) -> None:
        """Rebuild in-memory state from the database (start-up)."""
        self.state.seed(await db(queries.live_aircraft)())
        await self.reload_fences()
        self.tracker.load(await db(queries.inside_pairs_from_events)())
        logger.info(
            "state loaded: %d live aircraft, %d active geofences, %d aircraft-in-fence pairs",
            len(self.state), len(self.fence_names), len(self.tracker.inside_pairs()),
        )  # fmt: skip

    async def reload_fences(self) -> None:
        self.fence_names = await db(queries.active_fence_names)()
        self.tracker.prune(set(self.fence_names))

    # --- reader ----------------------------------------------------------------------

    async def handle_batch(self, batch: dict) -> None:
        records: list[Aircraft] = batch.get("aircraft") or []
        self.state.apply(records)
        if not records:
            return
        try:
            pairs = await db(queries.fences_containing)(records)
            if any(fence_id not in self.fence_names for _, fence_id in pairs):
                await self.reload_fences()  # created after our last reload
            events = self.tracker.update([r["icao24"] for r in records], pairs)
            if not events:
                return
            by_icao = {r["icao24"]: r for r in records}
            # stored before broadcast, so the id in the message is valid for the REST API
            rows = await db(queries.store_events)([(by_icao[i], f, e) for i, f, e in events])
        except DatabaseError as exc:
            # the tracker is untouched or ahead of the DB only for this batch; the next
            # batch is checked against the real fences again
            logger.warning("geofence check skipped: %s", exc)
            return
        for row in rows:
            record = by_icao[row.icao24]
            payload = {
                "id": row.id,
                "geofence": {"id": row.geofence_id, "name": self.fence_names.get(row.geofence_id)},
                "icao24": row.icao24,
                "callsign": record.get("callsign"),
                "event": row.event,
                "ts": record["ts"],
                "lon": record["lon"],
                "lat": record["lat"],
            }
            logger.info("geofence %s %s %s", row.event, row.icao24, payload["geofence"]["name"])
            await self.layer.group_send(
                settings.LIVE_GROUP, {"type": "live.geofence_event", "event": payload}
            )

    async def dispatch(self, channel: str, data: bytes) -> None:
        try:
            message = json.loads(data)
        except ValueError:
            logger.warning("ignoring non-JSON message on %s", channel)
            return
        if channel == settings.GEOFENCES_CHANGED_CHANNEL:
            logger.info("geofences changed (%s), reloading", message.get("action"))
            await self.reload_fences()
        elif message.get("schema") != BATCH_SCHEMA:
            logger.warning("ignoring batch with schema %r", message.get("schema"))
        else:
            await self.handle_batch(message)

    # --- ticker ----------------------------------------------------------------------

    async def tick(self, now: int) -> None:
        delta = self.state.flush(now)
        if delta is None:
            return
        for icao24 in delta["removes"]:
            self.tracker.forget(icao24)
        await self.layer.group_send(settings.LIVE_GROUP, {"type": "live.delta", **delta})

    async def _ticker(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await asyncio.sleep(1 - time.time() % 1)  # on the wall-clock second
            try:
                await self.tick(int(time.time()))
            except RedisError as exc:
                logger.warning("delta not published: %s", exc)
            if self.connected and self.heartbeat_file is not None:
                self.heartbeat_file.touch()

    # --- main loop -------------------------------------------------------------------

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.load()
                break
            except DatabaseError as exc:
                logger.warning("database not ready: %s", exc)
                await asyncio.sleep(2)
        ticker = asyncio.create_task(self._ticker(stop))
        channels = (settings.POSITIONS_CHANNEL, settings.GEOFENCES_CHANGED_CHANNEL)
        while not stop.is_set():
            client = aioredis.from_url(settings.REDIS_URL)
            try:
                async with client.pubsub() as pubsub:
                    await pubsub.subscribe(*channels)
                    self.connected = True
                    logger.info("subscribed to %s", ", ".join(channels))
                    # changes published while we were away were missed
                    await self.reload_fences()
                    while not stop.is_set():
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=1.0
                        )
                        if message is not None:
                            await self.dispatch(message["channel"].decode(), message["data"])
            except (RedisError, OSError) as exc:
                self.connected = False
                logger.warning("redis unavailable, retrying: %s", exc)
                await asyncio.sleep(1)
            finally:
                await client.aclose()
        ticker.cancel()
