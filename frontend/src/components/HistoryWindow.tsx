import { useState } from 'react'
import type { PlaybackStatus, PlaybackWindow } from '../hooks/usePlayback'
import { fromLocalInput, toLocalInput } from '../lib/format'

const LENGTHS = [
  [15, '15 min'],
  [30, '30 min'],
  [60, '1 hour'],
  [120, '2 hours'],
] as const

interface Props {
  range: PlaybackWindow
  status: PlaybackStatus
  onLoad: (range: PlaybackWindow) => void
}

/** Choose which past window to replay: length and end time (local). */
export function HistoryWindow({ range, status, onLoad }: Props) {
  const [minutes, setMinutes] = useState(Math.round((range.end - range.start) / 60))
  const [endInput, setEndInput] = useState(toLocalInput(range.end))
  const end = fromLocalInput(endInput)

  return (
    <section className="card" aria-label="History window">
      <h3>History window</h3>
      <form
        className="history-form"
        onSubmit={(e) => {
          e.preventDefault()
          if (end !== null) onLoad({ start: end - minutes * 60, end })
        }}
      >
        <label>
          Length
          <select value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
            {LENGTHS.map(([m, label]) => (
              <option key={m} value={m}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ends at
          <input type="datetime-local" value={endInput} onChange={(e) => setEndInput(e.target.value)} required />
        </label>
        <button type="submit" className="button" disabled={end === null}>
          Load
        </button>
      </form>
      <p className="muted small">
        {status.status === 'loading' && 'Loading positions…'}
        {status.status === 'error' && <span className="error">Could not load: {status.message}</span>}
        {status.status === 'ready' &&
          (status.fixes === 0
            ? 'No positions recorded in this window.'
            : `${status.aircraft} aircraft, ${status.fixes.toLocaleString('en')} positions. The live feed is paused.`)}
      </p>
    </section>
  )
}
