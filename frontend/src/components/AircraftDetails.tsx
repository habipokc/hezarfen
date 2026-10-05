import { useAircraftDetail } from '../hooks/useAircraftDetail'
import { useElevation } from '../hooks/useElevation'
import { useNow } from '../hooks/useNow'
import { altitudeColor } from '../lib/altitude'
import { formatAge, formatAltitude, formatDistance, formatHeading, formatSpeed, formatVrate } from '../lib/format'
import type { LonLat } from '../lib/playback'
import { aboveGround, isLowFlight, nearAirport } from '../lib/terrain'
import type { Aircraft } from '../lib/types'

interface Props {
  icao24: string
  live: Aircraft | null
  /** History mode: the simulated time (ages are relative to it, not to the wall clock). */
  clock?: number
  /** Airport buffer zones: low flying is expected there, so no "low" badge inside them. */
  airportRings: LonLat[][]
  onClose: () => void
}

export function AircraftDetails({ icao24, live, clock, airportRings, onClose }: Props) {
  const { detail, error } = useAircraftDetail(icao24)
  // live fields come from the socket (fresh every update), the rest from REST
  const a = live ?? detail
  const wall = useNow(1000, clock === undefined) / 1000
  const now = clock ?? wall
  const terrain = useElevation(a?.lon ?? null, a?.lat ?? null)
  const above = a ? aboveGround(a, terrain.elevation) : null
  // REST's nearest airport describes the live position, not a replayed one
  const nearestM = clock === undefined ? (detail?.nearest_airport?.distance_m ?? null) : null
  const low = a !== null && isLowFlight(a, above?.agl ?? null, nearAirport(a.lon, a.lat, airportRings, nearestM))

  return (
    <section className="card details" aria-label="Aircraft details">
      <header className="details-header">
        <span className="swatch" style={{ background: a ? altitudeColor(a.baro_alt ?? a.geo_alt, a.on_ground) : undefined }} />
        <div>
          <h2>
            {a?.callsign ?? icao24}
            {low && (
              <span className="badge badge-low" title="Less than 300 m above the terrain and more than 10 km from airports">
                Low flight
              </span>
            )}
          </h2>
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
          <dt>Terrain</dt>
          <dd>{terrain.known ? (terrain.elevation === null ? 'no data' : formatAltitude(terrain.elevation)) : (terrain.error ?? '…')}</dd>
          <dt>Above ground</dt>
          {/* "Altitude" above is barometric; AGL uses the GNSS altitude, so they need not add up */}
          <dd title="GNSS altitude minus the terrain elevation (Copernicus DEM, ±40 m)">
            {a.on_ground
              ? 'on ground'
              : above
                ? `${formatAltitude(above.agl)}${above.basis === 'baro' ? ' (baro)' : ''}`
                : terrain.known ? '—' : '…'}
          </dd>
          <dt>Speed</dt>
          <dd>{formatSpeed(a.velocity)}</dd>
          <dt>Heading</dt>
          <dd>{formatHeading(a.heading)}</dd>
          <dt>Vertical</dt>
          <dd>{formatVrate(a.vrate)}</dd>
          <dt>Squawk</dt>
          <dd className="mono">{a.squawk ?? '—'}</dd>
          {/* REST describes where the aircraft is now, which is wrong for a replayed moment */}
          {clock === undefined && (
            <>
              <dt>Province</dt>
              <dd>{detail ? (detail.province ?? 'over sea / abroad') : '…'}</dd>
              <dt>Nearest airport</dt>
              <dd>
                {detail?.nearest_airport
                  ? `${detail.nearest_airport.name} (${formatDistance(detail.nearest_airport.distance_m)})`
                  : detail ? '—' : '…'}
              </dd>
            </>
          )}
          <dt>Last seen</dt>
          <dd>
            {formatAge(a.ts, now)}
            {!live && (clock === undefined ? ' · not in view' : ' · not in this frame')}
          </dd>
        </dl>
      )}
    </section>
  )
}
