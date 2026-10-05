import { describe, expect, it } from 'vitest'
import { boundsToBbox, sameBbox } from './bbox'

describe('boundsToBbox', () => {
  it('pads the viewport on every side and rounds to 4 decimals', () => {
    expect(boundsToBbox(28, 40, 30, 41, 0.1)).toEqual([27.8, 39.9, 30.2, 41.1])
    expect(boundsToBbox(28.123456, 40.1, 28.987654, 40.9, 0)).toEqual([28.1235, 40.1, 28.9877, 40.9])
  })

  it('clamps to valid lon/lat ranges', () => {
    expect(boundsToBbox(-200, -95, 200, 95, 0)).toEqual([-180, -90, 180, 90])
    expect(boundsToBbox(170, 80, 179, 89, 0.5)).toEqual([165.5, 75.5, 180, 90])
  })

  it('keeps min < max even for a degenerate viewport', () => {
    const [w, s, e, n] = boundsToBbox(29, 41, 29, 41, 0.1)
    expect(w).toBeLessThan(e)
    expect(s).toBeLessThan(n)
  })
})

describe('sameBbox', () => {
  it('compares by value', () => {
    expect(sameBbox([1, 2, 3, 4], [1, 2, 3, 4])).toBe(true)
    expect(sameBbox([1, 2, 3, 4], [1, 2, 3, 5])).toBe(false)
    expect(sameBbox(null, [1, 2, 3, 4])).toBe(false)
  })
})
