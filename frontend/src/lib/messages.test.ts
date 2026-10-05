import { describe, expect, it } from 'vitest'
import { parseServerMessage } from './messages'
import { aircraft } from './testing'

describe('parseServerMessage', () => {
  it('accepts every documented frame type', () => {
    const frames = [
      { type: 'snapshot', ts: 1, aircraft: [aircraft('aaaaaa')] },
      { type: 'delta', ts: 1, upserts: [], removes: ['aaaaaa'] },
      { type: 'heartbeat', ts: 1 },
      { type: 'error', code: 'invalid_bbox', message: 'nope' },
      {
        type: 'geofence_event', id: 7, geofence: { id: 1, name: 'LTFM 15 km' }, icao24: 'aaaaaa',
        callsign: null, event: 'enter', ts: 1, lon: 28.8, lat: 41.2,
      },
    ]
    for (const frame of frames) {
      expect(parseServerMessage(JSON.stringify(frame))).toEqual(frame)
    }
  })

  it('rejects malformed JSON, unknown types and missing payloads', () => {
    for (const text of [
      '{nope',
      '[]',
      'null',
      '{"type":"hello"}',
      '{"type":"snapshot","ts":1}',
      '{"type":"delta","ts":1,"upserts":[]}',
      '{"type":"geofence_event","id":1}',
    ]) {
      expect(parseServerMessage(text)).toBeNull()
    }
  })
})
