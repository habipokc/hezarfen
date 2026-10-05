# Hezarfen

Real-time air traffic and geospatial analysis platform for the Marmara region: a live aircraft map with geofence alerts, track playback, terrain (DEM/hillshade, AGL) and a server-rendered operations panel.

> Status: **Phase 3 — REST API.** See [PROGRESS.md](PROGRESS.md). The full README (screenshots, live mode setup, data attributions) arrives in Phase 8.

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

## Data sources

The Go ingest service has four modes, chosen with `SOURCE_MODE` in `.env`:

| Mode | What it does |
|---|---|
| `auto` (default) | `live` if OpenSky credentials are set, else `replay` if `data/raw/` has recordings, else `synthetic` |
| `synthetic` | No network: 60 simulated aircraft flying great-circle routes between the region's airports (most via LTFM/LTFJ, so geofence alerts fire) plus overflights |
| `replay` | Plays recorded OpenSky responses (`REPLAY_DIR`, default `data/raw/`) re-timed to now, `REPLAY_SPEED` times faster |
| `live` | Polls OpenSky every 10 s (30 s when credits drop below 20%) and archives every raw response to `data/raw/YYYY-MM-DD/HHMMSS.json.gz` |

Out of the box the stack runs `synthetic`. To watch the data flow:

```bash
docker compose exec redis redis-cli SUBSCRIBE positions.batch     # one message per cycle
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://ingest:8080/metrics').read().decode())"
```

Replay the bundled real recording (25 snapshots of the Marmara sky, recorded anonymously) in the dev stack: set `SOURCE_MODE=replay` and `REPLAY_DIR=/src/testdata/opensky` in `.env`, then `make up`. `make record` records a fresh one (anonymous, 25 credits).

### Live mode (OpenSky account)

1. Create a free account at [opensky-network.org](https://opensky-network.org/), then open **Account → API Client** and create a client. You get a client id and a client secret (OAuth2 client credentials; OpenSky no longer accepts username/password for the API).
2. Put them in `.env` (never commit this file):
   ```bash
   OPENSKY_CLIENT_ID=your-client-id
   OPENSKY_CLIENT_SECRET=your-client-secret
   ```
3. `make up`. With `SOURCE_MODE=auto` ingest switches to `live`; `make logs s=ingest` shows `"mode":"live"` and `/metrics` shows `credits_remaining`.

Budget: a registered client has 4,000 credits per day and this region costs 1 credit per request, so 10 s polling lasts about 11 hours before adaptive polling slows down. For all-day running set `POLL_INTERVAL_SECONDS=20` or more. Live mode without credentials also works (anonymous, 400 credits per day). Raw recordings accumulate in `data/raw/` and become replay material.

Host ports (override in `.env`): `8800` (nginx, the only public entry point), `127.0.0.1:55432` (PostGIS) and `127.0.0.1:56379` (Redis) for debugging.

## REST API

Swagger UI: <http://localhost:8800/api/docs/> (OpenAPI schema at `/api/schema/`). Contract: [docs/ICD.md §7](docs/ICD.md).

```bash
curl 'localhost:8800/api/aircraft/live?bbox=28.5,40.7,29.5,41.4'   # GeoJSON, last 60 s
curl  localhost:8800/api/aircraft/<icao24>/                         # + province, nearest airport
curl  localhost:8800/api/aircraft/<icao24>/track                    # LineString, last 30 min
curl 'localhost:8800/api/playback?bucket=30'                        # last 15 min in frames
curl  localhost:8800/api/stats
curl -X POST localhost:8800/api/geofences/ -H 'Content-Type: application/json' -d '{"type":"Feature",
  "geometry":{"type":"Polygon","coordinates":[[[28.9,41.0],[29.0,41.0],[29.0,41.1],[28.9,41.1],[28.9,41.0]]]},
  "properties":{"name":"Bosphorus box"}}'
```

The API has no authentication: it is meant for a local, single-user deployment.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — components, data flow, environments
- [docs/ICD.md](docs/ICD.md) — interface contract (Redis messages, WebSocket, REST, units)
- [docs/DECISIONS.md](docs/DECISIONS.md) — decision log (Turkish)

## Data attribution

- Airports: [OurAirports](https://ourairports.com/data/) (public domain)
- Province boundaries: [Natural Earth](https://www.naturalearthdata.com/) admin-1 (public domain)
