import { describe, expect, it } from 'vitest'
import { BACKOFF_BASE_MS, BACKOFF_MAX_MS, backoffDelay } from './backoff'

describe('backoffDelay', () => {
  it('doubles the ceiling with every attempt (random = 1 gives the ceiling)', () => {
    expect(backoffDelay(0, () => 1)).toBe(BACKOFF_BASE_MS)
    expect(backoffDelay(1, () => 1)).toBe(BACKOFF_BASE_MS * 2)
    expect(backoffDelay(3, () => 1)).toBe(BACKOFF_BASE_MS * 8)
  })

  it('is capped', () => {
    expect(backoffDelay(30, () => 1)).toBe(BACKOFF_MAX_MS)
    expect(backoffDelay(10_000, () => 1)).toBe(BACKOFF_MAX_MS)
  })

  it('applies full jitter but never returns less than the base delay', () => {
    expect(backoffDelay(4, () => 0.5)).toBe((BACKOFF_BASE_MS * 16) / 2)
    expect(backoffDelay(4, () => 0)).toBe(BACKOFF_BASE_MS)
  })
})
