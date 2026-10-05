export const BACKOFF_BASE_MS = 500
export const BACKOFF_MAX_MS = 30_000

/**
 * Reconnect delay for attempt n (0-based): "full jitter" exponential backoff, a random
 * delay in [base, min(max, base·2ⁿ)]. The jitter keeps many tabs from reconnecting in
 * lock-step after a server restart.
 */
export function backoffDelay(attempt: number, random: () => number = Math.random): number {
  const ceiling = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.min(attempt, 16))
  return Math.max(BACKOFF_BASE_MS, Math.round(ceiling * random()))
}
