import { SPEEDS, type Speed } from '../hooks/usePlayback'
import { formatClock } from '../lib/format'

interface Props {
  start: number
  end: number
  t: number
  playing: boolean
  speed: Speed
  count: number
  disabled: boolean
  onTogglePlay: () => void
  onSeek: (t: number) => void
  onSpeed: (s: Speed) => void
}

/** Floating transport bar over the map: play/pause, speed, time slider. */
export function PlaybackBar({ start, end, t, playing, speed, count, disabled, onTogglePlay, onSeek, onSpeed }: Props) {
  return (
    <div className="playback-bar" role="group" aria-label="Playback">
      <div className="playback-row">
        <button type="button" className="play" onClick={onTogglePlay} disabled={disabled} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '❚❚' : '▶'}
        </button>
        <span className="mono playback-time">{disabled ? '--:--:--' : formatClock(t)}</span>
        <span className="muted playback-count">{disabled ? '' : `${count} aircraft`}</span>
        <div className="segmented" role="radiogroup" aria-label="Speed">
          {SPEEDS.map((s) => (
            <button key={s} type="button" role="radio" aria-checked={speed === s} className={speed === s ? 'on' : ''} onClick={() => onSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
      </div>
      <input
        type="range"
        className="playback-slider"
        aria-label="Time"
        min={start}
        max={end}
        step={1}
        value={Math.round(t)}
        disabled={disabled}
        onChange={(e) => onSeek(Number(e.target.value))}
      />
      <div className="playback-row muted playback-ends">
        <span className="mono">{disabled ? '' : formatClock(start)}</span>
        <span className="mono">{disabled ? '' : formatClock(end)}</span>
      </div>
    </div>
  )
}
