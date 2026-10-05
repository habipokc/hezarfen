"""Per-connection outbound queue: the consumer's backpressure policy (ICD §6.4).

Channel-layer handlers only push here and return at once; a single sender task pops and
awaits the socket. A slow client therefore never stalls the handlers, and what piles up
for it stays bounded:

- deltas merge into one pending delta (size bounded by the number of live aircraft);
- a snapshot request supersedes the pending delta;
- other messages (geofence events, heartbeats, errors) queue FIFO and are never dropped;
  past `max_messages` the caller should give up on the client and close the socket.
"""

import asyncio
from collections import deque
from typing import Any

from .state import Delta, merge_deltas

SNAPSHOT, MESSAGE, DELTA = "snapshot", "message", "delta"


class Outbox:
    def __init__(self, max_messages: int = 1000):
        self.max_messages = max_messages
        self._snapshot = False
        self._messages: deque[dict[str, Any]] = deque()
        self._delta: Delta | None = None
        self._wake = asyncio.Event()

    def request_snapshot(self) -> None:
        self._snapshot = True
        self._delta = None
        self._wake.set()

    def push_delta(self, delta: Delta) -> None:
        self._delta = delta if self._delta is None else merge_deltas(self._delta, delta)
        self._wake.set()

    def push(self, message: dict[str, Any]) -> bool:
        """Queue a message; False once the queue is over its cap (the client is stuck)."""
        self._messages.append(message)
        self._wake.set()
        return len(self._messages) <= self.max_messages

    def pop(self) -> tuple[str, Any] | None:
        if self._snapshot:
            self._snapshot = False
            return SNAPSHOT, None
        if self._messages:
            return MESSAGE, self._messages.popleft()
        if self._delta is not None:
            delta, self._delta = self._delta, None
            return DELTA, delta
        return None

    async def get(self) -> tuple[str, Any]:
        while (item := self.pop()) is None:
            self._wake.clear()
            await self._wake.wait()
        return item
