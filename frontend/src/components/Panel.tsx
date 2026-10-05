import type { ReactNode } from 'react'

interface Props {
  status: ReactNode
  expanded: boolean
  onToggle: () => void
  children: ReactNode
}

/** Side panel on wide screens; bottom sheet (collapsible) on narrow ones — CSS decides. */
export function Panel({ status, expanded, onToggle, children }: Props) {
  return (
    <aside className={`panel ${expanded ? 'expanded' : 'collapsed'}`}>
      <header className="panel-header">
        <button type="button" className="sheet-handle" onClick={onToggle} aria-expanded={expanded} aria-controls="panel-body">
          <span className="sr-only">{expanded ? 'Collapse panel' : 'Expand panel'}</span>
        </button>
        <h1>Hezarfen</h1>
        {status}
      </header>
      <div id="panel-body" className="panel-body">
        {children}
      </div>
    </aside>
  )
}
