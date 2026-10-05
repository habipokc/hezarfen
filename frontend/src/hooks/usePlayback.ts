import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'
import { requestJson } from '../lib/api'
import {
  type Clock,
  type PlaybackResponse,
  type Timeline,
  advanceClock,
  buildTimeline,
  firstFrameTs,
  playbackBucket,
  sampleAircraft,
  sampleAt,
  tailsAt,
  trackUntil,
} from '../lib/playback'
import { TAIL_SECONDS } from '../lib/tails'
import { trackLine } from '../lib/track'
import type { Aircraft } from '../lib/types'
import { AIRCRAFT_SOURCE, TAILS_SOURCE, TRACK_SOURCE } from '../map/layers'

export const SPEEDS = [1, 10, 60] as const
export type Speed = (typeof SPEEDS)[number]

/** Map redraws are capped (geojson-vt re-tiles on every setData); the slider updates less often. */
const DRAW_MS = 50
const UI_MS = 250

export interface PlaybackWindow {
  start: number
  end: number
}

interface Loaded extends PlaybackWindow {
  /** first recorded frame; playback starts and rewinds here */
  first: number
  bucket: number
  timeline: Timeline
  fixes: number
}

export type PlaybackStatus =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; fixes: number; aircraft: number }

const emptyCollection = { type: 'FeatureCollection', features: [] } as GeoJSON.FeatureCollection

/**
 * History mode: one REST request for the whole window, then everything happens on the client.
 * A `requestAnimationFrame` loop advances a simulated clock (real time × speed); at most every
 * 50 ms the aircraft, tails and the selected track are sampled at that instant and handed to
 * MapLibre. React only sees the clock four times a second (slider, labels, detail panel).
 */
export function usePlayback(
  mapRef: RefObject<MapLibreMap | null>,
  ready: boolean,
  range: PlaybackWindow | null,
  selectedId: string | null,
) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ui, setUi] = useState<{ t: number; playing: boolean; count: number }>({ t: 0, playing: false, count: 0 })
  const [speed, setSpeed] = useState<Speed>(10)

  const clockRef = useRef<Clock>({ t: 0, playing: false })
  const speedRef = useRef<Speed>(speed)
  const drawRef = useRef<(() => void) | null>(null)
  const currentSelected = useEffectEvent(() => selectedId)

  // fetch the window
  const start = range?.start
  const end = range?.end
  useEffect(() => {
    if (start === undefined || end === undefined) return
    const controller = new AbortController()
    const bucket = playbackBucket(end - start)
    requestJson<PlaybackResponse>(`/api/playback?start=${start}&end=${end}&bucket=${bucket}`, { signal: controller.signal })
      .then((body) => {
        const timeline = buildTimeline(body.frames)
        let fixes = 0
        for (const samples of timeline.values()) fixes += samples.length
        const first = firstFrameTs(body.start, body.frames)
        clockRef.current = { t: first, playing: false }
        setLoaded({ start: body.start, end: body.end, first, bucket: body.bucket, timeline, fixes })
        setError(null)
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return
        setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      controller.abort()
      setLoaded(null)
      setError(null)
    }
  }, [start, end])

  // animation loop and drawing
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !loaded) return
    const { timeline, bucket } = loaded
    const source = (id: string) => map.getSource<GeoJSONSource>(id)

    const draw = () => {
      const { t } = clockRef.current
      const aircraft = sampleAt(timeline, t, bucket)
      source(AIRCRAFT_SOURCE)?.setData({
        type: 'FeatureCollection',
        features: aircraft.map((a) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [a.lon, a.lat] }, properties: a })),
      })
      source(TAILS_SOURCE)?.setData(tailsAt(timeline, t, TAIL_SECONDS, bucket))
      const selected = currentSelected()
      const samples = selected ? timeline.get(selected) : undefined
      source(TRACK_SOURCE)?.setData(trackLine(samples ? trackUntil(samples, t, bucket) : []))
      return aircraft.length
    }

    let frame = 0
    let last = performance.now()
    let lastDraw = -Infinity
    let lastUi = -Infinity
    let count = draw()
    const publish = () => setUi({ t: clockRef.current.t, playing: clockRef.current.playing, count })
    drawRef.current = () => {
      count = draw()
      publish()
    }
    publish()

    const tick = (now: number) => {
      const before = clockRef.current
      clockRef.current = advanceClock(before, now - last, speedRef.current, loaded.end)
      last = now
      const moved = clockRef.current !== before
      if (moved && now - lastDraw >= DRAW_MS) {
        count = draw()
        lastDraw = now
      }
      if ((moved && now - lastUi >= UI_MS) || before.playing !== clockRef.current.playing) {
        publish()
        lastUi = now
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(frame)
      drawRef.current = null
      try {
        for (const id of [AIRCRAFT_SOURCE, TAILS_SOURCE, TRACK_SOURCE]) source(id)?.setData(emptyCollection)
      } catch {
        // map already removed
      }
    }
  }, [mapRef, ready, loaded])

  // a new selection while paused still needs its track drawn
  useEffect(() => {
    drawRef.current?.()
  }, [selectedId])

  const controls = useMemo(
    () => ({
      togglePlay() {
        const c = clockRef.current
        if (!loaded) return
        // pressing play at the end starts over
        const t = !c.playing && c.t >= loaded.end ? loaded.first : c.t
        clockRef.current = { t, playing: !c.playing }
        drawRef.current?.()
      },
      seek(t: number) {
        clockRef.current = { ...clockRef.current, t }
        drawRef.current?.()
      },
      setSpeed(s: Speed) {
        speedRef.current = s
        setSpeed(s)
      },
    }),
    [loaded],
  )

  const status: PlaybackStatus = error
    ? { status: 'error', message: error }
    : !range
      ? { status: 'idle' }
      : !loaded
        ? { status: 'loading' }
        : { status: 'ready', fixes: loaded.fixes, aircraft: loaded.timeline.size }

  const selected: Aircraft | null = useMemo(
    () => (loaded && selectedId ? sampleAircraft(loaded.timeline, selectedId, ui.t, loaded.bucket) : null),
    [loaded, selectedId, ui.t],
  )

  return {
    status,
    start: loaded?.start ?? start ?? 0,
    end: loaded?.end ?? end ?? 0,
    t: ui.t,
    playing: ui.playing,
    count: ui.count,
    speed,
    selected,
    ...controls,
  }
}
