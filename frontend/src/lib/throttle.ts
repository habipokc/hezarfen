export interface Throttled {
  (): void
  cancel(): void
}

/**
 * Leading + trailing throttle: the first call runs at once, calls inside the interval
 * collapse into one run at its end. No arguments — callers read the latest state when
 * the function runs, which is exactly what a "redraw" needs.
 */
export function throttle(fn: () => void, intervalMs: number): Throttled {
  let last = -Infinity
  let timer: ReturnType<typeof setTimeout> | null = null

  const run = () => {
    timer = null
    last = Date.now()
    fn()
  }
  const throttled = () => {
    if (timer !== null) return
    const wait = last + intervalMs - Date.now()
    if (wait <= 0) run()
    else timer = setTimeout(run, wait)
  }
  throttled.cancel = () => {
    if (timer !== null) clearTimeout(timer)
    timer = null
  }
  return throttled
}
