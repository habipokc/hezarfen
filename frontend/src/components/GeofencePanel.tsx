import { useState } from 'react'
import type { DrawState } from '../hooks/useDrawPolygon'
import type { GeofenceFeature } from '../hooks/useGeofences'
import { checkDrawnPolygon } from '../lib/polygon'
import type { LonLat } from '../lib/playback'

interface Props {
  zones: GeofenceFeature[]
  error: string | null
  draw: DrawState
  /** false until the drawing library has loaded */
  canDraw: boolean
  onStartDraw: () => void
  onCancelDraw: () => void
  onSave: (name: string, ring: LonLat[]) => Promise<string | null>
  onToggle: (id: number, active: boolean) => void
  onDelete: (id: number) => void
}

function SaveForm({ ring, onSave, onCancel }: { ring: LonLat[]; onSave: Props['onSave']; onCancel: () => void }) {
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const problem = checkDrawnPolygon(ring)

  return (
    <form
      className="zone-form"
      onSubmit={(e) => {
        e.preventDefault()
        setSaving(true)
        void onSave(name.trim(), ring).then((err) => {
          setSaving(false)
          setServerError(err)
        })
      }}
    >
      <input
        aria-label="Zone name"
        placeholder="Zone name"
        value={name}
        maxLength={128}
        onChange={(e) => setName(e.target.value)}
        autoFocus
      />
      {(problem ?? serverError) && <p className="error small">{problem ?? serverError}</p>}
      <div className="row">
        <button type="submit" className="button" disabled={saving || !name.trim() || problem !== null}>
          {saving ? 'Saving…' : 'Save zone'}
        </button>
        <button type="button" className="button secondary" onClick={onCancel}>
          Discard
        </button>
      </div>
    </form>
  )
}

export function GeofencePanel({ zones, error, draw, canDraw, onStartDraw, onCancelDraw, onSave, onToggle, onDelete }: Props) {
  return (
    <section className="card" aria-label="Zones">
      <h3>Zones</h3>
      {draw.status === 'idle' && (
        <button type="button" className="button" onClick={onStartDraw} disabled={!canDraw}>
          Draw a zone
        </button>
      )}
      {draw.status === 'drawing' && (
        <div className="row">
          <p className="muted small grow">Click to add corners; click the first corner to finish.</p>
          <button type="button" className="button secondary" onClick={onCancelDraw}>
            Cancel
          </button>
        </div>
      )}
      {draw.status === 'drawn' && <SaveForm ring={draw.ring} onSave={onSave} onCancel={onCancelDraw} />}
      {error && <p className="error small">{error}</p>}
      <ul className="zones">
        {zones.map(({ properties: z }) => (
          <li key={z.id} className={z.active ? '' : 'inactive'}>
            <label className="toggle grow" title={z.active ? 'Active: generates events' : 'Inactive'}>
              <input type="checkbox" checked={z.active} onChange={(e) => onToggle(z.id, e.target.checked)} />
              <span className="zone-name">{z.name}</span>
            </label>
            <span className="muted small">{z.kind === 'user_drawn' ? 'drawn' : z.kind.replace('_', ' ')}</span>
            <button
              type="button"
              className="icon-button small"
              aria-label={`Delete ${z.name}`}
              onClick={() => {
                if (window.confirm(`Delete zone "${z.name}" and its events?`)) onDelete(z.id)
              }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
