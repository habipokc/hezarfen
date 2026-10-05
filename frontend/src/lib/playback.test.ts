import { describe, expect, it } from 'vitest'
import {
  advanceClock,
  buildTimeline,
  lerpAngle,
  playbackBucket,
  sampleAircraft,
  sampleAt,
  tailsAt,
  trackUntil,
} from './playback'
import { aircraft } from './testing'

describe('playbackBucket', () => {
  it('aims for about 360 frames in multiples of 5 s', () => {
    expect(playbackBucket(15 * 60)).toBe(5)
    expect(playbackBucket(30 * 60)).toBe(5)
    expect(playbackBucket(60 * 60)).toBe(10)
    expect(playbackBucket(2 * 60 * 60)).toBe(20)
  })

  it('stays within the API range 1–600', () => {
    expect(playbackBucket(1)).toBe(5)
    expect(playbackBucket(10 * 24 * 3600)).toBe(600)
  })
})

describe('buildTimeline', () => {
  it('groups fixes per aircraft, sorted by ts, duplicates dropped', () => {
    const t = buildTimeline([
      { ts: 10, aircraft: [aircraft('a', { ts: 12 }), aircraft('b', { ts: 11 })] },
      { ts: 0, aircraft: [aircraft('a', { ts: 3 })] },
      { ts: 20, aircraft: [aircraft('a', { ts: 12 })] },
    ])
    expect(t.get('a')?.map((s) => s.ts)).toEqual([3, 12])
    expect(t.get('b')?.map((s) => s.ts)).toEqual([11])
  })
})

describe('lerpAngle', () => {
  it('turns along the shorter arc across north', () => {
    expect(lerpAngle(350, 10, 0.5)).toBeCloseTo(0)
    expect(lerpAngle(10, 350, 0.25)).toBeCloseTo(5)
    expect(lerpAngle(90, 180, 0.5)).toBeCloseTo(135)
  })

  it('always returns 0 ≤ angle < 360', () => {
    expect(lerpAngle(350, 10, 0.75)).toBeCloseTo(5)
    expect(lerpAngle(5, 355, 0.75)).toBeCloseTo(357.5)
  })
})

describe('sampleAt', () => {
  const timeline = buildTimeline([
    {
      ts: 0,
      aircraft: [aircraft('a', { ts: 0, lon: 28, lat: 40, baro_alt: 1000, heading: 350 })],
    },
    {
      ts: 10,
      aircraft: [aircraft('a', { ts: 10, lon: 29, lat: 41, baro_alt: 2000, heading: 10 })],
    },
  ])

  it('interpolates position, altitude and heading between two fixes', () => {
    const [a] = sampleAt(timeline, 2.5, 10)
    expect(a?.lon).toBeCloseTo(28.25)
    expect(a?.lat).toBeCloseTo(40.25)
    expect(a?.baro_alt).toBeCloseTo(1250)
    expect(a?.heading).toBeCloseTo(355)
    expect(a?.ts).toBe(2)
  })

  it('returns the exact fix on a sample', () => {
    expect(sampleAt(timeline, 10, 10)[0]?.lon).toBe(29)
  })

  it('hides an aircraft before its first fix', () => {
    expect(sampleAt(timeline, -1, 10)).toEqual([])
  })

  it('holds the last fix for one bucket, then hides it', () => {
    expect(sampleAt(timeline, 19, 10)[0]?.lon).toBe(29)
    expect(sampleAt(timeline, 21, 10)).toEqual([])
  })

  it('does not interpolate across a gap longer than three buckets', () => {
    const gappy = buildTimeline([
      { ts: 0, aircraft: [aircraft('a', { ts: 0, lon: 28 })] },
      { ts: 100, aircraft: [aircraft('a', { ts: 100, lon: 30 })] },
    ])
    expect(sampleAt(gappy, 5, 10)[0]?.lon).toBe(28) // held
    expect(sampleAt(gappy, 50, 10)).toEqual([]) // gone in between
    expect(sampleAt(gappy, 100, 10)[0]?.lon).toBe(30)
  })

  it('steps to the earlier fix when one side is null (no invented values)', () => {
    const t = buildTimeline([
      { ts: 0, aircraft: [aircraft('a', { ts: 0, baro_alt: null, heading: null })] },
      { ts: 10, aircraft: [aircraft('a', { ts: 10, baro_alt: 3000, heading: 90 })] },
    ])
    const [a] = sampleAt(t, 2, 10)
    expect(a?.baro_alt).toBeNull()
    expect(a?.heading).toBeNull()
    expect(sampleAt(t, 10, 10)[0]?.baro_alt).toBe(3000)
  })
})

describe('tailsAt', () => {
  const timeline = buildTimeline(
    [0, 10, 20, 30].map((ts) => ({ ts, aircraft: [aircraft('a', { ts, lon: 28 + ts / 10, lat: 40 })] })),
  )

  it('draws the fixes inside the window plus the interpolated head', () => {
    const fc = tailsAt(timeline, 25, 15, 10)
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0]?.geometry.coordinates).toEqual([
      [29, 40],
      [30, 40],
      [30.5, 40],
    ])
    expect(fc.features[0]?.properties.icao24).toBe('a')
  })

  it('skips aircraft that are not visible or have a single point', () => {
    expect(tailsAt(timeline, 100, 15, 10).features).toEqual([])
    expect(tailsAt(timeline, 0, 15, 10).features).toEqual([])
  })
})

describe('trackUntil', () => {
  it('returns the fixes up to t and the interpolated position', () => {
    const samples = [0, 10, 20].map((ts) => aircraft('a', { ts, lon: 28 + ts / 10, lat: 40 }))
    expect(trackUntil(samples, 15, 10)).toEqual([
      [28, 40],
      [29, 40],
      [29.5, 40],
    ])
    expect(trackUntil(samples, -5, 10)).toEqual([])
  })
})

describe('advanceClock', () => {
  it('moves simulated time by real time × speed', () => {
    expect(advanceClock({ t: 100, playing: true }, 500, 60, 1000)).toEqual({ t: 130, playing: true })
  })

  it('stops at the end of the window', () => {
    expect(advanceClock({ t: 990, playing: true }, 1000, 60, 1000)).toEqual({ t: 1000, playing: false })
  })

  it('does nothing while paused', () => {
    const paused = { t: 5, playing: false }
    expect(advanceClock(paused, 1000, 10, 100)).toBe(paused)
  })
})

describe('sampleAircraft', () => {
  it('returns one aircraft or null', () => {
    const timeline = buildTimeline([{ ts: 0, aircraft: [aircraft('a', { ts: 0 })] }])
    expect(sampleAircraft(timeline, 'a', 5, 10)?.icao24).toBe('a')
    expect(sampleAircraft(timeline, 'b', 5, 10)).toBeNull()
    expect(sampleAircraft(timeline, 'a', 50, 10)).toBeNull()
  })
})
