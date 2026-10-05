import { useEffect } from 'react'
import { TOAST_MS, type Toast } from '../lib/toasts'
import type { GeofenceEvent } from '../lib/types'

interface Props {
  toasts: Toast[]
  onDismiss: (id: number) => void
  onPick: (event: GeofenceEvent) => void
}

function ToastItem({ toast, onDismiss, onPick }: { toast: Toast } & Omit<Props, 'toasts'>) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), TOAST_MS)
    return () => clearTimeout(timer)
  }, [toast.id, onDismiss])

  return (
    <li className={`toast toast-${toast.kind}`}>
      <button type="button" onClick={() => onPick(toast.event)}>
        <span className={`badge badge-${toast.kind}`}>{toast.kind}</span>
        {toast.text}
      </button>
    </li>
  )
}

/** Live geofence events, top of the map, newest first; each disappears after a few seconds. */
export function Toasts({ toasts, onDismiss, onPick }: Props) {
  return (
    <ul className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} onPick={onPick} />
      ))}
    </ul>
  )
}
