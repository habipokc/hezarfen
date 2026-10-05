import type { Aircraft, AircraftFeature } from './types'

export interface AircraftCollection {
  type: 'FeatureCollection'
  features: AircraftFeature[]
}

function toFeature(a: Aircraft): AircraftFeature {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [a.lon, a.lat] }, properties: a }
}

/**
 * Client-side mirror of the live aircraft in the subscribed bbox (ICD §6.2): a snapshot
 * replaces everything, a delta patches it. Features are kept ready-made so building the
 * collection for `setData` is a single pass.
 */
export class LiveStore {
  private readonly features = new Map<string, AircraftFeature>()

  get size(): number {
    return this.features.size
  }

  get(icao24: string): Aircraft | undefined {
    return this.features.get(icao24)?.properties
  }

  clear(): void {
    this.features.clear()
  }

  applySnapshot(aircraft: Aircraft[]): void {
    this.features.clear()
    for (const a of aircraft) this.features.set(a.icao24, toFeature(a))
  }

  applyDelta(upserts: Aircraft[], removes: string[]): void {
    for (const a of upserts) {
      const current = this.features.get(a.icao24)
      // a delta queued just before a snapshot can be older than the snapshot (ICD §6.2)
      if (current && current.properties.ts > a.ts) continue
      this.features.set(a.icao24, toFeature(a))
    }
    for (const icao24 of removes) this.features.delete(icao24)
  }

  toFeatureCollection(): AircraftCollection {
    return { type: 'FeatureCollection', features: Array.from(this.features.values()) }
  }
}
