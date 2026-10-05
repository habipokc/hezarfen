import { describe, expect, it } from 'vitest'
import { SDF_EDGE, signedDistanceAlpha } from './sdf'

// 9×9 mask with a 5×5 filled square in the middle (pixels 2..6)
const W = 9
const mask = Array.from({ length: W * W }, (_, i) => {
  const [x, y] = [i % W, Math.floor(i / W)]
  return x >= 2 && x <= 6 && y >= 2 && y <= 6
})
const at = (alpha: Uint8ClampedArray, x: number, y: number) => alpha[y * W + x]!

describe('signedDistanceAlpha', () => {
  const alpha = signedDistanceAlpha(mask, W, W, 3)

  it('is brightest deep inside and darkest far outside', () => {
    expect(at(alpha, 4, 4)).toBeGreaterThan(at(alpha, 2, 4))
    expect(at(alpha, 0, 0)).toBe(0)
  })

  it('puts the shape edge around the SDF threshold MapLibre uses', () => {
    expect(at(alpha, 2, 4)).toBeGreaterThanOrEqual(SDF_EDGE)
    expect(at(alpha, 1, 4)).toBeLessThan(SDF_EDGE)
  })

  it('falls off monotonically away from the shape', () => {
    expect(at(alpha, 1, 4)).toBeGreaterThan(at(alpha, 0, 4))
  })
})
