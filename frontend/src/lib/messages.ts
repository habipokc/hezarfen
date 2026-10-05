import type { ServerMessage } from './types'

type Json = Record<string, unknown>

const isNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isString = (v: unknown): v is string => typeof v === 'string'

// Shallow structural checks: enough to make the union narrowing honest without paying for a
// full schema validator on every frame (the server is ours and follows the ICD).
const validators: Record<ServerMessage['type'], (m: Json) => boolean> = {
  snapshot: (m) => isNumber(m.ts) && Array.isArray(m.aircraft),
  delta: (m) => isNumber(m.ts) && Array.isArray(m.upserts) && Array.isArray(m.removes),
  geofence_event: (m) =>
    isNumber(m.id) && isString(m.icao24) && (m.event === 'enter' || m.event === 'exit') &&
    typeof m.geofence === 'object' && m.geofence !== null,
  heartbeat: (m) => isNumber(m.ts),
  error: (m) => isString(m.code) && isString(m.message),
}

/** Parse one `/ws/live/` text frame; `null` for anything that is not a documented message. */
export function parseServerMessage(text: string): ServerMessage | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const message = value as Json
  const validate = validators[message.type as ServerMessage['type']]
  return validate?.(message) ? (message as unknown as ServerMessage) : null
}
