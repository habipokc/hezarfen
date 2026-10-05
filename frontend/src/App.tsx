import { useEffect, useState } from 'react'
import { describeHealth, type HealthResponse } from './lib/health'

// Phase 0 placeholder: proves the frontend -> nginx -> backend path works.
// The map arrives in Phase 5.
export function App() {
  const [status, setStatus] = useState('checking backend…')

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/health', { signal: controller.signal })
      .then((r) => r.json() as Promise<HealthResponse>)
      .then((body) => setStatus(describeHealth(body)))
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setStatus(`backend unreachable: ${String(err)}`)
      })
    return () => controller.abort()
  }, [])

  return (
    <main className="placeholder">
      <h1>Hezarfen</h1>
      <p>Live air traffic &amp; geospatial analysis — Marmara region.</p>
      <p className="status">{status}</p>
    </main>
  )
}
