export type Mode = 'live' | 'history'

interface Props {
  mode: Mode
  onChange: (mode: Mode) => void
}

export function ModeSwitch({ mode, onChange }: Props) {
  return (
    <div className="segmented mode-switch" role="radiogroup" aria-label="Mode">
      {(['live', 'history'] as const).map((m) => (
        <button key={m} type="button" role="radio" aria-checked={mode === m} className={mode === m ? 'on' : ''} onClick={() => onChange(m)}>
          {m === 'live' ? 'Live' : 'History'}
        </button>
      ))}
    </div>
  )
}
