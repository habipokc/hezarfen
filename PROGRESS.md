# İlerleme (PROGRESS)

> Yeni oturumda önce bu dosyayı oku, "Sıradaki adım"dan devam et.

## Durum özeti

| Faz | Durum |
|---|---|
| 0 — İskelet, altyapı, ICD | ✅ Tamamlandı (tag `phase-0`) |
| 1 — Django, GeoDjango, referans veri | ✅ Tamamlandı (tag `phase-1`) |
| 2 — Go ingest | ✅ Tamamlandı (tag `phase-2`) |
| 3 — REST API | ✅ Tamamlandı (tag `phase-3`) |
| 4 — Gerçek zamanlı katman | ✅ Tamamlandı (tag `phase-4`) |
| 5 — Frontend çekirdeği | ✅ Tamamlandı (tag `phase-5`) |
| 6 — İz, playback, geofence çizimi | ✅ Tamamlandı (tag `phase-6`) |
| 7 — Raster / DEM | ✅ Tamamlandı (tag `phase-7`) — onay bekleniyor |
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
- Faz 0'dan kalan: ingest prod imajı `nonroot` (Faz 2'de `data/raw` izinleri). → Faz 2'de çözüldü (D-025).

## Faz 2 — Go ingest servisi (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-2.md`.

**Tamamlananlar**

- Paketler (`ingest/internal/`):
  - `config`: env okuma ve doğrulama; bütün hatalar tek seferde raporlanıyor.
  - `geo`: haversine, bearing, great-circle interpolasyonu, destination, bbox.
  - `opensky`: indeksli dizi parser'ı (null → nil pointer), OAuth2 `TokenSource` (mutex, süre dolmadan 60 sn önce yenileme, 401'de bir kez yenileme), `GetStates` (`X-Rate-Limit-Remaining`, 429 → `RateLimitError`, 5xx/ağ → 1-2-4 sn backoff).
  - `source`: `Live` (adaptive 10 → 30 sn, 429'da `Retry-After` kadar bekleme, raw zone `data/raw/YYYY-MM-DD/HHMMSS.json.gz` atomik yazım), `Replay` (sıralı, `REPLAY_SPEED`, oturum boşluklarını atlama, duvar saatine `Retime`, sonsuz döngü), `Synthetic` (60 uçak, mesafe tabanlı tırmanış/seyir/alçalma, %75 LTFM/LTFJ, %20 overflight), `ResolveMode` (auto).
  - `clean`: altı kural (`invalid_icao24`, `no_position`, `out_of_bbox`, `stale` > 15 sn, `duplicate`, `impossible_jump` > 400 m/s; üç ardışık redden sonra yeniden çapalama).
  - `store`: pgx, tek transaction, `unnest` dizileriyle tek pipelined batch; `aircraft` upsert, `aircraft_latest` yalnızca daha yeni `ts` ile, `positions` `ON CONFLICT DO NOTHING`.
  - `publish`: `positions.batch/v1`.
- `cmd/ingest`: mod çözümü, bağımlılık bekleme, ETL döngüsü (hata döngüyü durdurmuyor), `/healthz`, `/metrics` (ICD 1.2 alanları), graceful shutdown.
- Ingest container'ı host uid/gid ile çalışıyor (prod ve dev); dev imajları `:dev` etiketli (D-025, D-026).
- `scripts/record_fixture.sh` + `make record`: anonim 25 snapshot, `ingest/testdata/opensky/2026-10-05/` (yaklaşık 80 uçak, ~110 KB).
- `make test-ingest`, store ve publish entegrasyon testlerini stack'in db/redis'ine karşı çalıştırıyor (geçici şema, test kanalı).
- Dokümanlar: ICD 1.2, DECISIONS D-025…D-036, README (veri kaynakları, live mod kurulumu, kredi bütçesi), ARCHITECTURE (ingest pipeline), `.env.example` (yeni değişkenler).
- Learn: `05-go-temelleri.md`, `06-adsb-ve-etl.md`; `00-basla-buradan.md` güncellendi.

**Doğrulanan kabul kriterleri**

- `SOURCE_MODE=synthetic` (auto → synthetic): `aircraft_latest` iki saniyede bir ilerliyor (60 uçak, DB'deki 14 havalimanı). `redis-cli SUBSCRIBE positions.batch` ICD biçiminde mesaj gösteriyor. Geofence'lerin içinde uçak var (LTFM 9, LTFJ 8, anlık).
- Replay: gerçek fixture 5× hızla oynatıldı. 85 farklı uçak duvar saatine kaydırılmış `ts` ile yazıldı ve yayınlandı; kayıttaki konumların yaklaşık %12'si `stale` olarak atıldı. Hata yok.
- Live (anonim, prod distroless imajı): 3 poll yapıldı, raw dosyalar host kullanıcısına ait yazıldı, graceful shutdown çalıştı. Deneme kayıtları sonra silindi.
- `make up` ve `make up-prod` → 7 servis healthy. `make up-prod` sonrası `make test-ingest` doğru (dev) imajda çalışıyor.
- `go test ./...` (55 test, entegrasyon dahil), `go vet`, `gofmt` temiz; `make test` ve `make lint` temiz.

**Sapmalar**

- PLAN'daki paket listesine `internal/clean` eklendi (D-027).
- Null alanlar `sql.Null*` yerine pointer (D-027).
- `positions.batch/v1` içine uçak başına `ts` eklendi (geriye uyumlu, ICD 1.2, D-035).
- Explicit `SOURCE_MODE=live`, credential olmadan anonim erişimle çalışıyor (D-032).

**Bilinen sorunlar / notlar**

- Relay henüz Redis'e abone değil (Faz 4); `last_subscribers` normalde 0.
- Go job'ı CI'da store/publish entegrasyon testlerini atlıyor (migrate edilmiş DB yok, D-034).
- 10 sn'lik live polling 4.000 krediyi yaklaşık 11 saatte bitirir; sürekli yayın için `POLL_INTERVAL_SECONDS=20` önerisi README'de.
- Dev'de her ingest yeniden başlatmasında sentetik filo baştan başlıyor (sabit seed); `positions`'ta yeniden başlatma anlarında izler "atlıyor". Synthetic için zararsız.
- `aircraft` tablosunda önceki rastgele seed denemelerinden kalan 120 sentetik uçak var; 60 sn penceresinin dışında kaldıkları için Faz 4'te görünmeyecekler.

## Faz 3 — Django REST API (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-3.md`.

**Tamamlananlar**

- Bağımlılıklar: djangorestframework 3.18.1, djangorestframework-gis 1.3.0, drf-spectacular 0.30.0, shapely 2.1.2 (D-037).
- `hezarfen/api/`:
  - ICD §7.1 hata biçimi (exception handler, `ApiError`, JSON 404 catch-all, 503 `unavailable`) (D-038).
  - Saf parametre ayrıştırıcıları.
  - `UnixTimeField`.
  - URL tablosu.
- Endpoint'ler (ICD 1.3 §7.2):
  - `/api/aircraft/live`: `&&` ile bbox, son 60 sn, tek sorgu.
  - `/api/aircraft/{icao24}/`: il ve en yakın havalimanı (KNN aday + metrik yeniden sıralama, D-040).
  - `/api/aircraft/{icao24}/track`: `ST_MakeLine(geom ORDER BY ts)`, 24 saat sınırı (D-041).
  - `/api/playback`: `DISTINCT ON` ile bucket başına son konum, ≤ 2 saat (D-042).
  - `/api/geofences/`: CRUD, PUT yok; shapely doğrulaması; `geofences.changed/v1` commit sonrası yayınlanıyor (D-043).
  - `/api/geofence-events`: cursor sayfalama.
  - `/api/provinces/`: `ST_Simplify` 0,01°, 5 ondalık (D-044).
  - `/api/airports/`.
  - `/api/stats`: ingest durumu `ok|stale|starting|unreachable` (D-045).
  - `/api/schema/`, `/api/docs/` (Swagger).
- Kimlik doğrulama yok (D-039). REST `Aircraft` özellikleri `lon`/`lat` içeriyor (D-047).
- nginx: JSON yanıtlar için gzip.
- Faz 2 hatası düzeltildi: sıçrama filtresi tam saniye kesmesi yüzünden synthetic'te 230 m/s uçakları reddediyordu; hız artık `dt + 1` ile hesaplanıyor (D-046, Go testi eklendi).
- Testler: backend 16 → 80 (parametreler, poligon doğrulama, her endpoint, OpenAPI `--validate --fail-on-warn`). Go testleri 56.
- Dokümanlar: ICD 1.3, DECISIONS D-037…D-047, README (REST API bölümü), ARCHITECTURE (REST diyagramı), `.env.example`.
- Learn: `07-drf-ve-rest-tasarimi.md`; `00-basla-buradan.md` güncellendi.

**Doğrulanan kabul kriterleri**

- Synthetic veri akarken bütün endpoint'ler anlamlı GeoJSON/JSON dönüyor; nginx üzerinden curl ile doğrulandı.
- `/api/aircraft/live` 60 uçakla 52–65 ms (dev ve prod, nginx dahil) → < 100 ms.
- Swagger UI ve şema 200; şema uyarısız doğrulanıyor.
- Yanıt boyutları:
  - playback 15 dk: 1,19 MB → 208 KB (gzip)
  - iller: 206 KB → 98 KB (basitleştirme)
- `make up-prod` 7 servis healthy, endpoint'ler çalışıyor. `make up` geri açıldı.
- `make test` ve `make lint` temiz. Düzeltmeden sonra ingest'te `impossible_jump` reddi sıfır.

**Sapmalar**

- Plan'daki "sayfalama ya da sıkıştırma" için playback'te sıkıştırma seçildi (nginx gzip), sayfalama yok (D-042).
- ICD'de `start`/`end` zorunlu görünüyordu; varsayılanlar eklendi (`end = now`, `start = end − 15 dk`).
- `?simplify=` parametresi plan dışı ek (karşılaştırma ve learn için).

**Bilinen sorunlar / notlar**

- `geofence_events` hâlâ boş; olayları relay Faz 4'te yazacak.
- Swagger UI, JS ve CSS'ini jsDelivr CDN'den yüklüyor; çevrimdışı tarayıcıda boş görünür (şema `/api/schema/` yine çalışır).
- İl sınırları basitleştirildiğinde komşu iller arasında küçük boşluklar oluşabilir (topoloji korunmuyor); bölge zoom'unda görünmez.
- API'de kimlik doğrulama yok; yalnızca yerel kullanım içindir.

## Faz 4 — Gerçek zamanlı katman (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-4.md`.

**Tamamlananlar**

- Bağımlılıklar: channels 4.3.2, channels-redis 4.3.0; dev: pytest-asyncio 1.4.0, daphne 4.2.3 (yalnızca `channels.testing` için) (D-048).
- Yeni `realtime` uygulaması:
  - `state.py`: `LiveState` (coalescing, 60 sn zaman aşımı), `merge_deltas`, `filter_delta`, subscribe bbox doğrulaması.
  - `outbox.py`: bağlantı başına backpressure; deltalar birleşiyor, olaylar düşmüyor, 1000 mesajda 1013 ile kapatma (D-049, ICD 1.4).
  - `consumers.py`: `/ws/live/`; subscribe → snapshot (DB'den), bbox'a göre delta, geofence_event, 15 sn heartbeat, hata mesajları.
  - `relay.py` + `relay` komutu: `positions.batch` ve `geofences.changed` aboneliği, saniye sınırında flush, Redis kopunca yeniden bağlanma, heartbeat dosyası (D-053).
  - `queries.py`: batch başına tek geofence sorgusu (`unnest` + `ST_Contains`, D-051), olaylardan durum kurma, olayları toplu yazma.
  - `ws_tail` komutu ve `make ws`.
- `geofencing/tracker.py`: enter/exit state machine; batch'te olmamak çıkış değil, zaman aşımında olaysız unutma, silinen bölgeyi olaysız atma (D-052).
- ASGI: `ProtocolTypeRouter` + `AllowedHostsOriginValidator` (D-050). `relay` komutu `tracking`'ten `realtime`'a taşındı.
- Testler: backend 80 → 131. Saf: state, outbox, tracker (38). DB: tek sorgu kontrolü, enter/exit bir kez, yeniden başlatma, coalescing, `geofences.changed`. Consumer: Origin reddi, subscribe öncesi yalnızca heartbeat, hatalar, snapshot, bbox filtresi, boş delta yok, olaylar filtresiz, yeni subscribe. Testlerde in-memory channel layer (D-054).
- Dokümanlar: ICD 1.4 (§5 zamanlama, §6 Origin, sıralama notu, §6.4 backpressure), DECISIONS D-048…D-054, README (Live WebSocket), ARCHITECTURE (gerçek zamanlı katman diyagramı).
- Learn: `08-websocket-ve-gercek-zamanli.md`; `00-basla-buradan.md` güncellendi.

**Doğrulanan kabul kriterleri**

- `make ws` (nginx üzerinden, `ws://nginx/ws/live/`): snapshot, ardından synthetic tick'e uygun olarak 2 sn'de bir delta (ICD: en fazla 1/sn), 15 sn'de bir heartbeat.
- Synthetic uçaklar LTFM/LTFJ 15 km bölgelerine girip çıkınca `geofence_event` geliyor; olaylar `geofence_events`'e yazılıyor ve `/api/geofence-events`'te aynı id ile görünüyor.
- Relay yeniden başlatıldığında 7 çift olaylardan geri kuruldu; tekrar eden `enter` yok.
- REST'ten geofence oluşturma/silme relay'e ulaşıyor; yeni bölgedeki girişler hemen yakalanıyor.
- `make up-prod`: 7 servis healthy, 2 uvicorn worker ile WebSocket çalışıyor. `make up` geri açıldı.
- `make test` (Go, vitest 2, pytest 131) ve `make lint` temiz.

**Sapmalar**

- Backpressure politikası ICD 1.3'ten farklı: taşınca snapshot yerine bekleyen deltalar birleştiriliyor (ICD 1.4'e işlendi, D-049).
- Delta sıklığı ingest döngüsüne bağlı: synthetic 2 sn tick'te 2 sn'de bir delta geliyor (sözleşme "en fazla 1/sn").
- Plan dışı ekler: `ws_tail` komutu / `make ws`, WebSocket'te Origin kontrolü.

**Bilinen sorunlar / notlar**

- Snapshot DB'den, deltalar relay belleğinden geldiği için snapshot'tan hemen önce kuyruğa girmiş bir delta ~1 sn eski konum taşıyabilir; istemci uçak başına en yeni `ts`'yi tutmalı (ICD §6.2, Faz 5'te frontend).
- Origin başlığı olmadan bağlanan araçlar (ör. düz `websocat`) 403 alır; `-H 'Origin: http://localhost:8800'` gerekir.
- Bölge sınırında gidip gelen uçak için histerezis yok; sık enter/exit üretebilir.
- Yere inip sinyali kesilen uçak için `exit` yazılmıyor (bilinçli, D-052); olay tablosunda kapanmamış `enter`'lar kalabilir.

## Faz 5 — Frontend çekirdeği (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-5.md`.

**Tamamlananlar**

- maplibre-gl 6.12.0 (D-055). Arayüz İngilizce.
- Harita: `useMapLibre` (instance ref'te), OpenFreeMap `dark` + zaman aşımlı yedek style (D-056), worker Vite ile paketleniyor (D-064).
- Canlı uçak katmanı:
  - `LiveStore` (`Map<icao24, Feature>`, en yeni `ts` kazanır), 1 sn throttle'lı `setData`, React'e yalnızca `version` sayacı (D-057).
  - Canvas'ta üretilen SDF ikon; `icon-rotate` + `icon-rotation-alignment: map`; irtifaya göre `interpolate` renk, yerdekiler gri.
  - `promoteId` + `feature-state` ile hover/seçim halkası (D-058); callsign etiketi zoom ≥ 8.
- `useLiveSocket`: subscribe açılışta ve her `moveend`'de (viewport + %10, D-059); full jitter backoff, snapshot'ta sıfırlama, 45 sn watchdog, `online` olayı (D-060); durum rozeti geri sayımlı.
- Referans katmanlar (iller, havalimanları, geofence'ler) ve açma/kapama paneli, irtifa lejantı.
- Detay paneli: canlı alanlar soketten, il / en yakın havalimanı / ülke REST'ten (15 sn'de bir yenileme).
- Geofence olay listesi: REST geçmişi + canlı olaylar; tıklayınca uçağa uçuş.
- Responsive: 640 px altında iki durumlu bottom sheet; mobilde seçilen uçak çekmecenin üstüne kaydırılıyor (D-061).
- `make ui-smoke`: Playwright konteyneri, WebSocket frame'lerinden kabul kontrolleri, 16 kontrol, ekran görüntüleri `data/ui-smoke/` (D-062). Bundle: maplibre ayrı chunk.
- Faz 4 hatası düzeltildi: redis-py 8'in 5 sn varsayılan `socket_timeout`'u boştaki consumer'ları düşürüyordu; channel layer'a `socket_timeout: 15` ve config testi (D-063). Sender, gönderim sırasında kopan istemci için ERROR yerine debug logu yazıyor.
- Testler: frontend vitest 2 → 38 (mesaj ayrıştırma, store, bbox, irtifa rengi, backoff, throttle, biçimlendirme, basemap yedeği, olay birleştirme, SDF). Backend 131 → 132.
- Dokümanlar: DECISIONS D-055…D-064, README (Live map), ARCHITECTURE (frontend diyagramı).
- Learn: `09-react-ve-typescript.md`, `10-maplibre-ve-web-haritacilik.md`; `00-basla-buradan.md` güncellendi.

**Doğrulanan kabul kriterleri**

- Uçaklar her güncellemede ilerliyor; yönler doğru (yerdeki uçak pistle hizalı, 253° heading'li uçak batı-güneybatıya bakıyor).
- Kaydırınca yalnızca görünen bölgenin verisi geliyor: zoom + pan sonrası yeni ve daha küçük bbox ile subscribe, snapshot 61 → 20–25 uçak, bbox dışında sıfır uçak (WebSocket frame'lerinden).
- Mobil (375×812): yatay taşma yok, çekmece kapalı başlıyor, dokununca detay açılıyor, zoom düğmeleri kapanmıyor.
- Konsol hatası yok. `make ui-smoke` dev ve prod'da (`make up-prod`, statik derleme) geçiyor; `make up` geri açıldı.
- `tsc --noEmit` ve ESLint temiz; `make test` (Go, vitest 38, pytest 132) ve `make lint` temiz.

**Sapmalar**

- Uçaklar 2 sn'de bir sıçrayarak ilerliyor (synthetic tick 2 sn, `setData` ≤ 1/sn kuralı); ara karelerde konum tahmini (dead reckoning) yok.
- Plan dışı ekler: geofence olay listesi (REST geçmişiyle), `make ui-smoke`, dev'de `window.__map`.
- maplibre worker'ı için Vite yapılandırması (D-064); plan bunu öngörmüyordu.

**Bilinen sorunlar / notlar**

- Dev'de StrictMode yüzünden her açılışta bir "WebSocket closed before the connection is established" uyarısı ve backend'de iptal edilen ilk `fetch` için asgiref "CancelledError in shielded future" logu çıkıyor; zararsız, prod'da yok.
- Geofence katmanı açılışta bir kez yükleniyor; REST'ten eklenen/silinen bölge sayfa yenilenince görünüyor (Faz 6'da çizimle birlikte canlı hale gelecek).
- Masaüstünde panel haritanın sağ 360 px'ini kapatıyor; harita merkezi buna göre kaydırılmıyor.
- Basemap ve glyph'ler internetten geliyor; çevrimdışıyken yedek style görünüyor, etiketler (demotiles da erişilemezse) çıkmayabilir.
- `make ui-smoke` ilk çalıştırmada ~2 GB'lık (açılmış hali 3,5 GB) Playwright imajını indiriyor.

## Faz 6 — İleri özellikler: iz, geçmiş oynatma, geofence çizimi (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-6.md`.

**Tamamlananlar**

- İz: seçili uçağın son 30 dk'sı `/track`'ten, canlı fix'lerle uzuyor (D-067). Tüm uçaklara istemcide üretilen 2 dk'lık kuyruk, irtifa renginde, "Trails" anahtarıyla (D-066, performans ölçümüyle).
- Geçmiş modu:
  - Live/History anahtarı; geçmişte WebSocket kapanıyor, rozet "History" (D-070).
  - Pencere 15 dk–2 saat, bitiş zamanı seçilebilir; tek `/api/playback` isteği, ~360 kare hedefli bucket (D-068).
  - rAF saati, 1×/10×/60×, kaydırıcı; kareler arası lineer konum, kısa yaydan heading, 3 bucket'tan uzun boşluklar köprülenmiyor (D-069). Haritaya ≤ 20 çizim/sn.
  - Detay paneli ve seçili uçağın yolu oynatma zamanını izliyor.
- Geofence çizimi:
  - terra-draw 1.36.0 + MapLibre adapter 1.4.1; kendini kesen halka çizimde reddediliyor; kapanış tıklaması uçak seçmiyor (D-065).
  - İsim formu, istemci ön kontrolü (köşe, alan, bölge; D-071), `POST`; listeden aktif/pasif (`PATCH`) ve silme (`DELETE`, onaylı).
  - Geofence kaynağı REST verisiyle besleniyor (`promoteId: id`); pasif bölgeler soluk.
- Olay bildirimleri: toast (en fazla 4, 6 sn, tıklayınca uçağa uçuş), olay listesi, bölgenin `feature-state` ile yanıp sönmesi (D-072).
- nginx JS/CSS'i de gzip'liyor (D-073).
- Testler: vitest 38 → 79 (playback örnekleme ve saat, kuyruk, iz uzatma, poligon alanı ve kontrolü, toast, API hata zarfı, datetime-local). pytest 132 → 134 (playback pencere sınırları, varsayılan pencere).
- `make ui-smoke` 16 → 29 kontrol: iz çizgisi, kuyruklar, geçmiş modu 60× hız ölçümü, soketin duraklaması, canlıya dönüş, fareyle bölge çizimi, kayıt, gerçek sınır geçişi toast'ı, olay gecikmesi, silme.
- Dokümanlar: DECISIONS D-065…D-073, README (Live map), ARCHITECTURE (Faz 6 diyagramı).
- Learn: `11-zaman-serisi-cografi-veri.md`; `00-basla-buradan.md` güncellendi.

**Doğrulanan kabul kriterleri**

- Uçak seçince izi görünüyor (smoke: 12–24 noktalık çizgi).
- Son 1 saat 60× oynatılabiliyor (smoke: ölçülen 55–58×; 87 uçak, 21.650 konum).
- Kullanıcının çizdiği bölgeye giren synthetic uçak için toast çıkıyor. Konum zaman damgasından tarayıcıya en kötü 0,9 sn (17 olay). Bölge içindeki uçaklar için kayıt anında `enter` geliyor (D-052).
- Prod derlemesinde (`make up-prod`) çizim ve oynatma hatasız; konsol hatası yok. `make test`, `make lint` temiz; `make up` geri açıldı.

**Sapmalar**

- Plan dışı ekler: geçmiş penceresinin bitiş zamanını seçme, geçmişte de kuyruk ve seçili uçağın yolu, istemci tarafı poligon ön kontrolü, nginx gzip düzeltmesi.
- Geçmiş modunda haritaya ≤ 20 çizim/sn (canlıdaki ≤ 1/sn kuralı oynatmaya uygulanmadı, D-068).

**Bilinen sorunlar / notlar**

- `make ui-smoke`'un bölge adımı gerçek bir sınır geçişini bekliyor; trafiğe göre 20–100 sn sürüyor (zaman aşımı 180 sn).
- Smoke'un Faz 6 adımları `window.__map`'e dayandığı için yalnızca dev'de koşuyor; prod ayrıca elle (betikle) doğrulandı.
- Başka bir sekmede ya da Swagger'dan yapılan bölge değişikliği bu sekmede sayfa yenilenene ya da kendi işlemimize kadar görünmüyor (D-071).
- terra-draw ilk yüklemede geliyor (~270 kB sıkıştırılmamış, ~50 kB gzip); tembel yükleme Faz 8'e bırakıldı.
- Geçmiş penceresinde veri yoksa (stack kapalıyken geçen süre) uçaklar görünmüyor; panel "No positions recorded" diyor.
- Geçmiş modunda detay panelinde il ve en yakın havalimanı gizli: REST bunları uçağın şimdiki konumu için veriyor, oynatılan an için değil.
- Prod'dan dev'e geçişte bir kez `make up --wait` hata verdi, tekrarında tüm servisler sağlıklı açıldı.

## Faz 7 — Raster: DEM, hillshade, arazi örnekleme (2026-10-05)

Plan: `docs/superpowers/plans/2026-10-05-phase-7.md`.

**Tamamlananlar**

- `make dem` (`scripts/prepare_dem.sh`, `gdal` tools servisi, Debian GDAL 3.10.3; D-074):
  - Copernicus GLO-90: bbox için 18 karo (~70 MB, `data/dem/src` önbellek). 404 = deniz karosu; diğer indirme hataları betiği durduruyor (D-075).
  - `gdalinfo` incelemesi → `gdalbuildvrt` → `gdal_translate -of COG` (EPSG:4326, kaynak ızgarası, resampling yok, 50 MB) ve `gdalwarp` EPSG:3857 bilinear (D-076).
  - `gdaldem hillshade` (az 315, alt 45, z 1.32), siyah/beyaz + alfa'ya çevirme, `gdal2tiles --xyz` z6–11: 900 karo, 54 MB, `meta.json` (D-077).
  - Yedek yol: `DEM_SOURCE=auto` indirme yapılamazsa sentetik yüzeye düşüyor; `DEM_SOURCE=copernicus|synthetic` ile zorlanabiliyor. Gerçek çalışma ~28 sn.
- `GET /api/terrain/elevation`: rasterio, dataset süreç başına bir kez açık, kilitli; bilinear, nodata'da en yakın piksel; `out_of_region` (400), `terrain_unavailable` (503); dosya değişince yeniden açılıyor (D-078). Backend `data/dem`'i salt okunur bağlıyor.
- Frontend:
  - Hillshade raster katmanı (`meta.json` varsa; D-080), "Terrain" bölümünde aç/kapa ve opaklık kaydırıcısı (D-081), sentetikse "synthetic" etiketi, Copernicus atfı.
  - Detayda "Terrain" ve "Above ground" (GNSS − arazi, yoksa baro), "Low flight" rozeti: havada, AGL < 300 m, `airport_buffer` dışında ve en yakın havalimanına ≥ 10 km (D-079). Geçmiş modunda da çalışıyor.
- nginx: `meta.json` `no-cache`.
- Testler: pytest 134 → 158 (örnekleme matematiği, nodata, kenar, bölge dışı, geçersiz koordinat, 503, tek açılış, yeniden açılış). vitest 79 → 94 (AGL, alçak uçuş, nokta-poligon, havalimanı yakınlığı, önbellek anahtarı).
- `make ui-smoke` 29 → 36 kontrol: hillshade karoları 200, aç/kapa, opaklık, detayda AGL. Prod derlemesinde karo kontrolü de koşuyor.
- Dokümanlar: ICD 1.5 (endpoint ayrıntısı, iki hata kodu, IF-9 §7.4), DECISIONS D-074…D-082, README (Terrain bölümü, atıf), ARCHITECTURE (DEM diyagramı).
- Learn: `12-raster-ve-dem.md` (2.900 kelime); `00-basla-buradan.md` güncellendi.

**Doğrulanan kabul kriterleri**

- Hillshade katmanı görünüyor ve açılıp kapanıyor (smoke + ekran görüntüsü `data/ui-smoke/desktop-hillshade.png`).
- Uçak detayında AGL var (smoke: "Above ground" satırı dolu). "Low flight" rozeti tarayıcıda ayrı bir betikle görüldü.
- `make dem` pipeline'ı baştan sona çalıştırıyor (gerçek veri; ayrıca sentetik ve ağ yokken `auto` yedeği denendi).
- Örnek değerler: Uludağ 2506 m (gerçek 2543), LTBY 786,5 m (OurAirports 788,8), LTFJ 93,5 m (95,1), Karadeniz 0.
- Prod derlemesinde endpoint ve karolar çalışıyor (backend uid 10001 COG'u okuyabiliyor). `make test`, `make lint` temiz; dev yığını geri açık.

**Sapmalar**

- GDAL araçları resmî OSGeo imajı yerine kendi Debian imajımızda (ghcr erişim sorunu; D-074). Sentetik yedek rasterio yerine numpy + GDAL Python ile.
- Plan dışı ekler: `meta.json` ile katman algılama, saydam RGBA hillshade, dosya değişince COG'un yeniden açılması, 10 km havalimanı yakınlığı kuralı, `DEM_BASE_URL` (yedek yolu test etmek için).

**Bilinen sorunlar / notlar**

- AGL'de geoid düzeltmesi yok (GLO-90 EGM2008, ADS-B GNSS irtifası genelde WGS84 elipsoidi; bölgede ~36–40 m fark). GLO-90 bir DSM, şehirlerde bina yüksekliğini içeriyor.
- Sentetik uçaklar araziyi bilmiyor; bazıları dağın içinden geçiyor ve AGL negatif görünüyor (örn. LTFJ yaklaşmasında −30 m).
- "Low flight" yalnızca seçili uçağın detayında; tüm uçaklar için hesaplama relay tarafında yapılmalı (Faz 8 sonrası).
- Geçmiş modunda 10 km kuralı uygulanmıyor (REST'in en yakın havalimanı şimdiki konumu anlatıyor); yalnızca `airport_buffer` bölgeleri sayılıyor.
- Karolar nginx'te 7 gün önbellekli; `make dem` yeniden çalıştırılırsa tarayıcı eski karoları gösterebilir (sert yenileme gerekir).
- `nginx.conf` tek dosya bind mount: inode değiştiren düzenlemelerden sonra `nginx -s reload` yetmiyor, `docker compose restart nginx` gerekiyor (D-082).

## Sıradaki adım

Proje sahibinin Faz 7 onayı. Ardından Faz 8 (HTMX ops paneli, retention döngüsü, CI'ı tamamlama, README ve `docs/DEMO.md`, temiz clone'dan `make up` kontrolü) → `learn/13-htmx-test-ve-cicd.md` ve `learn/99-genel-bakis-ve-mulakat.md`.
