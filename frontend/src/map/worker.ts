import { setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

// maplibre-gl 6 derives its worker URL at runtime from its own module URL. Vite cannot see
// that, so the production build never emitted the worker (and dev pre-bundling moved the
// main file away from it). Let Vite bundle the worker with its imports and hand over the URL.
setWorkerUrl(workerUrl)
