"""Geofence enter/exit state machine. Pure: no Django, no I/O.

State per (aircraft, fence) pair is just "inside" or not. Each batch tells us, for the
aircraft in it, which fences contain them now; the difference to the stored state is the
event list. Aircraft missing from a batch keep their state: a skipped report is not an exit.
"""

from collections.abc import Iterable

ENTER, EXIT = "enter", "exit"

Pair = tuple[str, int]  # (icao24, geofence id)
Event = tuple[str, int, str]  # (icao24, geofence id, ENTER | EXIT)


class GeofenceTracker:
    def __init__(self):
        self._inside: dict[str, set[int]] = {}

    def update(self, seen: Iterable[str], inside_pairs: Iterable[Pair]) -> list[Event]:
        now: dict[str, set[int]] = {}
        for icao24, fence_id in inside_pairs:
            now.setdefault(icao24, set()).add(fence_id)
        events: list[Event] = []
        for icao24 in sorted(set(seen)):
            before = self._inside.get(icao24, set())
            after = now.get(icao24, set())
            events += [(icao24, f, EXIT) for f in sorted(before - after)]
            events += [(icao24, f, ENTER) for f in sorted(after - before)]
            if after:
                self._inside[icao24] = after
            else:
                self._inside.pop(icao24, None)
        return events

    def forget(self, icao24: str) -> None:
        """The aircraft timed out: we don't know where it went, so no exit event."""
        self._inside.pop(icao24, None)

    def prune(self, active_ids: set[int]) -> None:
        """Drop pairs of fences that were deleted or deactivated."""
        for icao24 in list(self._inside):
            kept = self._inside[icao24] & active_ids
            if kept:
                self._inside[icao24] = kept
            else:
                del self._inside[icao24]

    def load(self, pairs: Iterable[Pair]) -> None:
        """Restore state after a restart (from the last stored event of each pair)."""
        self._inside.clear()
        for icao24, fence_id in pairs:
            self._inside.setdefault(icao24, set()).add(fence_id)

    def inside_pairs(self) -> set[Pair]:
        return {(i, f) for i, fences in self._inside.items() for f in fences}
