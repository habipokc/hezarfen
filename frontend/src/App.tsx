import { useCallback, useRef, useState } from 'react'
import { AircraftDetails } from './components/AircraftDetails'
import { EventFeed } from './components/EventFeed'
import { LayerPanel } from './components/LayerPanel'
import { Panel } from './components/Panel'
import { StatusBadge } from './components/StatusBadge'
import { useLiveAircraft } from './hooks/useLiveAircraft'
import { useMapInteractions } from './hooks/useMapInteractions'
import { useMapLibre } from './hooks/useMapLibre'
import { useViewportBbox } from './hooks/useViewportBbox'
import type { GeofenceEvent } from './lib/types'
import type { LayerGroup, LayerVisibility } from './map/layers'

const INITIAL_VISIBILITY: LayerVisibility = { provinces: true, airports: true, geofences: true, callsigns: true }

export function App() {
  const containerRef = useRef<HTMLDivElement>(null)
  const { mapRef, basemap } = useMapLibre(containerRef)
  const ready = basemap !== null
  const bbox = useViewportBbox(mapRef, ready)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [visibility, setVisibility] = useState(INITIAL_VISIBILITY)
  const [expanded, setExpanded] = useState(false)

  const { socket, count, selected, events } = useLiveAircraft(mapRef, ready, bbox, selectedId)

  const select = useCallback((icao24: string | null) => {
    setSelectedId(icao24)
    if (icao24) setExpanded(true) // open the bottom sheet on mobile
  }, [])
  useMapInteractions(mapRef, ready, selectedId, select, visibility)

  const toggleLayer = useCallback((group: LayerGroup, visible: boolean) => {
    setVisibility((v) => ({ ...v, [group]: visible }))
  }, [])

  const pickEvent = useCallback(
    (e: GeofenceEvent) => {
      const map = mapRef.current
      map?.flyTo({ center: [e.lon, e.lat], zoom: Math.max(map.getZoom(), 9) })
      select(e.icao24)
    },
    [mapRef, select],
  )

  return (
    <div className="app">
      <div ref={containerRef} className="map" />
      {basemap?.name === 'fallback' && <div className="notice">Basemap unavailable — showing data layers only.</div>}
      <Panel status={<StatusBadge socket={socket} count={count} />} expanded={expanded} onToggle={() => setExpanded((x) => !x)}>
        {selectedId ? (
          <AircraftDetails key={selectedId} icao24={selectedId} live={selected} onClose={() => select(null)} />
        ) : (
          <p className="card muted hint">Click an aircraft for details. Pan or zoom: only the visible area is streamed.</p>
        )}
        <LayerPanel visibility={visibility} onChange={toggleLayer} />
        <EventFeed events={events} onPick={pickEvent} />
      </Panel>
    </div>
  )
}
