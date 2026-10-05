import { describe, expect, it } from 'vitest'
import { apiErrorMessage } from './api'

describe('apiErrorMessage', () => {
  it('reads the ICD error envelope', () => {
    const body = { error: { code: 'invalid_geometry', message: 'polygon is too small', details: {} } }
    expect(apiErrorMessage(body, 400)).toBe('polygon is too small')
  })

  it('falls back to the HTTP status for anything else', () => {
    expect(apiErrorMessage('<html>', 502)).toBe('HTTP 502')
    expect(apiErrorMessage(null, 500)).toBe('HTTP 500')
  })
})
