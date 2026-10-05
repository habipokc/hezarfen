import type { SocketState } from '../hooks/useLiveSocket'
import { useNow } from '../hooks/useNow'

const LABEL = { connecting: 'Connecting…', live: 'Live', waiting: 'Offline' } as const

export function StatusBadge({ socket, count }: { socket: SocketState; count: number }) {
  // tick only while a countdown is visible
  const now = useNow(500, socket.status === 'waiting')

  const detail =
    socket.status === 'waiting'
      ? `retry in ${Math.max(0, Math.ceil((socket.retryAt - now) / 1000))} s`
      : socket.status === 'live'
        ? `${count} aircraft`
        : null

  return (
    <span className={`status status-${socket.status}`} role="status" aria-live="polite">
      <span className="status-dot" aria-hidden="true" />
      {LABEL[socket.status]}
      {detail && <span className="status-detail"> · {detail}</span>}
    </span>
  )
}
