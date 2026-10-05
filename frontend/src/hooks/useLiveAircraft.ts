import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { EVENT_LIST_SIZE, mergeEvents } from '../lib/events'
import { LiveStore } from '../lib/liveStore'
import { type Throttled, throttle } from '../lib/throttle'
import type { Aircraft, Bbox, GeofenceEvent, ServerMessage } from '../lib/types'
import { AIRCRAFT_SOURCE } from '../map/layers'
import { liveSocketUrl, useLiveSocket } from './useLiveSocket'

const REDRAW_MS = 1000

/**
 * Live aircraft for the current viewport. Messages patch a plain `Map` (no React state per
 * aircraft); at most once a second the whole collection goes to MapLibre with `setData`
 * and a `version` counter tells React that derived values (count, selected) changed.
 */
export function useLiveAircraft(mapRef: RefObject<MapLibreMap | null>, ready: boolean, bbox: Bbox | null, selectedId: string | null) {
  const [store] = useState(() => new LiveStore())
  const [version, setVersion] = useState(0)
  const [events, setEvents] = useState<GeofenceEvent[]>([])

  const redrawRef = useRef<Throttled | null>(null)

  useEffect(() => {
    const redraw = throttle(() => {
      mapRef.current?.getSource<GeoJSONSource>(AIRCRAFT_SOURCE)?.setData(store.toFeatureCollection())
      setVersion((v) => v + 1)
    }, REDRAW_MS)
    redrawRef.current = redraw
    // data may arrive before the map has finished loading its style
    if (ready) redraw()
    return () => {
      redraw.cancel()
      redrawRef.current = null
    }
  }, [mapRef, store, ready])

  // recent history from REST so the list is not empty until the next live event
  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/geofence-events?page_size=${EVENT_LIST_SIZE}`, { signal: controller.signal })
      .then((r) => (r.ok ? (r.json() as Promise<{ results: GeofenceEvent[] }>) : { results: [] }))
      .then(({ results }) => setEvents((live) => mergeEvents(live, results)))
      .catch(() => {}) // live events still arrive; history is a nicety
    return () => controller.abort()
  }, [])

  const onMessage = useCallback(
    (m: ServerMessage) => {
      switch (m.type) {
        case 'snapshot':
          store.applySnapshot(m.aircraft)
          redrawRef.current?.()
          break
        case 'delta':
          store.applyDelta(m.upserts, m.removes)
          redrawRef.current?.()
          break
        case 'geofence_event': {
          const { type: _type, ...event } = m
          setEvents((list) => mergeEvents(list, [event]))
          break
        }
        case 'error':
          console.warn('live socket error', m.code, m.message)
          break
        case 'heartbeat':
          break
      }
    },
    [store],
  )

  const socket = useLiveSocket(liveSocketUrl(), bbox, onMessage)

  // `version` is the dependency that makes reading the mutable store here safe
  const selected: Aircraft | null = useMemo(
    () => (selectedId ? (store.get(selectedId) ?? null) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [store, selectedId, version],
  )

  return { socket, count: store.size, selected, events, version }
}
