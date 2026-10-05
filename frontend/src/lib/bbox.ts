import type { Bbox } from './types'

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
const round4 = (v: number) => Math.round(v * 1e4) / 1e4
const MIN_SPAN = 1e-3 // keep min < max after rounding, as the server requires

/**
 * Viewport bounds → subscribe bbox: padded by `pad` × span on every side (aircraft just
 * outside the view are already there when the user pans a little), clamped to valid
 * lon/lat ranges and rounded so tiny camera jitter does not produce a "new" bbox.
 */
export function boundsToBbox(west: number, south: number, east: number, north: number, pad: number): Bbox {
  const dx = Math.max(east - west, MIN_SPAN) * pad
  const dy = Math.max(north - south, MIN_SPAN) * pad
  let w = round4(clamp(west - dx, -180, 180))
  let e = round4(clamp(east + dx, -180, 180))
  let s = round4(clamp(south - dy, -90, 90))
  let n = round4(clamp(north + dy, -90, 90))
  if (e - w < MIN_SPAN) [w, e] = [round4(Math.max(-180, w - MIN_SPAN)), round4(Math.min(180, e + MIN_SPAN))]
  if (n - s < MIN_SPAN) [s, n] = [round4(Math.max(-90, s - MIN_SPAN)), round4(Math.min(90, n + MIN_SPAN))]
  return [w, s, e, n]
}

export function sameBbox(a: Bbox | null, b: Bbox | null): boolean {
  return a !== null && b !== null && a.every((v, i) => v === b[i])
}
