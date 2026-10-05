/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server sits behind nginx: the browser loads the page from
// localhost:8800, so the HMR websocket must also connect to 8800, not 5173.
const hmrClientPort = Number(process.env.VITE_HMR_CLIENT_PORT ?? 8800)

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // requests arrive with Host: localhost:8800 via nginx
    allowedHosts: true,
    hmr: { clientPort: hmrClientPort },
  },
  test: {
    environment: 'node',
  },
})
