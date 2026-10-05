import { signedDistanceAlpha } from './sdf'

export const AIRCRAFT_ICON = 'aircraft'
const SIZE = 64 // drawn at 2× and registered with pixelRatio 2 → 32 CSS px

// Top view of an airliner pointing north (heading 0), in a 64×64 box.
const OUTLINE: Array<[number, number]> = [
  [32, 4], [35, 9], [35, 24], [60, 37], [60, 41], [35, 34], [35, 50], [43, 56], [43, 59],
  [32, 56], [21, 59], [21, 56], [29, 50], [29, 34], [4, 41], [4, 37], [29, 24], [29, 9],
]

/** Rasterise the silhouette on a canvas and turn it into an SDF image for `map.addImage`. */
export function createAircraftIcon(): { width: number; height: number; data: Uint8Array } {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('2d canvas unavailable')
  ctx.beginPath()
  for (const [x, y] of OUTLINE) ctx.lineTo(x, y)
  ctx.closePath()
  ctx.fill()

  const pixels = ctx.getImageData(0, 0, SIZE, SIZE).data
  const mask = Array.from({ length: SIZE * SIZE }, (_, i) => pixels[i * 4 + 3]! >= 128)
  const alpha = signedDistanceAlpha(mask, SIZE, SIZE, 6)
  const data = new Uint8Array(SIZE * SIZE * 4)
  for (let i = 0; i < SIZE * SIZE; i++) {
    data.set([255, 255, 255, alpha[i]!], i * 4)
  }
  return { width: SIZE, height: SIZE, data }
}
