/** Alpha value MapLibre's SDF shader treats as the glyph/icon edge (cutoff 0.25 → 191). */
export const SDF_EDGE = 191

/**
 * Brute-force signed distance field for a small binary mask: each pixel gets the distance
 * to the nearest pixel on the other side of the edge, encoded like tiny-sdf
 * (inside → towards 255, edge ≈ 191, `radius` pixels outside → 0). Run once at startup on a
 * 64×64 icon, so O(w·h·r²) is fine. A real SDF (not just a mask) lets MapLibre draw a crisp
 * edge at any size and recolour the icon with `icon-color`.
 */
export function signedDistanceAlpha(mask: ArrayLike<boolean>, width: number, height: number, radius: number): Uint8ClampedArray {
  const out = new Uint8ClampedArray(width * height)
  const r = Math.ceil(radius)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const inside = mask[y * width + x]!
      let best = radius
      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          const [nx, ny] = [x + dx, y + dy]
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
            if (inside) best = Math.min(best, Math.hypot(dx, dy) - 0.5) // image border counts as outside
            continue
          }
          if (mask[ny * width + nx] !== inside) best = Math.min(best, Math.hypot(dx, dy) - 0.5)
        }
      }
      const signed = inside ? -best : best // negative inside
      out[y * width + x] = Math.round(255 * (1 - (signed / radius + 0.25)))
    }
  }
  return out
}
