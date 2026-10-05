import { useCallback, useRef, useState } from 'react'
import { AircraftDetails } from './components/AircraftDetails'
import { EventFeed } from './components/EventFeed'
import { GeofencePanel } from './components/GeofencePanel'
import { HistoryWindow } from './components/HistoryWindow'
import { LayerPanel } from './components/LayerPanel'
import { type Mode, ModeSwitch } from './components/ModeSwitch'
import { Panel } from './components/Panel'
import { PlaybackBar } from './components/PlaybackBar'
import { StatusBadge } from './components/StatusBadge'
import { Toasts } from './components/Toasts'
import { useDrawPolygon } from './hooks/useDrawPolygon'
import { useGeofences } from './hooks/useGeofences'
import { useLiveAircraft } from './hooks/useLiveAircraft'
import { useMapInteractions } from './hooks/useMapInteractions'
import { useMapLibre } from './hooks/useMapLibre'
import { type PlaybackWindow, usePlayback } from './hooks/usePlayback'
import { useTrack } from './hooks/useTrack'
import { useViewportBbox } from './hooks/useViewportBbox'
import type { LonLat } from './lib/playback'
import { type Toast, eventToast, pushToast } from './lib/toasts'
import type { GeofenceEvent } from './lib/types'
import type { LayerGroup, LayerVisibility } from './map/layers'

const INITIAL_VISIBILITY: LayerVisibility = { provinces: true, airports: true, geofences: true, trails: true, callsigns: true }
const DEFAULT_HISTORY_SECONDS = 3600

export function App() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { mapRef, basemap } = useMapLibre(containerRef)
  const ready = basemap !== null
  const bbox = useViewportBbox(mapRef, ready)

  const [mode, setMode] = useState<Mode>('live')
  const [range, setRange] = useState<PlaybackWindow | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [visibility, setVisibility] = useState(INITIAL_VISIBILITY)
  const [expanded, setExpanded] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const isLive = mode === 'live'

  const geofences = useGeofences(mapRef, ready)
  const draw = useDrawPolygon(mapRef, ready)

  const onLiveEvent = (e: GeofenceEvent) => {
    setToasts((list) => pushToast(list, eventToast(e)))
    geofences.blink(e.geofence.id)
  }
  const live = useLiveAircraft(mapRef, ready, bbox, selectedId, isLive, onLiveEvent)
  useTrack(mapRef, ready, selectedId, live.selected, isLive)
  const playback = usePlayback(mapRef, ready, isLive ? null : range, selectedId)

  const select = useCallback((icao24: string | null) => {
    setSelectedId(icao24)
    if (icao24) setExpanded(true) // open the bottom sheet on mobile
  }, [])
  useMapInteractions(mapRef, ready, selectedId, select, visibility, draw.capturesClicks)

  const toggleLayer = useCallback((group: LayerGroup, visible: boolean) => {
    setVisibility((v) => ({ ...v, [group]: visible }))
  }, [])

  const changeMode = (next: Mode) => {
    if (next === mode) return
    if (next === 'history' && !range) {
      const end = Math.floor(Date.now() / 1000)
      setRange({ start: end - DEFAULT_HISTORY_SECONDS, end })
    }
    setMode(next)
  }

  const pickEvent = useCallback(
    (e: GeofenceEvent) => {
      const map = mapRef.current
      map?.flyTo({ center: [e.lon, e.lat], zoom: Math.max(map.getZoom(), 9) })
      select(e.icao24)
    },
    [mapRef, select],
  )

  const dismissToast = useCallback((id: number) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  const saveZone = async (name: string, ring: LonLat[]) => {
    const error = await geofences.create(name, ring)
    if (!error) draw.reset()
    return error
  }

  const historyReady = playback.status.status === 'ready'

  return (
    <div className={`app mode-${mode}`}>
      <div ref={containerRef} className="map" />
      {basemap?.name === 'fallback' && <div className="notice">Basemap unavailable — showing data layers only.</div>}
      <Toasts toasts={toasts} onDismiss={dismissToast} onPick={pickEvent} />
      {!isLive && (
        <PlaybackBar
          start={playback.start}
          end={playback.end}
          t={playback.t}
          playing={playback.playing}
          speed={playback.speed}
          count={playback.count}
          disabled={!historyReady}
          onTogglePlay={playback.togglePlay}
          onSeek={playback.seek}
          onSpeed={playback.setSpeed}
        />
      )}
      <Panel
        status={<StatusBadge socket={live.socket} count={isLive ? live.count : playback.count} />}
        expanded={expanded}
        onToggle={() => setExpanded((x) => !x)}
      >
        <ModeSwitch mode={mode} onChange={changeMode} />
        {!isLive && range && <HistoryWindow range={range} status={playback.status} onLoad={setRange} />}
        {selectedId ? (
          <AircraftDetails
            key={selectedId}
            icao24={selectedId}
            live={isLive ? live.selected : playback.selected}
            clock={isLive ? undefined : playback.t}
            onClose={() => select(null)}
          />
        ) : (
          <p className="card muted hint">
            {isLive
              ? 'Click an aircraft for details and its 30-minute track. Pan or zoom: only the visible area is streamed.'
              : 'Press play to replay the window. Click an aircraft to follow its path.'}
          </p>
        )}
        <GeofencePanel
          zones={geofences.zones}
          error={geofences.error}
          draw={draw.state}
          onStartDraw={draw.start}
          onCancelDraw={draw.reset}
          onSave={saveZone}
          onToggle={(id, active) => void geofences.setActive(id, active)}
          onDelete={(id) => void geofences.remove(id)}
        />
        <EventFeed events={live.events} onPick={pickEvent} />
        <LayerPanel visibility={visibility} onChange={toggleLayer} />
      </Panel>
    </div>
  )
}
