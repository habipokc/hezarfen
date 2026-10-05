import type { GeofenceEvent } from './types'

export const MAX_TOASTS = 4
export const TOAST_MS = 6000

export interface Toast {
  id: number
  text: string
  kind: GeofenceEvent['event']
  event: GeofenceEvent
}

export function eventToast(e: GeofenceEvent): Toast {
  const verb = e.event === 'enter' ? 'entered' : 'left'
  return { id: e.id, text: `${e.callsign ?? e.icao24} ${verb} ${e.geofence.name}`, kind: e.event, event: e }
}

/** Newest first, at most MAX_TOASTS; an event already on screen is not shown twice. */
export function pushToast(list: Toast[], toast: Toast): Toast[] {
  if (list.some((t) => t.id === toast.id)) return list
  return [toast, ...list].slice(0, MAX_TOASTS)
}
