import { AttributionControl, Map as MapLibreMap, NavigationControl, ScaleControl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { type RefObject, useEffect, useRef, useState } from 'react'
import { type Basemap, loadBasemap } from '../lib/basemap'
import type { Bbox } from '../lib/types'
import { installLayers } from '../map/layers'
import '../map/worker'

/** Initial view: the region the ingest covers (BBOX_* in .env.example). */
export const REGION_BBOX: Bbox = [26.0, 39.5, 31.5, 42.0]

/**
 * Owns the MapLibre instance. The map is an imperative object with its own render loop and
 * internal state, so it lives in a ref: putting it in React state would re-render the tree
 * on every assignment and invite React to "own" something it cannot diff. React only learns
 * *that* the map is ready (`basemap` becomes non-null) and keeps rendering the UI around it.
 */
export function useMapLibre(containerRef: RefObject<HTMLDivElement | null>) {
  const mapRef = useRef<MapLibreMap | null>(null)
  const [basemap, setBasemap] = useState<Basemap | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let disposed = false
    let map: MapLibreMap | null = null

    void loadBasemap().then((loaded) => {
      if (disposed) return // StrictMode unmounted us while the style was loading
      map = new MapLibreMap({
        container,
        style: loaded.style,
        bounds: REGION_BBOX,
        fitBoundsOptions: { padding: 16 },
        attributionControl: false,
        maxPitch: 0,
      })
      mapRef.current = map
      // dev only: inspect the map from the browser console and from the smoke test
      if (import.meta.env.DEV) Object.assign(window, { __map: map })
      map.addControl(new NavigationControl({ showCompass: true, visualizePitch: false }), 'top-left')
      map.addControl(new AttributionControl({ compact: true }), 'bottom-right')
      map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left')
      map.on('load', () => {
        if (!map) return
        installLayers(map, loaded.font)
        setBasemap(loaded)
      })
    })

    // effects synchronise with an external system; cleanup undoes exactly what setup did
    return () => {
      disposed = true
      map?.remove()
      mapRef.current = null
    }
  }, [containerRef])

  return { mapRef, basemap }
}
