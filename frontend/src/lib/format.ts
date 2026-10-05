const FT_PER_M = 1 / 0.3048
const KT_PER_MS = 3600 / 1852
const DASH = '—'
const POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

export function formatAltitude(m: number | null): string {
  return m === null ? DASH : `${int.format(m)} m · ${int.format(m * FT_PER_M)} ft`
}

export function formatSpeed(ms: number | null): string {
  return ms === null ? DASH : `${int.format(ms * 3.6)} km/h · ${int.format(ms * KT_PER_MS)} kt`
}

export function formatVrate(ms: number | null): string {
  if (ms === null) return DASH
  const sign = ms > 0 ? '+' : ms < 0 ? '−' : ''
  return `${sign}${Math.abs(ms).toFixed(1)} m/s`
}

export function formatHeading(deg: number | null): string {
  if (deg === null) return DASH
  const rounded = Math.round(deg) % 360
  return `${rounded}° ${POINTS[Math.round(rounded / 45) % 8]}`
}

export function formatDistance(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`
}

export function formatAge(ts: number, now: number): string {
  const s = Math.max(0, Math.round(now - ts))
  if (s === 0) return 'just now'
  if (s < 60) return `${s} s ago`
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  return `${Math.floor(s / 3600)} h ago`
}

export function formatClock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('en-GB', { hour12: false })
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Unix seconds → value of an `<input type="datetime-local">` (local time, minute precision). */
export function toLocalInput(ts: number): string {
  const d = new Date(ts * 1000)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** The reverse of `toLocalInput`; null for an empty or malformed value. */
export function fromLocalInput(value: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value)
  if (!m) return null
  const [, y, mo, d, h, mi] = m.map(Number) as [number, number, number, number, number, number]
  return Math.floor(new Date(y, mo - 1, d, h, mi).getTime() / 1000)
}
