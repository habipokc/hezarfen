export interface HealthResponse {
  status: 'ok' | 'degraded'
  checks: Record<string, string>
}

export function describeHealth(body: HealthResponse): string {
  const parts = Object.entries(body.checks)
    .map(([name, value]) => `${name}: ${value}`)
    .join(', ')
  return `backend ${body.status} (${parts})`
}
