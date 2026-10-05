import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useEffect, useEffectEvent, useRef } from 'react'
import { requestJson } from '../lib/api'
import { EMPTY_TRACK, type Track, type TrackResponse, extendTrack, trackFromResponse, trackLine } from '../lib/track'
import type { Aircraft } from '../lib/types'
import { TRACK_SOURCE } from '../map/layers'

/**
 * Live mode: the selected aircraft's last 30 minutes from REST, extended with every live fix
 * that arrives afterwards. The track lives in a ref and goes straight to the map source;
 * nothing in React renders it.
 */
export function useTrack(
  mapRef: RefObject<MapLibreMap | null>,
  ready: boolean,
  icao24: string | null,
  live: Aircraft | null,
  enabled: boolean,
) {
  const trackRef = useRef<Track>(EMPTY_TRACK)
  const latestLive = useEffectEvent(() => live)

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !enabled || !icao24) return
    const source = () => map.getSource<GeoJSONSource>(TRACK_SOURCE)
    const controller = new AbortController()
    trackRef.current = EMPTY_TRACK
    requestJson<TrackResponse>(`/api/aircraft/${icao24}/track`, { signal: controller.signal })
      .then((body) => {
        // a live fix that arrived while the request was in flight is newer than the REST track
        const latest = latestLive()
        const base = trackFromResponse(body)
        const track = latest?.icao24 === icao24 ? extendTrack(base, latest) : base
        trackRef.current = track
        source()?.setData(trackLine(track.coords))
      })
      .catch(() => {}) // no track is fine: the live extension still draws from the next fix
    return () => {
      controller.abort()
      trackRef.current = EMPTY_TRACK
      try {
        source()?.setData(trackLine([]))
      } catch {
        // map already removed
      }
    }
  }, [mapRef, ready, icao24, enabled])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !enabled || !live || live.icao24 !== icao24) return
    const next = extendTrack(trackRef.current, live)
    if (next === trackRef.current) return
    trackRef.current = next
    map.getSource<GeoJSONSource>(TRACK_SOURCE)?.setData(trackLine(next.coords))
  }, [mapRef, ready, icao24, live, enabled])
}
