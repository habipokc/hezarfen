import type { HillshadeStatus } from '../hooks/useHillshade'
import { ALTITUDE_STOPS, GROUND_COLOR } from '../lib/altitude'
import type { LayerGroup, LayerVisibility } from '../map/layers'

const LABELS: Record<LayerGroup, string> = {
  provinces: 'Provinces',
  airports: 'Airports',
  geofences: 'Zones',
  trails: 'Trails (2 min)',
  callsigns: 'Callsigns (zoom ≥ 8)',
}

export interface HillshadeControl {
  status: HillshadeStatus
  visible: boolean
  opacity: number
  onVisible: (visible: boolean) => void
  onOpacity: (opacity: number) => void
}

interface Props {
  visibility: LayerVisibility
  onChange: (group: LayerGroup, visible: boolean) => void
  hillshade: HillshadeControl
}

export function LayerPanel({ visibility, onChange, hillshade }: Props) {
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
      <h3>Terrain</h3>
      <HillshadeToggle {...hillshade} />
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

function HillshadeToggle({ status, visible, opacity, onVisible, onOpacity }: HillshadeControl) {
  if (status.status === 'missing') {
    return (
      <p className="muted hillshade-note">
        Hillshade not built yet: run <code>make dem</code>.
      </p>
    )
  }
  const ready = status.status === 'ready'
  return (
    <div className="hillshade">
      <label className="toggle">
        <input type="checkbox" checked={visible} disabled={!ready} onChange={(e) => onVisible(e.target.checked)} />
        Hillshade
        {ready && status.source === 'synthetic' && <span className="badge badge-low">synthetic</span>}
      </label>
      <input
        type="range"
        aria-label="Hillshade opacity"
        min={0.1}
        max={1}
        step={0.05}
        value={opacity}
        disabled={!ready || !visible}
        onChange={(e) => onOpacity(Number(e.target.value))}
      />
    </div>
  )
}
