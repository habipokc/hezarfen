import type { Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useEffect, useState } from 'react'
import { HILLSHADE_LAYER, type HillshadeMeta, installHillshade } from '../map/layers'

export type HillshadeStatus =
  | { status: 'loading' }
  | { status: 'missing' }
  | { status: 'ready'; source: HillshadeMeta['source'] }

/**
 * Hillshade raster tiles written by `make dem`. Their meta.json says whether they exist (and
 * whether they come from real or synthetic terrain); without it the layer is not added, so the
 * map does not request hundreds of missing tiles.
 */
export function useHillshade(
  mapRef: RefObject<MapLibreMap | null>,
  ready: boolean,
  visible: boolean,
  opacity: number,
): HillshadeStatus {
  const [state, setState] = useState<HillshadeStatus>({ status: 'loading' })

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const controller = new AbortController()
    fetch('/tiles/hillshade/meta.json', { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok) return setState({ status: 'missing' })
        const meta = (await r.json()) as HillshadeMeta
        if (!map.getLayer(HILLSHADE_LAYER)) installHillshade(map, meta)
        setState({ status: 'ready', source: meta.source })
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: 'missing' })
      })
    return () => controller.abort()
  }, [mapRef, ready])

  const installed = state.status === 'ready'
  useEffect(() => {
    const map = mapRef.current
    if (!installed || !map) return
    map.setLayoutProperty(HILLSHADE_LAYER, 'visibility', visible ? 'visible' : 'none')
    map.setPaintProperty(HILLSHADE_LAYER, 'raster-opacity', opacity)
  }, [mapRef, installed, visible, opacity])

  return state
}
