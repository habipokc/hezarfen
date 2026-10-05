import type { StyleSpecification } from 'maplibre-gl'

export const BASEMAP_URL = 'https://tiles.openfreemap.org/styles/dark'
const TIMEOUT_MS = 5000

/**
 * Used when OpenFreeMap is unreachable (offline, outage): a plain background, so the data
 * layers (provinces, aircraft) still render on their own. demotiles glyphs keep labels.
 */
export const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#0b1220' } }],
}

export interface Basemap {
  name: 'openfreemap' | 'fallback'
  style: StyleSpecification
  /** text-font stack that exists on this style's glyph server */
  font: string[]
}

type FetchFn = (url: string, init?: RequestInit) => Promise<Response>

/**
 * Fetch the style JSON ourselves instead of handing MapLibre a URL: a URL that fails
 * leaves the map blank with only an 'error' event, while here we can decide on a fallback
 * before the map is created.
 */
export async function loadBasemap(fetchFn: FetchFn = fetch): Promise<Basemap> {
  try {
    const response = await fetchFn(BASEMAP_URL, { signal: AbortSignal.timeout(TIMEOUT_MS) })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const style = (await response.json()) as StyleSpecification
    if (style.version !== 8 || !Array.isArray(style.layers)) throw new Error('not a v8 style')
    return { name: 'openfreemap', style, font: ['Noto Sans Regular'] }
  } catch (err) {
    console.warn('basemap unavailable, using fallback style:', err)
    return { name: 'fallback', style: FALLBACK_STYLE, font: ['Open Sans Semibold'] }
  }
}
