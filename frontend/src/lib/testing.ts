import type { Aircraft } from './types'

/** An airborne aircraft with every nullable field null; override what a test cares about. */
export function aircraft(icao24: string, overrides: Partial<Aircraft> = {}): Aircraft {
  return {
    icao24,
    callsign: null,
    lon: 29,
    lat: 41,
    baro_alt: null,
    geo_alt: null,
    velocity: null,
    heading: null,
    vrate: null,
    on_ground: false,
    squawk: null,
    category: null,
    ts: 100,
    ...overrides,
  }
}
