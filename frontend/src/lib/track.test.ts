import { describe, expect, it } from 'vitest'
import { EMPTY_TRACK, extendTrack, trackFromResponse, trackLine } from './track'
import { aircraft } from './testing'

describe('trackFromResponse', () => {
  it('reads the LineString and its end time', () => {
    const track = trackFromResponse({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[28, 40], [28.1, 40]] },
      properties: { icao24: 'a', callsign: null, start_ts: 10, end_ts: 20, points: 2 },
    })
    expect(track).toEqual({ coords: [[28, 40], [28.1, 40]], endTs: 20 })
  })

  it('keeps a single point even though the API sends geometry null', () => {
    const track = trackFromResponse({
      type: 'Feature',
      geometry: null,
      properties: { icao24: 'a', callsign: null, start_ts: 20, end_ts: 20, points: 1 },
    })
    expect(track).toEqual({ coords: [], endTs: 20 })
  })
})

describe('extendTrack', () => {
  const base = { coords: [[28, 40], [28.1, 40]] as [number, number][], endTs: 20 }

  it('appends a live fix newer than the track', () => {
    const next = extendTrack(base, aircraft('a', { ts: 22, lon: 28.2, lat: 40 }))
    expect(next.coords).toEqual([[28, 40], [28.1, 40], [28.2, 40]])
    expect(next.endTs).toBe(22)
    expect(base.coords).toHaveLength(2) // not mutated
  })

  it('returns the same object for an old or repeated fix', () => {
    expect(extendTrack(base, aircraft('a', { ts: 20, lon: 9 }))).toBe(base)
    expect(extendTrack(base, aircraft('a', { ts: 15, lon: 9 }))).toBe(base)
  })

  it('starts from an empty track', () => {
    const next = extendTrack(EMPTY_TRACK, aircraft('a', { ts: 5, lon: 28, lat: 40 }))
    expect(next).toEqual({ coords: [[28, 40]], endTs: 5 })
  })
})

describe('trackLine', () => {
  it('is null below two points (RFC 7946 LineString)', () => {
    expect(trackLine([[28, 40]])).toEqual({ type: 'FeatureCollection', features: [] })
    expect(trackLine([[28, 40], [29, 40]]).features[0]?.geometry.type).toBe('LineString')
  })
})
