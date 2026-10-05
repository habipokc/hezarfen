import type { LonLat } from './playback'

/** Below this height above ground an airborne aircraft away from airports is "low". */
export const LOW_FLIGHT_AGL_M = 300
/** Approaches and departures are low by design: closer than this to any airport is not "low". */
export const AIRPORT_RADIUS_M = 10_000

export interface AboveGround {
  agl: number
  /** Which altitude it came from: GNSS (`geo`) is the right one, barometric only a fallback. */
  basis: 'geo' | 'baro'
}

/** Height above the terrain: geometric altitude minus the DEM elevation under the aircraft. */
export function aboveGround(
  a: { geo_alt: number | null; baro_alt: number | null },
  elevation: number | null,
): AboveGround | null {
  if (elevation === null) return null
  if (a.geo_alt !== null) return { agl: a.geo_alt - elevation, basis: 'geo' }
  if (a.baro_alt !== null) return { agl: a.baro_alt - elevation, basis: 'baro' }
  return null
}

export function isLowFlight(a: { on_ground: boolean }, agl: number | null, inAirportZone: boolean): boolean {
  return !a.on_ground && agl !== null && agl < LOW_FLIGHT_AGL_M && !inAirportZone
}

/** Ray casting: count the edges a ray towards +lon crosses; odd means inside. */
export function pointInRing(lon: number, lat: number, ring: LonLat[]): boolean {
  let inside = false
  let prev = ring.at(-1)
  for (const cur of ring) {
    if (!prev) break
    const [xi, yi] = cur
    const [xj, yj] = prev
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside
    prev = cur
  }
  return inside
}

export function inAnyRing(lon: number, lat: number, rings: LonLat[][]): boolean {
  return rings.some((ring) => pointInRing(lon, lat, ring))
}

/**
 * Inside an airport buffer zone, or closer than AIRPORT_RADIUS_M to the nearest airport (from
 * REST; only seeded airports have zones, but every airport has approaches).
 */
export function nearAirport(lon: number, lat: number, zones: LonLat[][], nearestAirportM: number | null): boolean {
  return inAnyRing(lon, lat, zones) || (nearestAirportM !== null && nearestAirportM < AIRPORT_RADIUS_M)
}

/** Cache key: 0.001° cells (~110 m north-south), about one DEM pixel (90 m). */
export function elevationKey(lon: number, lat: number): string {
  return `${lon.toFixed(3)},${lat.toFixed(3)}`
}
