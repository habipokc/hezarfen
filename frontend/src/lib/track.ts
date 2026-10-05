import type { LineCollection, LonLat } from './playback'
import type { Aircraft } from './types'

/** `GET /api/aircraft/{icao24}/track` (ICD §7.2). */
export interface TrackResponse {
  type: 'Feature'
  geometry: { type: 'LineString'; coordinates: LonLat[] } | null
  properties: { icao24: string; callsign: string | null; start_ts: number | null; end_ts: number | null; points: number }
}

export interface Track {
  coords: LonLat[]
  endTs: number | null
}

export const EMPTY_TRACK: Track = { coords: [], endTs: null }

export function trackFromResponse(body: TrackResponse): Track {
  return { coords: body.geometry?.coordinates ?? [], endTs: body.properties.end_ts }
}

/** Append a live fix that is newer than the track; unchanged input comes back as the same object. */
export function extendTrack(track: Track, a: Aircraft): Track {
  if (track.endTs !== null && a.ts <= track.endTs) return track
  return { coords: [...track.coords, [a.lon, a.lat]], endTs: a.ts }
}

export function trackLine(coords: LonLat[]): LineCollection<Record<string, never>> {
  return {
    type: 'FeatureCollection',
    features: coords.length < 2 ? [] : [{ type: 'Feature', geometry: { type: 'LineString', coordinates: coords }, properties: {} }],
  }
}
