import { describe, expect, it } from 'vitest'
import { TAIL_SECONDS, Tails } from './tails'
import { aircraft } from './testing'

describe('Tails', () => {
  it('collects one point per new fix and draws aircraft with two or more', () => {
    const tails = new Tails()
    tails.sync([aircraft('a', { ts: 0, lon: 28 }), aircraft('b', { ts: 0 })])
    tails.sync([aircraft('a', { ts: 0, lon: 28 }), aircraft('b', { ts: 0 })]) // same fix again
    tails.sync([aircraft('a', { ts: 2, lon: 28.1, baro_alt: 900 }), aircraft('b', { ts: 0 })])
    const fc = tails.toFeatureCollection()
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0]?.geometry.coordinates).toEqual([
      [28, 41],
      [28.1, 41],
    ])
    // properties of the newest fix, so the line can share the icon's altitude colour
    expect(fc.features[0]?.properties).toEqual({ icao24: 'a', baro_alt: 900, geo_alt: null, on_ground: false })
  })

  it(`keeps only the last ${TAIL_SECONDS} s of each aircraft`, () => {
    const tails = new Tails()
    for (const ts of [0, 60, 121, 130]) tails.sync([aircraft('a', { ts, lon: 28 + ts / 100 })])
    expect(tails.toFeatureCollection().features[0]?.geometry.coordinates.map(([lon]) => lon)).toEqual([28.6, 29.21, 29.3])
  })

  it('forgets aircraft that are no longer in the store', () => {
    const tails = new Tails()
    tails.sync([aircraft('a', { ts: 0 }), aircraft('b', { ts: 0 })])
    tails.sync([aircraft('b', { ts: 2, lon: 30 })])
    expect(tails.size).toBe(1)
    tails.clear()
    expect(tails.size).toBe(0)
  })
})
