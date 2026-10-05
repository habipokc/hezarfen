import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { backoffDelay } from '../lib/backoff'
import { parseServerMessage } from '../lib/messages'
import type { Bbox, ServerMessage } from '../lib/types'

/** No frame for this long (3 missed 15 s heartbeats) → treat the socket as dead. */
const WATCHDOG_MS = 45_000

export type SocketState =
  | { status: 'connecting' }
  | { status: 'live' } // subscribed and the snapshot arrived
  | { status: 'waiting'; retryAt: number; attempt: number }
  | { status: 'paused' } // closed on purpose (history mode)

export const liveSocketUrl = () =>
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/live/`

const subscribeFrame = (bbox: Bbox) => JSON.stringify({ type: 'subscribe', bbox })

/**
 * One WebSocket to `/ws/live/` for the component's lifetime: subscribes with the current
 * bbox on open and on every bbox change, reconnects with exponential backoff, and closes a
 * silent socket after the watchdog fires (a dead TCP connection may never emit `close`).
 * `enabled = false` closes the socket and keeps it closed until enabled again.
 */
export function useLiveSocket(
  url: string,
  bbox: Bbox | null,
  onMessage: (m: ServerMessage) => void,
  enabled = true,
): SocketState {
  const [state, setState] = useState<SocketState>({ status: 'connecting' })
  const socketRef = useRef<WebSocket | null>(null)

  // effect events see the latest props without making the connection effect depend on them
  const deliver = useEffectEvent((m: ServerMessage) => onMessage(m))
  const subscribeCurrent = useEffectEvent((ws: WebSocket) => {
    if (bbox) ws.send(subscribeFrame(bbox))
  })

  useEffect(() => {
    if (!enabled) return
    let disposed = false
    let attempt = 0
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let watchdog: ReturnType<typeof setTimeout> | undefined

    const drop = (ws: WebSocket) => {
      ws.onopen = ws.onmessage = ws.onclose = null
      ws.close()
      if (socketRef.current === ws) socketRef.current = null
      clearTimeout(watchdog)
    }

    const scheduleReconnect = () => {
      if (disposed) return
      const delay = backoffDelay(attempt)
      attempt += 1
      setState({ status: 'waiting', retryAt: Date.now() + delay, attempt })
      retryTimer = setTimeout(() => {
        setState({ status: 'connecting' })
        connect()
      }, delay)
    }

    const connect = () => {
      retryTimer = undefined
      const ws = new WebSocket(url)
      socketRef.current = ws
      const armWatchdog = () => {
        clearTimeout(watchdog)
        watchdog = setTimeout(() => {
          drop(ws)
          scheduleReconnect()
        }, WATCHDOG_MS)
      }
      ws.onopen = () => {
        armWatchdog()
        subscribeCurrent(ws)
      }
      ws.onmessage = (e: MessageEvent<string>) => {
        armWatchdog()
        const message = parseServerMessage(e.data)
        if (!message) return
        if (message.type === 'snapshot') {
          // reset only once data flows: an accept-then-close loop must keep backing off
          attempt = 0
          setState((s) => (s.status === 'live' ? s : { status: 'live' }))
        }
        deliver(message)
      }
      ws.onclose = () => {
        drop(ws)
        scheduleReconnect()
      }
    }

    // coming back online: skip the rest of the backoff wait
    const onOnline = () => {
      if (retryTimer === undefined) return
      clearTimeout(retryTimer)
      setState({ status: 'connecting' })
      connect()
    }

    connect()
    window.addEventListener('online', onOnline)
    return () => {
      disposed = true
      window.removeEventListener('online', onOnline)
      clearTimeout(retryTimer)
      if (socketRef.current) drop(socketRef.current)
      // the next connection (re-enabled, new url) starts from scratch
      setState({ status: 'connecting' })
    }
  }, [url, enabled])

  // a new viewport → new subscribe; the server answers with a fresh snapshot
  useEffect(() => {
    const ws = socketRef.current
    if (bbox && ws?.readyState === WebSocket.OPEN) ws.send(subscribeFrame(bbox))
  }, [bbox])

  return enabled ? state : { status: 'paused' }
}
