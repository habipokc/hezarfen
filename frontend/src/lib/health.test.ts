import { describe, expect, it } from 'vitest'
import { describeHealth } from './health'

describe('describeHealth', () => {
  it('lists every dependency check', () => {
    const text = describeHealth({ status: 'ok', checks: { postgis: '3.6.0', redis: 'ok' } })
    expect(text).toBe('backend ok (postgis: 3.6.0, redis: ok)')
  })

  it('surfaces a degraded status', () => {
    expect(describeHealth({ status: 'degraded', checks: { redis: 'error' } })).toContain('degraded')
  })
})
