import { describe, expect, it } from 'vitest'
import { checkDrawnPolygon, ringAreaKm2 } from './polygon'

// a closed ring, counter-clockwise, lon/lat
const square = (lon: number, lat: number, size: number): [number, number][] => [
  [lon, lat],
  [lon + size, lat],
  [lon + size, lat + size],
  [lon, lat + size],
  [lon, lat],
]

describe('ringAreaKm2', () => {
  it('matches the area of a small square near Istanbul (cos(lat) shrink)', () => {
    // 0.1° × 0.1° at 41° N ≈ 11.12 km × 8.39 km ≈ 93.3 km²
    expect(ringAreaKm2(square(29, 41, 0.1))).toBeCloseTo(93.3, 0)
  })

  it('does not depend on winding order', () => {
    const ring = square(29, 41, 0.1)
    expect(ringAreaKm2([...ring].reverse())).toBeCloseTo(ringAreaKm2(ring), 6)
  })
})

describe('checkDrawnPolygon', () => {
  it('accepts a reasonable zone inside the region', () => {
    expect(checkDrawnPolygon(square(28.8, 40.9, 0.3))).toBeNull()
  })

  it('needs at least three distinct corners', () => {
    expect(checkDrawnPolygon([[29, 41], [29.1, 41], [29, 41]])).toMatch(/three/)
  })

  it('rejects zones that are too small or too large', () => {
    expect(checkDrawnPolygon(square(29, 41, 0.001))).toMatch(/too small/)
    expect(checkDrawnPolygon(square(26, 39.5, 5))).toMatch(/too large/)
  })

  it('rejects zones outside the region', () => {
    expect(checkDrawnPolygon(square(10, 50, 0.3))).toMatch(/outside/)
  })

  it('rejects more than 1000 vertices', () => {
    const ring: [number, number][] = Array.from({ length: 1001 }, (_, i) => {
      const a = (i / 1001) * 2 * Math.PI
      return [29 + 0.2 * Math.cos(a), 41 + 0.2 * Math.sin(a)]
    })
    expect(checkDrawnPolygon([...ring, ring[0]!])).toMatch(/1000/)
  })
})
