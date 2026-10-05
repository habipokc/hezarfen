import { useAircraftDetail } from '../hooks/useAircraftDetail'
import { useNow } from '../hooks/useNow'
import { altitudeColor } from '../lib/altitude'
import { formatAge, formatAltitude, formatDistance, formatHeading, formatSpeed, formatVrate } from '../lib/format'
import type { Aircraft } from '../lib/types'

interface Props {
  icao24: string
  live: Aircraft | null
  onClose: () => void
}

export function AircraftDetails({ icao24, live, onClose }: Props) {
  const { detail, error } = useAircraftDetail(icao24)
  // live fields come from the socket (fresh every update), the rest from REST
  const a = live ?? detail
  const now = useNow(1000) / 1000

  return (
    <section className="card details" aria-label="Aircraft details">
      <header className="details-header">
        <span className="swatch" style={{ background: a ? altitudeColor(a.baro_alt ?? a.geo_alt, a.on_ground) : undefined }} />
        <div>
          <h2>{a?.callsign ?? icao24}</h2>
          <p className="muted mono">
            {icao24}
            {detail?.origin_country && ` · ${detail.origin_country}`}
          </p>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close details">
          ×
        </button>
      </header>

      {!a && !error && <p className="muted">Loading…</p>}
      {error && !a && <p className="error">Could not load details ({error}).</p>}
      {a && (
        <dl className="facts">
          <dt>Altitude</dt>
          <dd>{a.on_ground ? 'on ground' : formatAltitude(a.baro_alt ?? a.geo_alt)}</dd>
          <dt>Speed</dt>
          <dd>{formatSpeed(a.velocity)}</dd>
          <dt>Heading</dt>
          <dd>{formatHeading(a.heading)}</dd>
          <dt>Vertical</dt>
          <dd>{formatVrate(a.vrate)}</dd>
          <dt>Squawk</dt>
          <dd className="mono">{a.squawk ?? '—'}</dd>
          <dt>Province</dt>
          <dd>{detail ? (detail.province ?? 'over sea / abroad') : '…'}</dd>
          <dt>Nearest airport</dt>
          <dd>
            {detail?.nearest_airport
              ? `${detail.nearest_airport.name} (${formatDistance(detail.nearest_airport.distance_m)})`
              : detail ? '—' : '…'}
          </dd>
          <dt>Last seen</dt>
          <dd>
            {formatAge(a.ts, now)}
            {!live && ' · not in view'}
          </dd>
        </dl>
      )}
    </section>
  )
}
