import { useEffect, useState } from 'react'
import type { AircraftDetail } from '../lib/types'

const REFRESH_MS = 15_000

type Result = { icao24: string; detail: AircraftDetail | null; error: string | null }

/**
 * REST detail (province, nearest airport, origin country) for the selected aircraft,
 * refreshed every 15 s while it stays selected. The result is keyed by icao24, so a stale
 * response for the previous selection is never shown.
 */
export function useAircraftDetail(icao24: string | null): { detail: AircraftDetail | null; error: string | null } {
  const [result, setResult] = useState<Result | null>(null)

  useEffect(() => {
    if (!icao24) return
    const controller = new AbortController()
    const load = () =>
      fetch(`/api/aircraft/${icao24}/`, { signal: controller.signal })
        .then(async (r) => {
          if (!r.ok) throw new Error(r.status === 404 ? 'not found' : `HTTP ${r.status}`)
          const body = (await r.json()) as { properties: AircraftDetail }
          setResult({ icao24, detail: body.properties, error: null })
        })
        .catch((err: unknown) => {
          if (!controller.signal.aborted) setResult((prev) => ({ icao24, detail: prev?.icao24 === icao24 ? prev.detail : null, error: String(err) }))
        })
    void load()
    const timer = setInterval(() => void load(), REFRESH_MS)
    return () => {
      controller.abort()
      clearInterval(timer)
    }
  }, [icao24])

  if (!icao24 || result?.icao24 !== icao24) return { detail: null, error: null }
  return { detail: result.detail, error: result.error }
}
