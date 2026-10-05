import { useEffect, useState } from 'react'
import { requestJson } from '../lib/api'
import { elevationKey } from '../lib/terrain'

const MAX_CACHED = 500

interface ElevationResponse {
  elevation_m: number | null
}
type Cache = ReadonlyMap<string, number | null>

/**
 * Terrain elevation under a point from `/api/terrain/elevation`, cached per ~100 m cell so a
 * cruising aircraft costs one request every few seconds. Moving to a new cell aborts the
 * request for the old one (at 60× playback the cell changes faster than requests finish).
 */
export function useElevation(lon: number | null, lat: number | null) {
  const key = lon === null || lat === null ? null : elevationKey(lon, lat)
  const [cache, setCache] = useState<Cache>(() => new Map())
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (key === null || cache.has(key)) return
    const controller = new AbortController()
    const [qlon, qlat] = key.split(',')
    requestJson<ElevationResponse>(`/api/terrain/elevation?lon=${qlon}&lat=${qlat}`, { signal: controller.signal })
      .then((body) => {
        setError(null)
        setCache((prev) => {
          const next = new Map(prev)
          if (next.size >= MAX_CACHED) next.delete(next.keys().next().value as string)
          return next.set(key, body.elevation_m)
        })
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : String(err))
      })
    return () => controller.abort()
  }, [key, cache])

  const known = key !== null && cache.has(key)
  return { elevation: known ? (cache.get(key) ?? null) : null, known, error: known ? null : error }
}
