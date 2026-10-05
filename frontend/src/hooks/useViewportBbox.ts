import type { Map as MapLibreMap } from 'maplibre-gl'
import { type RefObject, useCallback, useRef, useSyncExternalStore } from 'react'
import { boundsToBbox, sameBbox } from '../lib/bbox'
import type { Bbox } from '../lib/types'

export const SUBSCRIBE_PADDING = 0.1

/**
 * The viewport bbox as React state. The map is an external store: `subscribe` listens to
 * `moveend` (not `move`, which fires every frame), `getSnapshot` must return the *same*
 * array while the bbox is unchanged or React would re-render forever.
 */
export function useViewportBbox(mapRef: RefObject<MapLibreMap | null>, ready: boolean): Bbox | null {
  const cache = useRef<Bbox | null>(null)

  const subscribe = useCallback(
    (onChange: () => void) => {
      const map = mapRef.current
      if (!ready || !map) return () => {}
      map.on('moveend', onChange)
      return () => {
        map.off('moveend', onChange)
      }
    },
    [mapRef, ready],
  )

  const getSnapshot = useCallback(() => {
    const map = mapRef.current
    if (!ready || !map) return null
    const b = map.getBounds()
    const next = boundsToBbox(b.getWest(), b.getSouth(), b.getEast(), b.getNorth(), SUBSCRIBE_PADDING)
    if (!sameBbox(cache.current, next)) cache.current = next
    return cache.current
  }, [mapRef, ready])

  return useSyncExternalStore(subscribe, getSnapshot)
}
