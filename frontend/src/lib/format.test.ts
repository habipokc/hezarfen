import { describe, expect, it } from 'vitest'
import {
  formatAge,
  formatAltitude,
  formatDistance,
  formatHeading,
  formatSpeed,
  formatVrate,
  fromLocalInput,
  toLocalInput,
} from './format'

describe('formatters', () => {
  it('altitude in metres and feet', () => {
    expect(formatAltitude(3350)).toBe('3,350 m · 10,991 ft')
    expect(formatAltitude(null)).toBe('—')
  })

  it('speed in km/h and knots', () => {
    expect(formatSpeed(152.3)).toBe('548 km/h · 296 kt')
    expect(formatSpeed(null)).toBe('—')
  })

  it('vertical rate with a sign', () => {
    expect(formatVrate(6.5)).toBe('+6.5 m/s')
    expect(formatVrate(-3)).toBe('−3.0 m/s')
    expect(formatVrate(0)).toBe('0.0 m/s')
    expect(formatVrate(null)).toBe('—')
  })

  it('heading as degrees and compass point', () => {
    expect(formatHeading(87.4)).toBe('87° E')
    expect(formatHeading(359.6)).toBe('0° N')
    expect(formatHeading(225)).toBe('225° SW')
    expect(formatHeading(null)).toBe('—')
  })

  it('distance in metres below 1 km, km above', () => {
    expect(formatDistance(850)).toBe('850 m')
    expect(formatDistance(11189)).toBe('11.2 km')
  })

  it('age relative to now', () => {
    expect(formatAge(100, 103)).toBe('3 s ago')
    expect(formatAge(100, 100)).toBe('just now')
    expect(formatAge(100, 100 + 125)).toBe('2 min ago')
    expect(formatAge(100, 100 + 7300)).toBe('2 h ago')
  })
})

describe('datetime-local values', () => {
  it('round-trips to the minute', () => {
    const ts = 1_791_187_245 // :45 seconds are dropped
    expect(toLocalInput(ts)).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(fromLocalInput(toLocalInput(ts))).toBe(ts - 45)
  })

  it('rejects empty or malformed input', () => {
    expect(fromLocalInput('')).toBeNull()
    expect(fromLocalInput('2026-10-05 12:00')).toBeNull()
  })
})
