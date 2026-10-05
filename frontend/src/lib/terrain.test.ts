import { describe, expect, it } from 'vitest'
import { AIRPORT_RADIUS_M, LOW_FLIGHT_AGL_M, aboveGround, elevationKey, inAnyRing, isLowFlight, nearAirport, pointInRing } from './terrain'
import type { LonLat } from './playback'

const square: LonLat[] = [[28, 41], [29, 41], [29, 42], [28, 42], [28, 41]]

describe('aboveGround', () => {
  it('subtracts the terrain from the geometric altitude', () => {
    expect(aboveGround({ geo_alt: 1200, baro_alt: 1100 }, 150)).toEqual({ agl: 1050, basis: 'geo' })
  })
  it('falls back to the barometric altitude when there is no geometric one', () => {
    expect(aboveGround({ geo_alt: null, baro_alt: 900 }, 100)).toEqual({ agl: 800, basis: 'baro' })
  })
  it('is unknown without an altitude or without terrain', () => {
    expect(aboveGround({ geo_alt: null, baro_alt: null }, 100)).toBeNull()
    expect(aboveGround({ geo_alt: 1000, baro_alt: 1000 }, null)).toBeNull()
  })
})

describe('isLowFlight', () => {
  const airborne = { on_ground: false }
  it('flags an airborne aircraft below the threshold outside airport zones', () => {
    expect(isLowFlight(airborne, LOW_FLIGHT_AGL_M - 1, false)).toBe(true)
  })
  it('is not low at or above the threshold', () => {
    expect(isLowFlight(airborne, LOW_FLIGHT_AGL_M, false)).toBe(false)
  })
  it('ignores aircraft near airports and on the ground', () => {
    expect(isLowFlight(airborne, 50, true)).toBe(false)
    expect(isLowFlight({ on_ground: true }, 0, false)).toBe(false)
  })
  it('needs a known AGL', () => {
    expect(isLowFlight(airborne, null, false)).toBe(false)
  })
})

describe('pointInRing', () => {
  it('finds points inside and outside', () => {
    expect(pointInRing(28.5, 41.5, square)).toBe(true)
    expect(pointInRing(29.5, 41.5, square)).toBe(false)
    expect(pointInRing(28.5, 40.9, square)).toBe(false)
  })
  it('handles a concave ring', () => {
    // a U shape open to the north: the notch between the arms is outside
    const u: LonLat[] = [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]]
    expect(pointInRing(1.5, 2, u)).toBe(false)
    expect(pointInRing(0.5, 2, u)).toBe(true)
    expect(pointInRing(1.5, 0.5, u)).toBe(true)
  })
  it('works for an unclosed ring too', () => {
    expect(pointInRing(28.5, 41.5, square.slice(0, 4))).toBe(true)
  })
})

describe('inAnyRing', () => {
  it('checks every ring', () => {
    const far: LonLat[] = [[30, 40], [31, 40], [31, 41], [30, 40]]
    expect(inAnyRing(28.5, 41.5, [far, square])).toBe(true)
    expect(inAnyRing(27, 41.5, [far, square])).toBe(false)
    expect(inAnyRing(27, 41.5, [])).toBe(false)
  })
})

describe('elevationKey', () => {
  it('snaps nearby points to the same ~100 m cell', () => {
    expect(elevationKey(28.12341, 41.00049)).toBe(elevationKey(28.12339, 41.0001))
    expect(elevationKey(28.1234, 41.0)).not.toBe(elevationKey(28.1254, 41.0))
  })
})

describe('nearAirport', () => {
  it('is true inside an airport zone', () => {
    expect(nearAirport(28.5, 41.5, [square], null)).toBe(true)
  })
  it('is true close to any airport, zone or not', () => {
    expect(nearAirport(27, 41.5, [square], AIRPORT_RADIUS_M - 1)).toBe(true)
    expect(nearAirport(27, 41.5, [square], AIRPORT_RADIUS_M)).toBe(false)
  })
  it('is false far from zones without a known nearest airport', () => {
    expect(nearAirport(27, 41.5, [square], null)).toBe(false)
  })
})
