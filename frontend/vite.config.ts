/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server sits behind nginx: the browser loads the page from
// localhost:8800, so the HMR websocket must also connect to 8800, not 5173.
const hmrClientPort = Number(process.env.VITE_HMR_CLIENT_PORT ?? 8800)

export default defineConfig({
  plugins: [react()],
  // the maplibre worker (src/map/worker.ts) is spawned with { type: 'module' }
  worker: { format: 'es' },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // requests arrive with Host: localhost:8800 via nginx
    allowedHosts: true,
    hmr: { clientPort: hmrClientPort },
  },
  build: {
    rolldownOptions: {
      output: {
        // maplibre (~1 MB) changes far less often than app code: its own long-cached chunk
        codeSplitting: { groups: [{ name: 'maplibre', test: /node_modules[\\/]maplibre-gl/ }] },
      },
    },
    // maplibre alone is ~1 MB minified (~280 kB gzip); that is the floor, not a regression
    chunkSizeWarningLimit: 1100,
  },
  test: {
    environment: 'node',
  },
})
