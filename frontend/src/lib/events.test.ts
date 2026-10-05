import { describe, expect, it } from 'vitest'
import { EVENT_LIST_SIZE, mergeEvents } from './events'
import type { GeofenceEvent } from './types'

const ev = (id: number): GeofenceEvent => ({
  id, geofence: { id: 1, name: 'LTFM 15 km' }, icao24: 'aaaaaa', callsign: null, event: 'enter', ts: id, lon: 28.8, lat: 41.2,
})
const ids = (list: GeofenceEvent[]) => list.map((e) => e.id)

describe('mergeEvents', () => {
  it('keeps newest first and drops duplicates', () => {
    expect(ids(mergeEvents([ev(5), ev(3)], [ev(4), ev(5), ev(1)]))).toEqual([5, 4, 3, 1])
  })

  it('caps the list', () => {
    const many = Array.from({ length: 20 }, (_, i) => ev(i))
    expect(mergeEvents([], many)).toHaveLength(EVENT_LIST_SIZE)
    expect(mergeEvents([], many)[0]?.id).toBe(19)
  })

  it('a live event older than the history (REST answered late) still sorts correctly', () => {
    expect(ids(mergeEvents([ev(10)], [ev(12), ev(11), ev(9)]))).toEqual([12, 11, 10, 9])
  })
})
