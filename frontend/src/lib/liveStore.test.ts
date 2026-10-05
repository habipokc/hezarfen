import { describe, expect, it } from 'vitest'
import { LiveStore } from './liveStore'
import { aircraft } from './testing'

describe('LiveStore', () => {
  it('replaces its whole content on snapshot', () => {
    const store = new LiveStore()
    store.applySnapshot([aircraft('aaaaaa'), aircraft('bbbbbb')])
    store.applySnapshot([aircraft('cccccc')])
    expect(store.size).toBe(1)
    expect(store.get('cccccc')?.icao24).toBe('cccccc')
    expect(store.get('aaaaaa')).toBeUndefined()
  })

  it('applies upserts and removes from a delta', () => {
    const store = new LiveStore()
    store.applySnapshot([aircraft('aaaaaa'), aircraft('bbbbbb')])
    store.applyDelta([aircraft('aaaaaa', { lon: 30, ts: 101 }), aircraft('cccccc')], ['bbbbbb', 'zzzzzz'])
    expect(store.get('aaaaaa')?.lon).toBe(30)
    expect(store.get('bbbbbb')).toBeUndefined()
    expect(store.size).toBe(2)
  })

  it('keeps the newest ts per aircraft (a delta may be older than the snapshot)', () => {
    const store = new LiveStore()
    store.applySnapshot([aircraft('aaaaaa', { lon: 29.5, ts: 105 })])
    store.applyDelta([aircraft('aaaaaa', { lon: 29.4, ts: 104 })], [])
    expect(store.get('aaaaaa')?.lon).toBe(29.5)
    store.applyDelta([aircraft('aaaaaa', { lon: 29.6, ts: 105 })], [])
    expect(store.get('aaaaaa')?.lon).toBe(29.6) // same second, later message wins
  })

  it('builds a GeoJSON FeatureCollection with lon, lat order', () => {
    const store = new LiveStore()
    store.applySnapshot([aircraft('aaaaaa', { lon: 28.8, lat: 41.2 })])
    const fc = store.toFeatureCollection()
    expect(fc.type).toBe('FeatureCollection')
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0]?.geometry.coordinates).toEqual([28.8, 41.2])
    expect(fc.features[0]?.properties.icao24).toBe('aaaaaa')
  })

  it('clear empties the store', () => {
    const store = new LiveStore()
    store.applySnapshot([aircraft('aaaaaa')])
    store.clear()
    expect(store.size).toBe(0)
  })
})
