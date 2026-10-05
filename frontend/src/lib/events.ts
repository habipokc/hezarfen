import type { GeofenceEvent } from './types'

export const EVENT_LIST_SIZE = 8

/** Newest first (ids grow with time), unique by id, capped: REST history and live events overlap. */
export function mergeEvents(current: GeofenceEvent[], incoming: GeofenceEvent[]): GeofenceEvent[] {
  const byId = new Map([...current, ...incoming].map((e) => [e.id, e]))
  return [...byId.values()].sort((a, b) => b.id - a.id).slice(0, EVENT_LIST_SIZE)
}
