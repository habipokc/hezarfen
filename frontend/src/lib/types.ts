// Wire types from docs/ICD.md. Units: metres, m/s, degrees, Unix seconds; coordinates lon, lat.

/** `[minLon, minLat, maxLon, maxLat]` (ICD §2). */
export type Bbox = [number, number, number, number]

/** ICD §6.2 — shared by `snapshot`, `delta` and REST `properties`. */
export interface Aircraft {
  icao24: string
  callsign: string | null
  lon: number
  lat: number
  baro_alt: number | null
  geo_alt: number | null
  velocity: number | null
  heading: number | null
  vrate: number | null
  on_ground: boolean
  squawk: string | null
  category: number | null
  ts: number
}

/** ICD §6.3 (REST returns the same object without `type`). */
export interface GeofenceEvent {
  id: number
  geofence: { id: number; name: string }
  icao24: string
  callsign: string | null
  event: 'enter' | 'exit'
  ts: number
  lon: number
  lat: number
}

/** Server → client frames of `/ws/live/`, discriminated by `type`. */
export type ServerMessage =
  | { type: 'snapshot'; ts: number; aircraft: Aircraft[] }
  | { type: 'delta'; ts: number; upserts: Aircraft[]; removes: string[] }
  | ({ type: 'geofence_event' } & GeofenceEvent)
  | { type: 'heartbeat'; ts: number }
  | { type: 'error'; code: string; message: string }

/** `GET /api/aircraft/{icao24}/` properties (ICD §7.2). */
export interface AircraftDetail extends Aircraft {
  origin_country: string | null
  source: string
  province: string | null
  nearest_airport: { ident: string; name: string; distance_m: number } | null
}

export interface AircraftFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: Aircraft
}
