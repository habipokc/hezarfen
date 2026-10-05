# Hezarfen — 5-minute demo

A walkthrough for showing the project to someone: what to click, what to say, and what is happening underneath. Timings are a guide; the whole script fits in five minutes.

## Before the demo (once, ~5 minutes)

```bash
make up && make seed && make dem   # stack, reference data and geofences, terrain
make smoke                         # every check "ok"
```

- Let the stack run for **at least 20 minutes** before the demo so there is history to play back (one hour is better).
- Open two tabs: <http://localhost:8800/> (map) and <http://localhost:8800/ops/>, plus [docs/ARCHITECTURE.md](ARCHITECTURE.md) on GitHub or in the editor.
- Synthetic mode needs no network. For real traffic, put OpenSky API client credentials in `.env` and `make up` again ([README](../README.md#live-mode-opensky-account)).

## 1. Live map (0:00–0:45)

**Do:** show the whole region, then zoom into Istanbul.

**Say:** "Every icon is an aircraft over the Marmara region, rotated to its heading and coloured by altitude. A Go service polls the positions every few seconds, cleans them and writes them to PostGIS and Redis in one cycle. A Django relay turns each cycle into a delta and pushes it over a WebSocket. When I zoom, the page re-subscribes with the new bounding box, so the server only sends what is on screen."

**Point at:** the "Live · N aircraft" badge; the 2-minute tails behind each aircraft.

## 2. Select an aircraft and its track (0:45–1:30)

**Do:** click an aircraft near LTFM or LTFJ.

**Say:** "The details mix two sources: altitude, speed and heading come live from the socket; the province and the nearest airport come from a REST call that runs a PostGIS query, a point-in-polygon for the province and a KNN search re-ranked by real distance on the spheroid for the airport. The line is its last 30 minutes from the positions table, and it keeps growing with live updates."

## 3. Draw a geofence and get an alert (1:30–2:30)

**Do:** "Draw a zone" → click four corners over the Bosphorus → click the first corner → name it → Save. Wait for a toast.

**Say:** "The polygon is validated twice: in the browser for instant feedback, and on the server with shapely, where it is repaired if it self-intersects and must fall inside the region. After the commit the backend publishes `geofences.changed`; the relay reloads its zones without a restart. For every batch it asks PostGIS which aircraft are inside which zones, with a GiST index, and a small state machine turns 'inside now vs inside before' into enter and exit events. The toast arrives within about a second of the position."

**Point at:** the zone blinking; the event list. Delete the zone afterwards.

## 4. Terrain and height above ground (2:30–3:15)

**Do:** fly to Bursa / Uludağ; toggle "Hillshade" and move the opacity slider; select an aircraft over the mountains.

**Say:** "`make dem` downloads 18 Copernicus elevation tiles, mosaics them with GDAL, writes a Cloud Optimized GeoTIFF for sampling and renders hillshade tiles for the map. The details show the ground elevation under the aircraft, sampled bilinearly from the COG, and its height above ground. Below 300 metres away from airports you get a 'Low flight' badge. It is approximate, about 40 metres either way: the DEM includes buildings and trees, and its heights use the geoid while GPS altitude uses the ellipsoid."

## 5. History playback (3:15–3:50)

**Do:** History → last hour → 60× → play; drag the slider.

**Say:** "This replays the positions table. The server buckets the window into frames with one SQL query, the client interpolates between frames, so motion stays smooth even at 60 times speed. The live socket is paused meanwhile; 'Live' reconnects and gets a fresh snapshot."

## 6. Ops panel (3:50–4:30)

**Do:** switch to the `/ops/` tab. Deactivate "LTFJ 15 km" and watch the event table for a few refreshes: no new LTFJ events, LTFM ones keep coming. Activate it again. Click "Run retention now". (The map tab shows the zone change only after a reload, see D-071.)

**Say:** "This page has no JavaScript framework at all: Django renders HTML and HTMX swaps fragments. The ingest card and the event table poll every 5 seconds; the buttons post and get back just the changed row. The ingest numbers come from the Go service's metrics endpoint: mode, last cycle, OpenSky credits left, records rejected by each cleaning rule. Retention runs hourly in its own small service, deleting in batches so the insert path is never blocked."

## 7. Architecture and contract (4:30–5:00)

**Do:** open [ARCHITECTURE.md](ARCHITECTURE.md) (component diagram) and [ICD.md](ICD.md) §1.

**Say:** "Eight containers in one compose project. PostGIS is the source of truth; Redis is only a notification bus, so a restarted relay rebuilds its state from the database. Every interface, from table columns to WebSocket messages, is written down in the ICD before the code, with units and a versioning rule. CI runs the Go, Python and TypeScript suites, Go against a freshly migrated PostGIS, then builds every image, starts the stack and smoke-tests it."

## If something goes wrong

| Symptom | Check |
|---|---|
| No aircraft | `/ops/` ingest card; `make logs s=ingest` |
| No geofence alerts | `make logs s=relay`; are the zones active in `/ops/`? |
| History empty | the stack was not running during the chosen window; pick a shorter or more recent one |
| No hillshade, "run make dem" in the layer panel | `make dem` (offline: `make dem DEM_SOURCE=synthetic`) |
| Old hillshade after `make dem` | hard refresh (tiles are cached for 7 days) |
