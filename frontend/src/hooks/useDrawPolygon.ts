import type { Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useCallback, useEffect, useRef, useState } from 'react'
import type { TerraDraw } from 'terra-draw'
import type { LonLat } from '../lib/playback'

export type DrawState = { status: 'idle' } | { status: 'drawing' } | { status: 'drawn'; ring: LonLat[] }

/** terra-draw (~50 kB gzip) in its own chunk, fetched after the map is up instead of delaying the first paint. */
async function loadTerraDraw() {
  const [draw, adapter] = await Promise.all([import('terra-draw'), import('terra-draw-maplibre-gl-adapter')])
  return { ...draw, Adapter: adapter.TerraDrawMapLibreGLAdapter }
}

/**
 * terra-draw in polygon mode. The adapter draws with its own MapLibre sources and layers, so
 * it is created once the style has loaded. Click to add corners; click the first corner (or
 * press Enter) to close. Self-intersecting rings are refused while drawing.
 */
export function useDrawPolygon(mapRef: RefObject<MapLibreMap | null>, ready: boolean) {
  const drawRef = useRef<TerraDraw | null>(null)
  // the click that closes the ring reaches MapLibre after terra-draw has already finished
  const closingClickRef = useRef(false)
  const [state, setState] = useState<DrawState>({ status: 'idle' })
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    let draw: TerraDraw | null = null
    let cancelled = false
    void loadTerraDraw().then(({ TerraDraw, TerraDrawPolygonMode, ValidateNotSelfIntersecting, Adapter }) => {
      if (cancelled) return
      draw = new TerraDraw({
        adapter: new Adapter({ map }),
        modes: [
          new TerraDrawPolygonMode({
            validation: (feature) => ValidateNotSelfIntersecting(feature),
            styles: {
              fillColor: '#38bdf8',
              fillOpacity: 0.15,
              outlineColor: '#38bdf8',
              outlineWidth: 2,
              closingPointColor: '#f8fafc',
              closingPointWidth: 5,
              closingPointOutlineColor: '#0b1220',
              closingPointOutlineWidth: 1,
            },
          }),
        ],
      })
      const instance = draw
      instance.start()
      instance.on('finish', (id, context) => {
        if (context.action !== 'draw') return
        closingClickRef.current = true
        // pointerup, mouseup and click are dispatched in one task; a timeout runs after all of them
        setTimeout(() => (closingClickRef.current = false), 0)
        const feature = instance.getSnapshotFeature(id)
        if (feature?.geometry.type !== 'Polygon') return
        // keep the shape on screen (static mode cannot edit it) until it is saved or discarded
        instance.setMode('static')
        setState({ status: 'drawn', ring: feature.geometry.coordinates[0] as LonLat[] })
      })
      drawRef.current = instance
      setLoaded(true)
    })
    return () => {
      cancelled = true
      drawRef.current = null
      setLoaded(false)
      try {
        draw?.stop()
      } catch {
        // the map was removed first
      }
    }
  }, [mapRef, ready])

  const start = useCallback(() => {
    const draw = drawRef.current
    if (!draw) return
    draw.clear()
    draw.setMode('polygon')
    setState({ status: 'drawing' })
  }, [])

  const reset = useCallback(() => {
    const draw = drawRef.current
    if (draw) {
      draw.clear()
      draw.setMode('static')
    }
    setState({ status: 'idle' })
  }, [])

  /** True while map clicks belong to the drawing (corners, the closing click). */
  const capturesClicks = useCallback(
    () => drawRef.current?.getMode() === 'polygon' || closingClickRef.current,
    [],
  )

  return { state, start, reset, capturesClicks, loaded }
}
