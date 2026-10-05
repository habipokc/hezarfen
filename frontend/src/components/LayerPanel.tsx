import { ALTITUDE_STOPS, GROUND_COLOR } from '../lib/altitude'
import type { LayerGroup, LayerVisibility } from '../map/layers'

const LABELS: Record<LayerGroup, string> = {
  provinces: 'Provinces',
  airports: 'Airports',
  geofences: 'Geofences',
  callsigns: 'Callsigns (zoom ≥ 8)',
}

interface Props {
  visibility: LayerVisibility
  onChange: (group: LayerGroup, visible: boolean) => void
}

export function LayerPanel({ visibility, onChange }: Props) {
  return (
    <section className="card" aria-label="Layers">
      <h3>Layers</h3>
      <div className="toggles">
        {(Object.keys(LABELS) as LayerGroup[]).map((group) => (
          <label key={group} className="toggle">
            <input type="checkbox" checked={visibility[group]} onChange={(e) => onChange(group, e.target.checked)} />
            {LABELS[group]}
          </label>
        ))}
      </div>
      <h3>Altitude</h3>
      <div
        className="legend-bar"
        style={{ background: `linear-gradient(to right, ${ALTITUDE_STOPS.map(([, c]) => c).join(', ')})` }}
      />
      <div className="legend-scale muted">
        {ALTITUDE_STOPS.map(([m]) => (
          <span key={m}>{m / 1000} km</span>
        ))}
      </div>
      <p className="muted legend-ground">
        <span className="swatch small" style={{ background: GROUND_COLOR }} /> on ground
      </p>
    </section>
  )
}
