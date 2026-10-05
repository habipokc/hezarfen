import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { type RefObject, useEffect, useEffectEvent } from 'react'
import { AIRCRAFT_LAYER, AIRCRAFT_SOURCE, type LayerVisibility, setGroupVisibility } from '../map/layers'

const HIT_PX = 10 // forgiving hit box, mostly for fingers
const NARROW = '(max-width: 640px)' // same breakpoint as the bottom sheet in index.css

/** Hover/selection via feature-state, click-to-select, and layer visibility. */
export function useMapInteractions(
  mapRef: RefObject<MapLibreMap | null>,
  ready: boolean,
  selectedId: string | null,
  onSelect: (icao24: string | null) => void,
  visibility: LayerVisibility,
) {
  const select = useEffectEvent((icao24: string | null) => onSelect(icao24))

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    let hovered: string | null = null

    const hitFeature = (e: MapMouseEvent) => {
      const { x, y } = e.point
      return map.queryRenderedFeatures([[x - HIT_PX, y - HIT_PX], [x + HIT_PX, y + HIT_PX]], { layers: [AIRCRAFT_LAYER] })[0]
    }
    const hit = (e: MapMouseEvent) => (hitFeature(e)?.properties.icao24 as string | undefined) ?? null
    const setHover = (id: string | null) => {
      if (id === hovered) return
      if (hovered) map.setFeatureState({ source: AIRCRAFT_SOURCE, id: hovered }, { hover: false })
      if (id) map.setFeatureState({ source: AIRCRAFT_SOURCE, id }, { hover: true })
      hovered = id
      map.getCanvas().style.cursor = id ? 'pointer' : ''
    }
    const onMove = (e: MapMouseEvent) => setHover(hit(e))
    const onClick = (e: MapMouseEvent) => {
      const feature = hitFeature(e)
      select((feature?.properties.icao24 as string | undefined) ?? null)
      // on phones the opening bottom sheet covers the lower half: move the aircraft up
      if (feature?.geometry.type === 'Point' && window.matchMedia(NARROW).matches) {
        const [lon, lat] = feature.geometry.coordinates as [number, number]
        map.easeTo({ center: [lon, lat], offset: [0, -map.getContainer().clientHeight * 0.25] })
      }
    }
    const onLeave = () => setHover(null)

    map.on('mousemove', onMove)
    map.on('click', onClick)
    map.getCanvas().addEventListener('mouseleave', onLeave)
    return () => {
      map.off('mousemove', onMove)
      map.off('click', onClick)
      map.getCanvas().removeEventListener('mouseleave', onLeave)
    }
  }, [mapRef, ready])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map || !selectedId) return
    map.setFeatureState({ source: AIRCRAFT_SOURCE, id: selectedId }, { selected: true })
    return () => {
      try {
        map.setFeatureState({ source: AIRCRAFT_SOURCE, id: selectedId }, { selected: false })
      } catch {
        // the map was already removed (the whole tree is unmounting)
      }
    }
  }, [mapRef, ready, selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (ready && map) setGroupVisibility(map, visibility)
  }, [mapRef, ready, visibility])
}
