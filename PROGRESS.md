# İlerleme (PROGRESS)

> Yeni oturumda önce bu dosyayı oku, "Sıradaki adım"dan devam et.

## Durum özeti

| Faz | Durum |
|---|---|
| 0 — İskelet, altyapı, ICD | ✅ Tamamlandı (tag `phase-0`) — onay bekleniyor |
| 1 — Django, GeoDjango, referans veri | ⏳ |
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

## Sıradaki adım

Proje sahibinin Faz 0 onayı. Ardından Faz 1: `docs/superpowers/plans/` altına Faz 1 planı → modeller/migration'lar (`geofencing`, `terrain` app'leri eklenecek) → admin harita widget'ı + prod static çözümü → `scripts/load_reference_data.sh` (ogr2ogr) → `seed_geofences` → pytest spatial testler → `learn/02`, `03`, `04`.
