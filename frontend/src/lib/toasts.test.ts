import { describe, expect, it } from 'vitest'
import { MAX_TOASTS, eventToast, pushToast } from './toasts'
import type { GeofenceEvent } from './types'

const event = (id: number, overrides: Partial<GeofenceEvent> = {}): GeofenceEvent => ({
  id,
  geofence: { id: 3, name: 'Bosphorus' },
  icao24: 'abc123',
  callsign: 'THY7',
  event: 'enter',
  ts: 100,
  lon: 29,
  lat: 41,
  ...overrides,
})

describe('eventToast', () => {
  it('describes the event in one line', () => {
    expect(eventToast(event(1)).text).toBe('THY7 entered Bosphorus')
    expect(eventToast(event(2, { event: 'exit', callsign: null })).text).toBe('abc123 left Bosphorus')
  })
})

describe('pushToast', () => {
  it('puts the newest first and keeps at most MAX_TOASTS', () => {
    let list = [] as ReturnType<typeof eventToast>[]
    for (let i = 1; i <= MAX_TOASTS + 2; i++) list = pushToast(list, eventToast(event(i)))
    expect(list).toHaveLength(MAX_TOASTS)
    expect(list[0]?.id).toBe(MAX_TOASTS + 2)
  })

  it('ignores a toast that is already shown', () => {
    const list = pushToast([], eventToast(event(1)))
    expect(pushToast(list, eventToast(event(1)))).toBe(list)
  })
})
