import { describe, expect, it, vi } from 'vitest'
import { BASEMAP_URL, FALLBACK_STYLE, loadBasemap } from './basemap'

const style = { version: 8, glyphs: 'https://example/fonts/{fontstack}/{range}.pbf', sources: {}, layers: [] }

describe('loadBasemap', () => {
  it('uses the OpenFreeMap style when it loads', async () => {
    const fetchFn = vi.fn().mockResolvedValue(new Response(JSON.stringify(style)))
    const basemap = await loadBasemap(fetchFn)
    expect(fetchFn).toHaveBeenCalledWith(BASEMAP_URL, expect.objectContaining({ signal: expect.anything() }))
    expect(basemap.name).toBe('openfreemap')
    expect(basemap.style).toEqual(style)
    expect(basemap.font).toEqual(['Noto Sans Regular'])
  })

  it('falls back on network errors, HTTP errors and invalid styles', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    for (const fetchFn of [
      vi.fn().mockRejectedValue(new TypeError('offline')),
      vi.fn().mockResolvedValue(new Response('nope', { status: 503 })),
      vi.fn().mockResolvedValue(new Response('{"version":7}')),
      vi.fn().mockResolvedValue(new Response('<html>')),
    ]) {
      const basemap = await loadBasemap(fetchFn)
      expect(basemap.name).toBe('fallback')
      expect(basemap.style).toBe(FALLBACK_STYLE)
    }
  })

  it('the fallback style still has glyphs so labels render', () => {
    expect(FALLBACK_STYLE.glyphs).toMatch(/\{fontstack\}/)
  })
})
