import type { LonLat } from './playback'
import type { Bbox } from './types'

// Same limits as backend/geofencing/validation.py; the server stays the authority.
export const MAX_VERTICES = 1000
export const MIN_AREA_KM2 = 0.25
export const MAX_AREA_KM2 = 20_000
const REGION: Bbox = [26.0, 39.5, 31.5, 42.0]
const EARTH_RADIUS_KM = 6371.0088

const rad = (deg: number) => (deg * Math.PI) / 180

/**
 * Area of a lon/lat ring on a sphere (the formula used by d3-geo and turf): each edge
 * contributes Δλ·(2 + sin φ1 + sin φ2), and half the sum times R² is the enclosed area.
 */
export function ringAreaKm2(ring: LonLat[]): number {
  let sum = 0
  for (let i = 0; i < ring.length - 1; i++) {
    const [l1, p1] = ring[i]!
    const [l2, p2] = ring[i + 1]!
    sum += rad(l2 - l1) * (2 + Math.sin(rad(p1)) + Math.sin(rad(p2)))
  }
  return Math.abs((sum * EARTH_RADIUS_KM * EARTH_RADIUS_KM) / 2)
}

/** Quick feedback before the POST; returns a reason or null when the ring looks acceptable. */
export function checkDrawnPolygon(ring: LonLat[]): string | null {
  const closed = ring.length > 1 && ring[0]![0] === ring[ring.length - 1]![0] && ring[0]![1] === ring[ring.length - 1]![1]
  const corners = new Set((closed ? ring.slice(0, -1) : ring).map(([x, y]) => `${x},${y}`)).size
  if (corners < 3) return 'A zone needs at least three distinct corners.'
  if (corners > MAX_VERTICES) return `A zone can have at most ${MAX_VERTICES} corners.`
  const area = ringAreaKm2(closed ? ring : [...ring, ring[0]!])
  if (area < MIN_AREA_KM2) return `Zone is too small (${area.toFixed(2)} km², minimum ${MIN_AREA_KM2}).`
  if (area > MAX_AREA_KM2) return `Zone is too large (${Math.round(area).toLocaleString('en')} km², maximum ${MAX_AREA_KM2.toLocaleString('en')}).`
  const lons = ring.map(([x]) => x)
  const lats = ring.map(([, y]) => y)
  const [w, s, e, n] = REGION
  if (Math.max(...lons) < w || Math.min(...lons) > e || Math.max(...lats) < s || Math.min(...lats) > n) {
    return 'Zone is outside the covered region.'
  }
  return null
}
