import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useEffect, useMemo, useRef, useState } from 'react'
import { EVENT_LIST_SIZE, mergeEvents } from '../lib/events'
import { LiveStore } from '../lib/liveStore'
import { Tails } from '../lib/tails'
import { type Throttled, throttle } from '../lib/throttle'
import type { Aircraft, Bbox, GeofenceEvent, ServerMessage } from '../lib/types'
import { AIRCRAFT_SOURCE, TAILS_SOURCE } from '../map/layers'
import { liveSocketUrl, useLiveSocket } from './useLiveSocket'

const REDRAW_MS = 1000

/**
 * Live aircraft for the current viewport. Messages patch a plain `Map` (no React state per
 * aircraft); at most once a second the whole collection goes to MapLibre with `setData`
 * and a `version` counter tells React that derived values (count, selected) changed.
 * The same redraw feeds the 2-minute tails. `enabled = false` (history mode) closes the
 * socket and leaves both sources to the player.
 */
export function useLiveAircraft(
  mapRef: RefObject<MapLibreMap | null>,
  ready: boolean,
  bbox: Bbox | null,
  selectedId: string | null,
  enabled: boolean,
  onLiveEvent: (event: GeofenceEvent) => void,
) {
  const [store] = useState(() => new LiveStore())
  const [tails] = useState(() => new Tails())
  const [version, setVersion] = useState(0)
  const [events, setEvents] = useState<GeofenceEvent[]>([])

  const redrawRef = useRef<Throttled | null>(null)

  useEffect(() => {
    if (!enabled) return
    const redraw = throttle(() => {
      const map = mapRef.current
      const collection = store.toFeatureCollection()
      tails.sync(collection.features.map((f) => f.properties))
      map?.getSource<GeoJSONSource>(AIRCRAFT_SOURCE)?.setData(collection)
      map?.getSource<GeoJSONSource>(TAILS_SOURCE)?.setData(tails.toFeatureCollection())
      setVersion((v) => v + 1)
    }, REDRAW_MS)
    redrawRef.current = redraw
    // data may arrive before the map has finished loading its style
    if (ready) redraw()
    return () => {
      redraw.cancel()
      redrawRef.current = null
      // leaving live mode: what we hold is about to be stale; the next snapshot refills it
      store.clear()
      tails.clear()
    }
  }, [mapRef, store, tails, ready, enabled])

  // recent history from REST so the list is not empty until the next live event
  useEffect(() => {
    const controller = new AbortController()
    fetch(`/api/geofence-events?page_size=${EVENT_LIST_SIZE}`, { signal: controller.signal })
      .then((r) => (r.ok ? (r.json() as Promise<{ results: GeofenceEvent[] }>) : { results: [] }))
      .then(({ results }) => setEvents((live) => mergeEvents(live, results)))
      .catch(() => {}) // live events still arrive; history is a nicety
    return () => controller.abort()
  }, [])

  // useLiveSocket reads this through an effect event: it may change on every render
  const onMessage = (m: ServerMessage) => {
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
        onLiveEvent(event)
        break
      }
      case 'error':
        console.warn('live socket error', m.code, m.message)
        break
      case 'heartbeat':
        break
    }
  }

  const socket = useLiveSocket(liveSocketUrl(), bbox, onMessage, enabled)

  // `version` is the dependency that makes reading the mutable store here safe
  const selected: Aircraft | null = useMemo(
    () => (selectedId ? (store.get(selectedId) ?? null) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [store, selectedId, version],
  )

  return { socket, count: store.size, selected, events, version }
}
