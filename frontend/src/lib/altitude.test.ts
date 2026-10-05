import { describe, expect, it } from 'vitest'
import { ALTITUDE_STOPS, GROUND_COLOR, UNKNOWN_ALTITUDE_COLOR, altitudeColor, altitudeColorExpression } from './altitude'

describe('altitudeColor', () => {
  it('returns the exact stop colour at each stop', () => {
    for (const [metres, colour] of ALTITUDE_STOPS) {
      expect(altitudeColor(metres, false)).toBe(colour)
    }
  })

  it('interpolates linearly in RGB between stops, like MapLibre interpolate', () => {
    // halfway between #000000-like stops is easiest to see on a synthetic pair
    const [[a, ca], [b, cb]] = [ALTITUDE_STOPS[0]!, ALTITUDE_STOPS[1]!]
    const mid = altitudeColor((a + b) / 2, false)
    const channel = (hex: string, i: number) => parseInt(hex.slice(1 + 2 * i, 3 + 2 * i), 16)
    for (const i of [0, 1, 2]) {
      expect(channel(mid, i)).toBe(Math.round((channel(ca, i) + channel(cb, i)) / 2))
    }
  })

  it('clamps below the first and above the last stop', () => {
    expect(altitudeColor(-500, false)).toBe(ALTITUDE_STOPS[0]![1])
    expect(altitudeColor(20000, false)).toBe(ALTITUDE_STOPS.at(-1)![1])
  })

  it('greys out aircraft on the ground and flags unknown altitude', () => {
    expect(altitudeColor(9000, true)).toBe(GROUND_COLOR)
    expect(altitudeColor(null, false)).toBe(UNKNOWN_ALTITUDE_COLOR)
  })
})

describe('altitudeColorExpression', () => {
  it('uses the same stops as altitudeColor', () => {
    const expr = JSON.stringify(altitudeColorExpression())
    for (const [metres, colour] of ALTITUDE_STOPS) {
      expect(expr).toContain(`${metres},"${colour}"`)
    }
    expect(expr).toContain('"on_ground"')
    expect(expr).toContain(GROUND_COLOR)
  })
})
