import type { Aircraft } from './types'
import type { LineCollection, LonLat, TailProperties } from './playback'

/** Length of the short trail drawn behind every live aircraft. */
export const TAIL_SECONDS = 120

interface Point {
  coord: LonLat
  ts: number
}

/**
 * Short trails for live aircraft, built on the client from the fixes it has already seen
 * (no extra request). `sync` runs on every redraw with the store's aircraft.
 */
export class Tails {
  private readonly points = new Map<string, Point[]>()
  private latest = new Map<string, Aircraft>()

  get size(): number {
    return this.points.size
  }

  clear(): void {
    this.points.clear()
    this.latest.clear()
  }

  sync(aircraft: Iterable<Aircraft>): void {
    const seen = new Map<string, Aircraft>()
    for (const a of aircraft) {
      seen.set(a.icao24, a)
      const list = this.points.get(a.icao24) ?? []
      const last = list[list.length - 1]
      if (!last || a.ts > last.ts) list.push({ coord: [a.lon, a.lat], ts: a.ts })
      const cutoff = a.ts - TAIL_SECONDS
      while (list.length > 0 && list[0]!.ts < cutoff) list.shift()
      this.points.set(a.icao24, list)
    }
    for (const id of this.points.keys()) if (!seen.has(id)) this.points.delete(id)
    this.latest = seen
  }

  toFeatureCollection(): LineCollection<TailProperties> {
    const features: LineCollection<TailProperties>['features'] = []
    for (const [icao24, list] of this.points) {
      const a = this.latest.get(icao24)
      if (!a || list.length < 2) continue
      features.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: list.map((p) => p.coord) },
        properties: { icao24, baro_alt: a.baro_alt, geo_alt: a.geo_alt, on_ground: a.on_ground },
      })
    }
    return { type: 'FeatureCollection', features }
  }
}
