import type { ExpressionSpecification } from 'maplibre-gl'

/** Barometric altitude (m) → colour; low and warm to high and cool, like most flight trackers. */
export const ALTITUDE_STOPS: ReadonlyArray<readonly [number, string]> = [
  [0, '#f97316'],
  [1500, '#facc15'],
  [3000, '#84cc16'],
  [6000, '#22d3ee'],
  [9000, '#3b82f6'],
  [12000, '#c084fc'],
]
export const GROUND_COLOR = '#94a3b8'
export const UNKNOWN_ALTITUDE_COLOR = '#f8fafc'

const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
const hex = (channels: number[]) => '#' + channels.map((c) => Math.round(c).toString(16).padStart(2, '0')).join('')

/** Same mapping as `altitudeColorExpression`, for the UI (legend, detail panel). */
export function altitudeColor(metres: number | null, onGround: boolean): string {
  if (onGround) return GROUND_COLOR
  if (metres === null) return UNKNOWN_ALTITUDE_COLOR
  const first = ALTITUDE_STOPS[0]!
  if (metres <= first[0]) return first[1]
  for (let i = 1; i < ALTITUDE_STOPS.length; i++) {
    const [hi, hiColor] = ALTITUDE_STOPS[i]!
    if (metres <= hi) {
      const [lo, loColor] = ALTITUDE_STOPS[i - 1]!
      const t = (metres - lo) / (hi - lo)
      const [a, b] = [rgb(loColor), rgb(hiColor)]
      return hex(a.map((c, k) => c + (b[k]! - c) * t))
    }
  }
  return ALTITUDE_STOPS.at(-1)![1]
}

/** Data-driven `icon-color`: ground → grey, unknown altitude → white, else interpolate. */
export function altitudeColorExpression(): ExpressionSpecification {
  const altitude: ExpressionSpecification = ['coalesce', ['get', 'baro_alt'], ['get', 'geo_alt']]
  return [
    'case',
    ['==', ['get', 'on_ground'], true],
    GROUND_COLOR,
    ['==', altitude, null],
    UNKNOWN_ALTITUDE_COLOR,
    ['interpolate', ['linear'], altitude, ...ALTITUDE_STOPS.flat()],
  ] as ExpressionSpecification
}
