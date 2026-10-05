import type { Aircraft } from './types'

export type LonLat = [number, number]

/** `GET /api/playback` (ICD §7.2). */
export interface PlaybackFrame {
  ts: number
  aircraft: Aircraft[]
}
export interface PlaybackResponse {
  start: number
  end: number
  bucket: number
  frames: PlaybackFrame[]
}

/** Every aircraft's fixes in time order: the trajectory, independent of how frames bucketed it. */
export type Timeline = Map<string, Aircraft[]>

export interface TailProperties {
  icao24: string
  baro_alt: number | null
  geo_alt: number | null
  on_ground: boolean
}
export interface LineCollection<P> {
  type: 'FeatureCollection'
  features: { type: 'Feature'; geometry: { type: 'LineString'; coordinates: LonLat[] }; properties: P }[]
}

const TARGET_FRAMES = 360
/** Longest gap (in buckets) we still bridge by interpolation; beyond it the aircraft is hidden. */
const MAX_GAP_BUCKETS = 3

/** Bucket size for a window: ~360 frames, a multiple of 5 s, within the API's 1–600 s. */
export function playbackBucket(windowSeconds: number): number {
  const raw = Math.ceil(windowSeconds / TARGET_FRAMES / 5) * 5
  return Math.min(600, Math.max(5, raw))
}

export function buildTimeline(frames: PlaybackFrame[]): Timeline {
  const timeline: Timeline = new Map()
  for (const frame of frames) {
    for (const a of frame.aircraft) {
      const samples = timeline.get(a.icao24)
      if (samples) samples.push(a)
      else timeline.set(a.icao24, [a])
    }
  }
  for (const [id, samples] of timeline) {
    samples.sort((x, y) => x.ts - y.ts)
    timeline.set(
      id,
      samples.filter((s, i) => i === 0 || s.ts !== samples[i - 1]?.ts),
    )
  }
  return timeline
}

const lerp = (a: number, b: number, f: number) => a + (b - a) * f

/** Interpolate a compass angle along the shorter arc (350° → 10° passes through 0°). */
export function lerpAngle(a: number, b: number, f: number): number {
  const delta = ((((b - a) % 360) + 540) % 360) - 180
  return (((a + delta * f) % 360) + 360) % 360
}

/** Both known → interpolate; otherwise keep the earlier fix's value (a step, never invented). */
function lerpNullable(a: number | null, b: number | null, f: number, fn = lerp): number | null {
  return a !== null && b !== null ? fn(a, b, f) : a
}

/** Index of the last sample with `ts <= t`, or -1. */
function lastAtOrBefore(samples: Aircraft[], t: number): number {
  let lo = 0
  let hi = samples.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (samples[mid]!.ts <= t) {
      found = mid
      lo = mid + 1
    } else hi = mid - 1
  }
  return found
}

/**
 * Where one aircraft is at time `t`: linear between the fixes around `t`, held for one bucket
 * after the last fix, hidden before the first fix and inside gaps longer than 3 buckets.
 */
function positionAt(samples: Aircraft[], t: number, bucket: number): Aircraft | null {
  const i = lastAtOrBefore(samples, t)
  if (i < 0) return null
  const s = samples[i]!
  const next = samples[i + 1]
  if (next && next.ts - s.ts <= MAX_GAP_BUCKETS * bucket) {
    const f = (t - s.ts) / (next.ts - s.ts)
    if (f === 0) return s
    return {
      ...s,
      lon: lerp(s.lon, next.lon, f),
      lat: lerp(s.lat, next.lat, f),
      baro_alt: lerpNullable(s.baro_alt, next.baro_alt, f),
      geo_alt: lerpNullable(s.geo_alt, next.geo_alt, f),
      velocity: lerpNullable(s.velocity, next.velocity, f),
      heading: lerpNullable(s.heading, next.heading, f, lerpAngle),
      on_ground: f < 0.5 ? s.on_ground : next.on_ground,
      ts: Math.floor(t),
    }
  }
  return t - s.ts <= bucket ? s : null
}

/** One aircraft at `t` (for the detail panel), or null when it is not visible then. */
export function sampleAircraft(timeline: Timeline, icao24: string, t: number, bucket: number): Aircraft | null {
  const samples = timeline.get(icao24)
  return samples ? positionAt(samples, t, bucket) : null
}

export function sampleAt(timeline: Timeline, t: number, bucket: number): Aircraft[] {
  const out: Aircraft[] = []
  for (const samples of timeline.values()) {
    const a = positionAt(samples, t, bucket)
    if (a) out.push(a)
  }
  return out
}

/** Fixes in `[from, t]` followed by the position at `t`. */
function pathUntil(samples: Aircraft[], from: number, t: number, bucket: number): LonLat[] {
  const head = positionAt(samples, t, bucket)
  if (!head) return []
  const coords: LonLat[] = []
  for (const s of samples) {
    if (s.ts > t) break
    if (s.ts >= from) coords.push([s.lon, s.lat])
  }
  const last = coords[coords.length - 1]
  if (!last || last[0] !== head.lon || last[1] !== head.lat) coords.push([head.lon, head.lat])
  return coords
}

/** The last `seconds` of every visible aircraft, ending at its interpolated position. */
export function tailsAt(timeline: Timeline, t: number, seconds: number, bucket: number): LineCollection<TailProperties> {
  const features: LineCollection<TailProperties>['features'] = []
  for (const [icao24, samples] of timeline) {
    const coords = pathUntil(samples, t - seconds, t, bucket)
    if (coords.length < 2) continue
    const head = positionAt(samples, t, bucket)!
    features.push({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: coords },
      properties: { icao24, baro_alt: head.baro_alt, geo_alt: head.geo_alt, on_ground: head.on_ground },
    })
  }
  return { type: 'FeatureCollection', features }
}

/** One aircraft's path from the start of the window up to `t`. */
export function trackUntil(samples: Aircraft[], t: number, bucket: number): LonLat[] {
  return pathUntil(samples, -Infinity, t, bucket)
}

export interface Clock {
  t: number
  playing: boolean
}

/** Simulated time advances by real elapsed time × speed and stops at `end`. */
export function advanceClock(clock: Clock, elapsedMs: number, speed: number, end: number): Clock {
  if (!clock.playing) return clock
  const t = clock.t + (elapsedMs / 1000) * speed
  return t >= end ? { t: end, playing: false } : { t, playing: true }
}
