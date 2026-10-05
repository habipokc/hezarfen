# Hezarfen

Real-time air traffic and geospatial analysis platform for the Marmara region: a live aircraft map with geofence alerts, track playback, terrain (DEM/hillshade, AGL) and a server-rendered operations panel.

> Status: **Phase 1 — Django, GeoDjango and reference data.** See [PROGRESS.md](PROGRESS.md). The full README (screenshots, live mode setup, data attributions) arrives in Phase 8.

## Stack

Go ingest service · Django (GeoDjango, DRF, Channels) · PostgreSQL/PostGIS · Redis · React + TypeScript + MapLibre GL JS · nginx · Docker Compose.

## Quick start

Requirements: Docker (with Compose v2), `make`, `git`. No Go, Node or GDAL needed on the host.

```bash
make up          # builds images, starts the dev stack with hot reload, waits until healthy
curl localhost:8800/api/health
open http://localhost:8800/
make seed        # airports (OurAirports) + Turkish provinces (Natural Earth) via ogr2ogr, LTFM/LTFJ geofences
make superuser   # then edit geofences on a map at http://localhost:8800/admin/
make test        # Go, frontend and backend test suites (inside containers)
make down
```

`make seed` caches downloads in `data/reference/`; without network (or with `make seed REFERENCE_OFFLINE=1`) it loads the small hand-made fixtures in `scripts/fixtures/` instead.

Host ports (override in `.env`): `8800` (nginx, the only public entry point), `127.0.0.1:55432` (PostGIS) and `127.0.0.1:56379` (Redis) for debugging.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, data flow, environments
- [docs/ICD.md](docs/ICD.md) — interface contract (Redis messages, WebSocket, REST, units)
- [docs/DECISIONS.md](docs/DECISIONS.md) — decision log (Turkish)

## Data attribution

- Airports: [OurAirports](https://ourairports.com/data/) (public domain)
- Province boundaries: [Natural Earth](https://www.naturalearthdata.com/) admin-1 (public domain)
