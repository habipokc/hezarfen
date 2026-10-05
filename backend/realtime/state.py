"""Live picture of the sky and per-client deltas (ICD §5, §6). Pure: no Django, no I/O.

An `Aircraft` is the ICD §6.2 object as a dict; `Delta` is `{ts, upserts, removes}`.
"""

import math
from collections.abc import Iterable
from typing import Any

Aircraft = dict[str, Any]
Delta = dict[str, Any]
BBox = tuple[float, float, float, float]


class LiveState:
    """Relay-side state: the latest record per aircraft and what changed since the last flush.

    Batches are applied as they arrive; `flush` runs once per second and turns everything
    that changed in between into a single delta (coalescing).
    """

    def __init__(self, window: int = 60):
        self.window = window
        self._aircraft: dict[str, Aircraft] = {}
        self._pending: set[str] = set()

    def __contains__(self, icao24: str) -> bool:
        return icao24 in self._aircraft

    def __len__(self) -> int:
        return len(self._aircraft)

    def seed(self, aircraft: Iterable[Aircraft]) -> None:
        """Known on start-up (clients get them from the snapshot), so not pending."""
        for record in aircraft:
            self._aircraft[record["icao24"]] = record

    def apply(self, records: Iterable[Aircraft]) -> None:
        for record in records:
            icao24 = record["icao24"]
            current = self._aircraft.get(icao24)
            if current is not None and (current == record or current["ts"] > record["ts"]):
                continue  # replayed or out-of-order record
            self._aircraft[icao24] = record
            self._pending.add(icao24)

    def flush(self, now: int) -> Delta | None:
        cutoff = now - self.window
        removes = sorted(i for i, a in self._aircraft.items() if a["ts"] < cutoff)
        for icao24 in removes:
            del self._aircraft[icao24]
            self._pending.discard(icao24)
        upserts = [self._aircraft[i] for i in sorted(self._pending)]
        self._pending.clear()
        if not upserts and not removes:
            return None
        return {"ts": now, "upserts": upserts, "removes": removes}


def merge_deltas(older: Delta, newer: Delta) -> Delta:
    """One delta equivalent to applying `older` then `newer`; the later word on an aircraft wins."""
    upserts = {a["icao24"]: a for a in older["upserts"]}
    removes = set(older["removes"])
    for icao24 in newer["removes"]:
        upserts.pop(icao24, None)
        removes.add(icao24)
    for record in newer["upserts"]:
        upserts[record["icao24"]] = record
        removes.discard(record["icao24"])
    return {"ts": newer["ts"], "upserts": list(upserts.values()), "removes": sorted(removes)}


def in_bbox(record: Aircraft, bbox: BBox) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= record["lon"] <= max_lon and min_lat <= record["lat"] <= max_lat


def filter_delta(delta: Delta, bbox: BBox, known: set[str]) -> tuple[list[Aircraft], list[str]]:
    """Cut the global delta down to one client's view. Updates `known` (what the client holds)."""
    upserts, removes = [], []
    for record in delta["upserts"]:
        icao24 = record["icao24"]
        if in_bbox(record, bbox):
            upserts.append(record)
            known.add(icao24)
        elif icao24 in known:
            removes.append(icao24)  # flew out of the client's view
            known.discard(icao24)
    for icao24 in delta["removes"]:
        if icao24 in known:
            removes.append(icao24)
            known.discard(icao24)
    return upserts, removes


def parse_subscribe_bbox(value: Any) -> BBox:
    """Validate `subscribe.bbox` (ICD §6.1); raises ValueError with a client-facing message."""
    hint = "bbox must be [minLon, minLat, maxLon, maxLat] with min < max"
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(hint)
    # bool is an int subclass; `true` is not a coordinate
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in value):
        raise ValueError(hint)
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in value)
    if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
        raise ValueError(hint)
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError(hint)
    return min_lon, min_lat, max_lon, max_lat
