import type { ExpressionSpecification, LayerSpecification, Map as MapLibreMap } from 'maplibre-gl'
import { altitudeColorExpression } from '../lib/altitude'
import { AIRCRAFT_ICON, createAircraftIcon } from './aircraftIcon'

export const AIRCRAFT_SOURCE = 'aircraft'
export const AIRCRAFT_LAYER = 'aircraft'

/** Layer groups the user can switch on and off. */
export const LAYER_GROUPS = {
  provinces: ['provinces-fill', 'provinces-line'],
  airports: ['airports-circle', 'airports-label'],
  geofences: ['geofences-fill', 'geofences-line'],
  callsigns: ['aircraft-label'],
} as const
export type LayerGroup = keyof typeof LAYER_GROUPS
export type LayerVisibility = Record<LayerGroup, boolean>

// GeoJSON is fetched inside a web worker, where a relative URL would resolve against the
// worker's blob: URL; make it absolute against the page.
const api = (path: string) => new URL(path, window.location.href).href

const halo = { 'text-halo-color': '#0b1220', 'text-halo-width': 1.2 }
const hoverOrSelected = (selected: number, hover: number): ExpressionSpecification => [
  'case',
  ['boolean', ['feature-state', 'selected'], false],
  selected,
  ['boolean', ['feature-state', 'hover'], false],
  hover,
  0,
]

function referenceLayers(font: string[]): LayerSpecification[] {
  return [
    { id: 'provinces-fill', type: 'fill', source: 'provinces', paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.04 } },
    {
      id: 'provinces-line', type: 'line', source: 'provinces',
      paint: { 'line-color': '#38bdf8', 'line-opacity': 0.35, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 10, 1.2] },
    },
    { id: 'geofences-fill', type: 'fill', source: 'geofences', paint: { 'fill-color': '#ef4444', 'fill-opacity': 0.1 } },
    {
      id: 'geofences-line', type: 'line', source: 'geofences',
      paint: { 'line-color': '#f87171', 'line-width': 1.5, 'line-dasharray': [3, 2] },
    },
    {
      id: 'airports-circle', type: 'circle', source: 'airports',
      paint: {
        'circle-radius': ['match', ['get', 'type'], 'large_airport', 5, 3.5],
        'circle-color': '#e2e8f0',
        'circle-stroke-color': '#0b1220',
        'circle-stroke-width': 1.5,
      },
    },
    {
      id: 'airports-label', type: 'symbol', source: 'airports', minzoom: 7,
      layout: {
        'text-field': ['coalesce', ['get', 'iata_code'], ['get', 'ident']],
        'text-font': font,
        'text-size': 11,
        'text-offset': [0, 0.9],
        'text-anchor': 'top',
      },
      paint: { 'text-color': '#cbd5e1', ...halo },
    },
  ]
}

function aircraftLayers(font: string[]): LayerSpecification[] {
  return [
    {
      // hover/selection ring: feature-state can drive paint, not layout (icon-size)
      id: 'aircraft-highlight', type: 'circle', source: AIRCRAFT_SOURCE,
      paint: {
        'circle-radius': 15,
        'circle-color': '#ffffff',
        'circle-opacity': hoverOrSelected(0.12, 0.06),
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2,
        'circle-stroke-opacity': hoverOrSelected(1, 0.5),
      },
    },
    {
      id: AIRCRAFT_LAYER, type: 'symbol', source: AIRCRAFT_SOURCE,
      layout: {
        'icon-image': AIRCRAFT_ICON,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.55, 10, 0.9],
        'icon-rotate': ['coalesce', ['get', 'heading'], 0],
        // rotate relative to north on the map, not to the screen, so headings stay true when the map is rotated
        'icon-rotation-alignment': 'map',
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
      },
      paint: { 'icon-color': altitudeColorExpression(), 'icon-halo-color': '#0b1220', 'icon-halo-width': 1 },
    },
    {
      id: 'aircraft-label', type: 'symbol', source: AIRCRAFT_SOURCE, minzoom: 8,
      layout: {
        'text-field': ['coalesce', ['get', 'callsign'], ['get', 'icao24']],
        'text-font': font,
        'text-size': 11,
        'text-offset': [0, 1.5],
        'text-anchor': 'top',
        'text-optional': true,
      },
      paint: { 'text-color': '#f1f5f9', ...halo },
    },
  ]
}

/** Add our sources and layers once the basemap style has loaded. */
export function installLayers(map: MapLibreMap, font: string[]): void {
  map.addImage(AIRCRAFT_ICON, createAircraftIcon(), { pixelRatio: 2, sdf: true })
  map.addSource('provinces', { type: 'geojson', data: api('/api/provinces/') })
  map.addSource('airports', { type: 'geojson', data: api('/api/airports/?type=large_airport,medium_airport') })
  map.addSource('geofences', { type: 'geojson', data: api('/api/geofences/?active=true') })
  map.addSource(AIRCRAFT_SOURCE, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
    // feature ids for feature-state come from this property instead of array positions
    promoteId: 'icao24',
  })

  // reference data sits under the basemap's place labels, aircraft above everything
  const firstSymbol = map.getStyle().layers.find((l) => l.type === 'symbol')?.id
  for (const layer of referenceLayers(font)) {
    map.addLayer(layer, layer.type === 'symbol' ? undefined : firstSymbol)
  }
  for (const layer of aircraftLayers(font)) map.addLayer(layer)
}

export function setGroupVisibility(map: MapLibreMap, visibility: LayerVisibility): void {
  for (const [group, layers] of Object.entries(LAYER_GROUPS) as Array<[LayerGroup, readonly string[]]>) {
    for (const id of layers) map.setLayoutProperty(id, 'visibility', visibility[group] ? 'visible' : 'none')
  }
}
