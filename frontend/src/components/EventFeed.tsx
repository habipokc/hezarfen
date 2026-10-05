import { formatClock } from '../lib/format'
import type { GeofenceEvent } from '../lib/types'

interface Props {
  events: GeofenceEvent[]
  onPick: (event: GeofenceEvent) => void
}

export function EventFeed({ events, onPick }: Props) {
  return (
    <section className="card" aria-label="Geofence events">
      <h3>Geofence events</h3>
      {events.length === 0 ? (
        <p className="muted">Waiting for enter/exit events…</p>
      ) : (
        <ul className="events">
          {events.map((e) => (
            <li key={e.id}>
              <button type="button" onClick={() => onPick(e)}>
                <span className="mono muted">{formatClock(e.ts)}</span>
                <span className={`badge badge-${e.event}`}>{e.event}</span>
                <span className="event-text">
                  {e.callsign ?? e.icao24} · {e.geofence.name}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
