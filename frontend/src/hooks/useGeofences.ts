import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useCallback, useEffect, useRef, useState } from 'react'
import { requestJson } from '../lib/api'
import type { LonLat } from '../lib/playback'
import { GEOFENCES_SOURCE } from '../map/layers'

export interface GeofenceProperties {
  id: number
  name: string
  kind: string
  active: boolean
  created_at: string
}
export interface GeofenceFeature {
  type: 'Feature'
  id?: number
  geometry: { type: 'Polygon'; coordinates: LonLat[][] }
  properties: GeofenceProperties
}
interface GeofenceCollection {
  type: 'FeatureCollection'
  features: GeofenceFeature[]
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }
const BLINKS = 3
const BLINK_MS = 350

/**
 * Geofence zones over REST (ICD §7.2). Every change reloads the list and pushes it into the
 * map source; the relay hears about it on its own through `geofences.changed`.
 */
export function useGeofences(mapRef: RefObject<MapLibreMap | null>, ready: boolean) {
  const [zones, setZones] = useState<GeofenceFeature[]>([])
  const [error, setError] = useState<string | null>(null)
  const blinkTimers = useRef(new Map<number, ReturnType<typeof setTimeout>[]>())

  const show = useCallback(
    (fc: GeofenceCollection) => {
      setZones(fc.features)
      mapRef.current?.getSource<GeoJSONSource>(GEOFENCES_SOURCE)?.setData(fc)
    },
    [mapRef],
  )
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e))

  const reload = useCallback(async () => {
    try {
      show(await requestJson<GeofenceCollection>('/api/geofences/'))
    } catch (e) {
      fail(e)
    }
  }, [show])

  useEffect(() => {
    if (!ready) return
    const controller = new AbortController()
    requestJson<GeofenceCollection>('/api/geofences/', { signal: controller.signal })
      .then(show)
      .catch((e: unknown) => controller.signal.aborted || fail(e))
    return () => controller.abort()
  }, [ready, show])

  useEffect(() => {
    const timers = blinkTimers.current
    return () => {
      for (const list of timers.values()) list.forEach(clearTimeout)
      timers.clear()
    }
  }, [])

  /** POST a drawn ring; resolves to an error message, or null on success. */
  const create = useCallback(
    async (name: string, ring: LonLat[]): Promise<string | null> => {
      try {
        await requestJson('/api/geofences/', {
          method: 'POST',
          headers: JSON_HEADERS,
          body: JSON.stringify({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: { name } }),
        })
        await reload()
        return null
      } catch (e) {
        return e instanceof Error ? e.message : String(e)
      }
    },
    [reload],
  )

  const setActive = useCallback(
    async (id: number, active: boolean) => {
      setError(null)
      try {
        await requestJson(`/api/geofences/${id}/`, {
          method: 'PATCH',
          headers: JSON_HEADERS,
          body: JSON.stringify({ properties: { active } }),
        })
      } catch (e) {
        fail(e)
      }
      await reload()
    },
    [reload],
  )

  const remove = useCallback(
    async (id: number) => {
      setError(null)
      try {
        await requestJson(`/api/geofences/${id}/`, { method: 'DELETE' })
      } catch (e) {
        fail(e)
      }
      await reload()
    },
    [reload],
  )

  /** Blink a zone a few times through feature-state (paint-only, no data change). */
  const blink = useCallback(
    (id: number) => {
      const map = mapRef.current
      if (!map) return
      const timers = blinkTimers.current
      timers.get(id)?.forEach(clearTimeout)
      const set = (flash: boolean) => {
        try {
          map.setFeatureState({ source: GEOFENCES_SOURCE, id }, { flash })
        } catch {
          // map removed meanwhile
        }
      }
      const list: ReturnType<typeof setTimeout>[] = []
      for (let i = 0; i < BLINKS * 2; i++) list.push(setTimeout(() => set(i % 2 === 0), i * BLINK_MS))
      list.push(setTimeout(() => (set(false), timers.delete(id)), BLINKS * 2 * BLINK_MS))
      timers.set(id, list)
    },
    [mapRef],
  )

  return { zones, error, reload, create, setActive, remove, blink }
}
