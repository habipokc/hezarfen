# İlerleme (PROGRESS)

> Yeni oturumda önce bu dosyayı oku, "Sıradaki adım"dan devam et.

## Durum özeti

| Faz | Durum |
|---|---|
| 0 — İskelet, altyapı, ICD | ✅ Tamamlandı (tag `phase-0`) |
| 1 — Django, GeoDjango, referans veri | ✅ Tamamlandı (tag `phase-1`) — onay bekleniyor |
| 2 — Go ingest | ⏳ |
| 3 — REST API | ⏳ |
| 4 — Gerçek zamanlı katman | ⏳ |
| 5 — Frontend çekirdeği | ⏳ |
| 6 — İz, playback, geofence çizimi | ⏳ |
| 7 — Raster / DEM | ⏳ |
| 8 — HTMX ops, CI, teslim | ⏳ |

## Faz 0 — İskelet, altyapı ve sözleşme (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-0.md`.

**Tamamlananlar**

- 7 servisli compose yığını (`db`, `redis`, `backend`, `relay`, `ingest`, `frontend`, `nginx`); healthcheck'ler ve `depends_on: service_healthy` zinciri; `name: hezarfen`, `container_name` yok.
- Dev override: Django `uvicorn --reload` (watchfiles), relay `watchfiles`, Go `air`, Vite HMR nginx üzerinden (`clientPort` 8800).
- nginx: `/api`, `/admin`, `/ops`, `/static` → backend; `/ws/` upgrade; `/tiles/` statik; `/` → frontend (upgrade dahil).
- Backend: Django 6.1 + GeoDjango, `ops` (`/api/health`: PostGIS + Redis), `tracking` (placeholder `relay`, heartbeat dosyası).
- Ingest: Go 1.27 placeholder (`/healthz`, `/metrics`, `-healthcheck`, slog JSON, graceful shutdown); prod imajı distroless (17 MB).
- Frontend: Vite 8 + React 19 + TS 6 (strict) placeholder; `/api/health`'i gösteriyor.
- Makefile: `up`, `up-prod`, `down`, `clean`, `logs`, `ps`, `test`, `lint`, `seed`/`dem`/`record` (placeholder), `psql`, `shell-backend`.
- Dokümanlar: `docs/ICD.md` (8 arayüz, birimler, sürümleme), `docs/ARCHITECTURE.md` (Mermaid), `docs/DECISIONS.md` (D-001…D-014), `CLAUDE.md`, `README.md`.
- CI: `.github/workflows/ci.yml` (go vet/fmt/test, ruff + pytest + PostGIS service, tsc/eslint/vitest, prod imaj build). Yerelde aynı komutlar container'larda çalıştırıldı ve geçti; GitHub'da henüz koşmadı (remote yok).
- Learn: `learn/00-basla-buradan.md` (yaşayan giriş dosyası, her faz kapanışında güncellenir), `learn/00-cografi-temeller.md`, `learn/01-altyapi.md` (ayrı `learn/` reposunda commit'li).

**Doğrulanan kabul kriterleri**

- `make up` → 7 servis healthy.
- `curl localhost:8800/api/health` → `{"status":"ok","checks":{"postgis":"3.6.4","redis":"ok"}}`; `localhost:8800/` → React sayfası; `/admin/login/` 200.
- Hot-reload: Django, relay, Go ve Vite dosyaları değişince container restart olmadan yeni kod çalıştı (StartedAt değişmedi). Vite HMR WebSocket'i nginx üzerinden 101 döndü.
- `make up-prod` (override'sız, prod target'lar) → 7 servis healthy.
- `make test` (go test, vitest, pytest) ve `make lint` (go vet + gofmt, tsc + eslint, ruff check + format) temiz.

**Sapmalar**

- PLAN'daki `localhost/` yerine `localhost:8800/` (spec). Django 5.x yerine 6.1 (güncel stabil, D-003). TypeScript 7 yerine 6.0 (D-004). ASGI sunucusu uvicorn (D-005).

**Bilinen sorunlar / notlar**

- Prod modunda (`DEBUG=0`) admin CSS'i servis edilmiyor; Faz 1'de çözülecek (D-012).
- `frontend/node_modules` host'ta root'a ait boş bir dizin olarak duruyor (anonim volume'un bağlama noktası); zararsız.
- Docker Desktop açılışta WSL soketini oluşturmazsa yeniden başlatılmalı (D-014).
- `learn/01-altyapi.md` ~4.300 kelime (hedef 1.500–3.500); tablo ve başlıklar dahil sayım, içerik bilerek korundu.
- Ingest prod imajı `nonroot` kullanıcıyla çalışıyor; Faz 2'de `data/raw`'a yazarken izinler ele alınmalı.

## Faz 1 — Django, GeoDjango ve referans veri (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-1.md`.

**Tamamlananlar**

- App'ler: `tracking` (aircraft, aircraft_latest, positions), `reference` (airports, provinces), `geofencing` (geofences, geofence_events), `terrain` (boş, Faz 7), `ops`. Tablo adları `Meta.db_table` ile sabit.
- Index'ler: tüm geometri kolonlarında GiST; `positions.ts` üzerinde BRIN; `(icao24, ts)` unique constraint (ingest `ON CONFLICT DO NOTHING`). `on_ground` ve `source` için `db_default`.
- ICD 1.1: IF-2 tablolarının kolon listesi eklendi (Go servisi için).
- Admin: geofence, havalimanı ve il ekranlarında OpenLayers harita widget'ı (Marmara'ya ortalı); ingest tabloları ve geofence olayları salt okunur.
- Static: WhiteNoise. Dev'de finders, prod'da build sırasında `collectstatic`; hash'li, gzip'li, `immutable` cache. D-012 kapandı.
- `scripts/load_reference_data.sh`: OurAirports CSV ve Natural Earth admin-1 (`/vsizip/`) → ogr2ogr (`-where`, `-spat`, `-select`, `-a_srs`/`-t_srs`, `-nlt PROMOTE_TO_MULTI`) → staging tabloları → `ogrinfo` kontrolü → `manage.py import_reference` (tek transaction'da upsert ve silme). Önbellek `data/reference/`. Yedek yol: `scripts/fixtures/*.geojson` (`REFERENCE_OFFLINE=1` ile de tetiklenir).
- Komutlar: `import_reference`, `seed_geofences` (geography `ST_Buffer` 15 km, 64 köşe, idempotent), `prune_positions` (`--days`, varsayılan `POSITIONS_RETENTION_DAYS`).
- Makefile: `seed` (host UID ile; migrate → load → seed_geofences), `prune`, `superuser`; `lint-backend` içine `makemigrations --check`. Aynı kontrol CI'da da var.
- `make up-prod` artık `DJANGO_DEBUG=0` ile çalışıyor (D-020).
- Testler: 16 pytest testi (gerçek PostGIS). Kapsam: unique ve idempotent insert, index türleri, buffer içi ve dışı, "her yönde 15 km", derece buffer'ının elips üretmesi, il sorgusu, seed idempotency, import upsert ve aynalama, prune.
- Dokümanlar: DECISIONS D-015…D-024, ARCHITECTURE (referans veri akışı), README (seed, superuser, veri kaynakları).
- Learn: `02-django-temelleri.md`, `03-postgis-ve-geodjango.md`, `04-gdal-ogr-vektor.md`; `00-basla-buradan.md` güncellendi.

**Doğrulanan kabul kriterleri**

- `make seed` → 21 havalimanı, 81 il (geçersiz geometri yok), 2 geofence. Önbellekle 7 sn. `make seed REFERENCE_OFFLINE=1` → 8 havalimanı ve 4 il; bölge dışı ve tip dışı kayıtlar filtrelendi.
- Spatial kontroller: (28.98, 41.01) → İstanbul; buffer alanı 706 km² (π·15² ≈ 707); `EXPLAIN` GiST kullanıyor.
- Admin: giriş, liste ve düzenleme sayfaları 200. Admin formundan geofence ekleme denendi; EPSG:3857 gönderilen geometri 4326'da doğru koordinatlarla kaydedildi.
- Static: dev'de `/static/admin/css/base.css` 200; prod'da (`DEBUG=0`) hash'li dosya 200, gzip ve `immutable`.
- `make up` ve `make up-prod` → 7 servis healthy. `make test` ve `make lint` temiz.

**Sapmalar**

- Referans tablolar PLAN'daki "tracking veya ayrı modül" seçeneğinden ayrı `reference` app'inde (D-015).
- `positions` için ayrı `(icao24, ts)` B-tree yok, unique constraint'in index'i kullanılıyor; `positions.icao24` FK değil (D-017).
- `prune_positions` §5'ten Faz 1'e alındı; zamanlama henüz yok (D-024).

**Bilinen sorunlar / notlar**

- Admin harita widget'ı OpenLayers JS'ini ve OSM karolarını internetten yüklüyor; çevrimdışı tarayıcıda harita görünmez, form yine çalışır.
- GeoDjango'da `distance_lte` WHERE içinde `ST_DistanceSphere` üretiyor ve index kullanmıyor. Faz 3'teki "en yakın havalimanı" sorgusu KNN (`<->`) ya da geography `ST_DWithin` ile yazılmalı.
- `make seed` dev imajını kullanıyor (prod stack çalışırken de çalışır; tek seferlik container).
- Faz 0'dan kalan: ingest prod imajı `nonroot` (Faz 2'de `data/raw` izinleri).

## Sıradaki adım

Proje sahibinin Faz 1 onayı. Ardından Faz 2 (Go ingest): Faz 2 planı → `internal/{config,opensky,source,store,publish,geo}` → synthetic üretici (haversine ve great-circle için TDD) → replay → live (OAuth2, adaptive polling, raw zone kaydı) → PostGIS'e batch yazma (ICD §3 kolonları) + Redis `positions.batch/v1` → `scripts/record_fixture.sh` → `learn/05`, `06`.
