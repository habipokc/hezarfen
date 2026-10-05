import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { throttle } from './throttle'

describe('throttle', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('runs the first call immediately and coalesces the rest into one trailing call', () => {
    const fn = vi.fn()
    const t = throttle(fn, 1000)
    t()
    expect(fn).toHaveBeenCalledTimes(1)
    t()
    t()
    t()
    expect(fn).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(999)
    expect(fn).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(1)
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('never runs more than once per interval', () => {
    const fn = vi.fn()
    const t = throttle(fn, 1000)
    for (let ms = 0; ms < 5000; ms += 100) {
      t()
      vi.advanceTimersByTime(100)
    }
    expect(fn.mock.calls.length).toBeLessThanOrEqual(6)
    expect(fn.mock.calls.length).toBeGreaterThanOrEqual(5)
  })

  it('runs immediately again once the interval has passed', () => {
    const fn = vi.fn()
    const t = throttle(fn, 1000)
    t()
    vi.advanceTimersByTime(1500)
    t()
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('cancel drops a pending trailing call', () => {
    const fn = vi.fn()
    const t = throttle(fn, 1000)
    t()
    t()
    t.cancel()
    vi.advanceTimersByTime(2000)
    expect(fn).toHaveBeenCalledTimes(1)
  })
})
