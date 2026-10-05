# Karar Kaydı (Decision Log)

Her kayıt: **tarih**, **karar**, **neden**, **alternatif(ler)**. Bu dosya `learn/` dosyalarıyla birlikte okunacak bir öğrenme materyalidir; "neden böyle yaptık?" sorusunun cevabı burada.

---

## D-001 — Backend için Django, FastAPI yok

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Backend Django 6.x + GeoDjango + DRF + Channels ile yazılır. FastAPI kullanılmaz.
- **Neden:** Proje sahibi FastAPI'yi zaten biliyor; bu projenin öğrenme hedefi Django. Ayrıca GeoDjango (spatial ORM, admin harita widget'ı), migration sistemi, admin paneli ve management command'lar coğrafi bir platform için hazır "pil" sağlıyor.
- **Alternatif:** FastAPI + SQLAlchemy + GeoAlchemy2 + Alembic. Daha ince ve async-native, ama admin, auth ve migration'ı ayrı ayrı kurmak gerekirdi ve öğrenme hedefini karşılamazdı.

## D-002 — Ortam spec'i PLAN.md'ye göre öncelikli

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** `docs/superpowers/specs/2026-10-05-hezarfen-environment-design.md` geçerlidir: her faz kapanışından sonra durulur ve onay beklenir; erişim adresi `localhost:8800`; `learn/` ana repoda gitignore'dadır ve kendi içinde ayrı bir yerel git reposudur; remote/push yok.
- **Neden:** Proje sahibi geliştirme sırasında başında; makinede 80, 5432, 6379, 5173 gibi portları kullanan başka projeler var.
- **Alternatif:** PLAN.md'deki gözetimsiz akış ve 80 numaralı port. Çakışma yaratırdı.

## D-003 — Sürümler: kurulum anındaki güncel stabil sürümler

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Python 3.14, Django 6.1.1 (PLAN "5.x" diyordu; güncel stabil 6.1), PostGIS imajı `postgis/postgis:18-3.6`, Redis 8.8, nginx 1.30 (stable dal), Go 1.27, Node 24 (aktif LTS "Krypton"), Vite 8, React 19.3, vitest 5, ESLint 10.
- **Neden:** PLAN §0.5: güncel stabil sürümlere sabitle. Beta/RC imajlar (PostGIS 19beta) bilinçli olarak dışarıda.
- **Alternatif:** Django 5.2 LTS. Daha uzun destek süresi var ama PLAN güncel stabili istiyor; 6.1'de API farkı bu proje için önemsiz.

## D-004 — TypeScript 6.0, 7.0 değil

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** `typescript@6.0.3`.
- **Neden:** npm'deki en güncel sürüm 7.0 (Go ile yeniden yazılan derleyici), fakat `typescript-eslint@8.71` peer dependency olarak `typescript <6.1.0` istiyor. ESLint'in tip bilgisiyle çalışabilmesi için uyumlu en yeni sürüm 6.0.
- **Alternatif:** TS 7 + ESLint'te tip kurallarını kapatmak ya da `--legacy-peer-deps`. Kırılgan; typescript-eslint TS 7'yi desteklediğinde yükseltilebilir.

## D-005 — ASGI sunucusu olarak uvicorn

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Backend hem dev hem prod'da `uvicorn hezarfen.asgi:application` ile çalışır. Dev'de `--reload` (watchfiles), prod'da `--workers 2 --proxy-headers`.
- **Neden:** Spec "polling olmadan hot-reload" istiyor. Django'nun `runserver` autoreloader'ı `pywatchman` yoksa her saniye dosyaları `stat` eden StatReloader'a düşer. uvicorn'un reloader'ı `watchfiles` (Rust, inotify) kullanır. uvicorn `websockets` ile WebSocket'i de destekler, Channels ile uyumludur.
- **Alternatif:** daphne (Channels'ın referans sunucusu; reload yok), `runserver` + daphne (StatReloader polling), gunicorn + uvicorn worker (prod'da gereksiz katman).

## D-006 — relay worker'ının dev reload'u `watchfiles` CLI ile

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Dev'de relay `watchfiles --filter python "python manage.py relay" /app` ile çalışır; `.py` değişince süreç yeniden başlatılır.
- **Neden:** Management command'lar uzun ömürlü döngülerdir, Django autoreloader'ı onları kapsamaz. `watchfiles` zaten `uvicorn[standard]` ile geliyor; ek bağımlılık yok.
- **Alternatif:** `django-extensions`'ın `runscript`/`--reload` desteği veya elle container restart.

## D-007 — Healthcheck stratejileri

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:**
  - backend: `/api/health` hem PostGIS'e (`postgis_lib_version()`) hem Redis'e (`PING`) dokunur; biri yoksa 503.
  - relay: HTTP sunucusu olmayan bir worker; döngü her 5 sn'de `/tmp/relay-heartbeat` dosyasına `touch` atar, healthcheck dosyanın 30 sn'den taze olduğunu kontrol eder.
  - ingest (prod): distroless imajda shell/curl yok; binary `-healthcheck` bayrağıyla kendi `/healthz`'ini yoklar. Dev imajında `curl`.
  - frontend: dev'de `node -e fetch(...)`, prod'da busybox `wget`.
- **Neden:** "Container çalışıyor" ile "servis iş yapıyor" aynı şey değil; healthcheck gerçek bağımlılığı doğrulamalı.
- **Alternatif:** Sadece process kontrolü ya da relay'e küçük bir HTTP sunucusu eklemek (fazladan yük).

## D-008 — Migration'ları backend çalıştırır; relay ve ingest backend'in healthy olmasını bekler

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Backend başlarken `migrate` çalıştırır. `relay` ve `ingest` `depends_on: backend: service_healthy` ile bekler.
- **Neden:** Şemanın sahibi Django; Go servisi tabloları oluşturmaz. Backend healthy ⇒ migration bitti ⇒ tablolar hazır.
- **Alternatif:** Ayrı bir tek seferlik `migrate` servisi (`service_completed_successfully`). Daha "temiz" ama bir servis daha demek; backend replikasyonu olmadığı için gerek yok.

## D-009 — Frontend prod imajı da 5173'te dinler

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Prod'da frontend, build çıktısını servis eden küçük bir nginx'tir ve 5173'te dinler.
- **Neden:** Gateway `nginx.conf` dev ve prod'da birebir aynı kalır (`upstream frontend { server frontend:5173; }`).
- **Alternatif:** Build çıktısını gateway nginx'e kopyalamak (tek nginx). Daha az container ama dev/prod config'i ayrışır.

## D-010 — `tracking` ve `ops` app'leri Faz 0'da oluşturuldu

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Faz 0'da yalnızca iki app var: `ops` (`/api/health`) ve `tracking` (placeholder `relay` komutu). `geofencing` ve `terrain` Faz 1'de eklenir.
- **Neden:** Faz 0 kabul kriteri `relay` servisinin ayağa kalkmasını ve `/api/health`'in çalışmasını istiyor; management command bir app içinde yaşamak zorunda.
- **Alternatif:** Ayrı bir `core` app'i; PLAN'daki app listesine yabancı bir isim eklerdi.

## D-011 — Frontend `node_modules` anonim volume'da

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Dev'de `./frontend` bind mount edilir, `/app/node_modules` ise anonim volume'dur; `make up` `--renew-anon-volumes` ile çalışır.
- **Neden:** Host'ta Node yok (spec); `node_modules` imajın içinde `npm ci` ile oluşur. Bind mount onu ezmesin diye ayrı volume gerekir; anonim volume her `up`'ta yenilenir, böylece `package.json` değişince eski paketler kalmaz.
- **Alternatif:** İsimli volume (bağımlılık değişince elle silmek gerekir) veya host'ta `npm install` (spec'e aykırı).

## D-012 — Admin static dosyaları prod'da Faz 1'e kadar servis edilmiyor

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Faz 0'da `/static/` nginx üzerinden backend'e yönlenir; prod'da (`DEBUG=0`) admin CSS'i Faz 1'de `collectstatic` + servis çözümüyle eklenecek.
- **Neden:** Faz 0 kapsamı health ve iskelet; admin Faz 1 işi.
- **Alternatif:** Şimdiden whitenoise eklemek.

## D-013 — Dev container'larında araç önbellekleri bind mount dışında

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** `RUFF_CACHE_DIR=/tmp/ruff-cache`, pytest `-p no:cacheprovider`, air `tmp_dir = "/tmp/air"`.
- **Neden:** Dev container'ları root çalışıyor; bind mount'a yazılan önbellekler host'ta root'a ait dosyalar bırakıyordu (ilk test turunda yaşandı) ve kullanıcı bunları `sudo`'suz silemiyordu.
- **Alternatif:** Container'ları host UID'siyle (`user: "1000:1000"`) çalıştırmak. Daha genel bir çözüm, ama imajdaki kurulumlarla (pip, go mod cache, node_modules) izin çatışmaları çıkarır.

## D-014 — Docker Desktop WSL entegrasyonu yeniden başlatmayla düzeldi (ortam notu)

- **Tarih:** 2026-10-05 (Faz 0)
- **Karar:** Docker Desktop açılıştan sonra WSL'de `/var/run/docker.sock` oluşmazsa Docker Desktop yeniden başlatılır.
- **Neden:** Ubuntu entegrasyonu ayarlarda açık olduğu halde proxy süreci başlamadı; Windows tarafında yeniden başlatma 20 sn'de soketi getirdi. Kod değişikliği gerektirmiyor; bir sonraki oturumda aynı belirti görülürse ilk yapılacak şey bu.
- **Alternatif:** WSL içine ayrı Docker Engine kurmak; spec host'a araç kurmamayı tercih ediyor.

## D-015 — Referans veri ayrı bir `reference` app'inde

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `airports` ve `provinces` modelleri `reference` app'inde. App listesi: `tracking`, `reference`, `geofencing`, `terrain`, `ops`.
- **Neden:** PLAN §5 "tracking veya ayrı reference modülü" seçeneğini bırakıyor. Havalimanı ve il verisi uçak takibinden bağımsız, nadiren değişen ve dışarıdan yüklenen bir katman. `tracking` yalnızca ingest'in yazdığı tablolara odaklanıyor.
- **Alternatif:** İkisini `tracking` içine koymak. Bir app eksik olurdu ama "canlı veri" ile "statik referans" karışırdı.

## D-016 — ogr2ogr staging tablolarına yazar, `import_reference` Django tablolarına aynalar

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `scripts/load_reference_data.sh`, ogr2ogr ile `stage_airports` ve `stage_provinces` tablolarına `-overwrite` yazar. Ardından `manage.py import_reference` tek transaction'da bunları `airports` ve `provinces` tablolarına `INSERT … ON CONFLICT DO UPDATE` ile aktarır, staging'de olmayanları siler ve staging tablolarını düşürür.
- **Neden:** Şemanın sahibi Django (ICD §3). ogr2ogr'un hedef tabloya `-overwrite` yazması Django'nun tablosunu silip kendi şemasıyla yeniden yaratırdı (migration'la uyumsuz kolon tipleri, index adları). Böylece işler bölünüyor: ogr2ogr format okuma, geometri üretme ve filtrelemeyi yapıyor; Django şemayı ve upsert'i yönetiyor. İşlem idempotent; script tekrar tekrar çalıştırılabilir.
- **Alternatif:** ogr2ogr `-append` ile doğrudan Django tablosuna yazmak. Kolon eşleme `-sql` ile yapılabilir ama tekrar çalıştırmada kopya satır oluşur ve "güncelle ya da sil" mantığı kurulamaz.

## D-017 — `positions.icao24` foreign key değil; ayrı `(icao24, ts)` B-tree yok

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `positions.icao24` düz bir `varchar(6)`. `(icao24, ts)` için yalnızca unique constraint var.
- **Neden:** `positions` en sık yazılan, append-only zaman serisi tablosu. FK her insert'te `aircraft` tablosunda bir kontrol yapar ve yükleme sırasını zorunlu kılar. Tarihçe de uçak kaydından bağımsız yaşayabilmeli. Unique constraint zaten `(icao24, ts)` üzerinde bir B-tree index yaratıyor; PLAN'daki ayrı B-tree aynı index'in kopyası olurdu.
- **Alternatif:** FK + ayrı index. Bütünlük kontrolü kazanılır, yazma maliyeti ve disk iki katına çıkar.

## D-018 — Ingest'in güvendiği default'lar `db_default` ile kolonda

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `on_ground` (`false`) ve `source` (`live`) `db_default` ile tanımlandı.
- **Neden:** Django'nun `default=` parametresi yalnızca Python tarafında, ORM ile kayıt oluşturulurken uygulanır; veritabanı kolonunda default oluşmaz. Ingest ham SQL ile yazdığı için ilk test turunda `null value in column "source"` hatası alındı. `db_default` default'u DDL'e yazar.
- **Alternatif:** Ingest'in her kolonu her zaman göndermesi. ICD'de zaten öyle, ama veritabanının kendi kendini koruması daha sağlam.

## D-019 — Static dosyalar WhiteNoise ile (dev + prod); D-012 kapandı

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `whitenoise` middleware'i. Dev'de `WHITENOISE_USE_FINDERS` ve autorefresh açık, collectstatic gerekmiyor. Prod'da imaj build'inde `collectstatic` çalışıyor; dosyalar `CompressedManifestStaticFilesStorage` ile hash'li ve gzip'li, `Cache-Control: immutable` ile servis ediliyor.
- **Neden:** Django'nun static servisi yalnızca `runserver`'a özgü; uvicorn kullandığımız için dev'de de admin CSS'i servis edilmiyordu. WhiteNoise tek bağımlılıkla iki ortamı da çözüyor.
- **Alternatif:** collectstatic çıktısını bir volume ile gateway nginx'e vermek. Daha "klasik" ama ek volume ve dev/prod farkı demek.

## D-020 — `make up-prod` `DJANGO_DEBUG=0`'ı zorlar

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `x-db-env` içinde `DJANGO_DEBUG: ${DJANGO_DEBUG:-0}`; `make up-prod` komutu `DJANGO_DEBUG=0` export ederek çalışır.
- **Neden:** Prod smoke testinde `.env`'deki dev değeri (`1`) `env_file` üzerinden prod-like stack'e de geçiyordu; yani Faz 0'daki "prod" testi aslında DEBUG açıkken yapılmıştı. Compose'da `environment`, `env_file`'ı ezer; interpolasyonda da shell değişkeni `.env`'i ezer.
- **Alternatif:** Ayrı bir `.env.prod`. Daha esnek ama ikinci bir env dosyasının bakımı gerekir.

## D-021 — `make seed`: host kullanıcısıyla, önbellekli indirme, fixture yedeği

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `make seed` tek bir backend container'ı `--user $(id -u):$(id -g)` ile ve `scripts/` ile `data/` mount edilmiş olarak çalıştırır: migrate → load script → `seed_geofences`. İndirilen dosyalar `data/reference/` altında önbelleğe alınır. İndirme ya da yükleme başarısız olursa veya `REFERENCE_OFFLINE=1` verilirse aynı ogr2ogr akışı `scripts/fixtures/*.geojson` ile çalışır (8 havalimanı, 4 kaba il sınırı; filtrelerin işlediğini göstermek için bölge dışı ve tip dışı birer kayıt da var).
- **Neden:** Dev container'ları root çalışıyor (D-013); indirmeler host'ta root'a ait dosya bırakmasın. Önbellek tekrar çalıştırmayı 7 saniyeye indiriyor ve ağ olmadan da çalışmayı sağlıyor.
- **Alternatif:** Script'i host'ta çalıştırmak (GDAL host'a kurulmaz, spec'e aykırı) veya ayrı bir GDAL imajı (`ghcr.io/osgeo/gdal`). Backend imajında zaten `gdal-bin` var, ikinci imaj gereksiz.

## D-022 — Referans veride birim ve isim normalizasyonu

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** Havalimanı yüksekliği `elevation_ft * 0.3048` ile `elevation_m`'ye çevrilir (ICD: irtifa metre). İl adı Natural Earth'ün `name_tr` alanından alınır, boşsa `name`. Boş CSV hücreleri `NULL` olur. İl geometrileri `ST_MakeValid` + `ST_Multi`'den geçer.
- **Neden:** Tüm arayüzlerde tek birim sistemi. `name` alanı ASCII'ye indirgenmiş ("Sirnak"), `name_tr` doğru yazılmış ("Şırnak").
- **Alternatif:** Ham değerleri saklayıp API'de çevirmek. Her tüketici dönüşümü tekrarlardı.

## D-023 — Geofence seed: geography buffer, 64 köşe, havalimanı verisine bağımlı

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** `seed_geofences`, `ST_Buffer(geom::geography, 15000, 'quad_segs=16')` ile 64 köşeli bir çember üretir; merkez `airports` tablosundaki LTFM ve LTFJ'dir. Havalimanları yüklenmemişse komut açık bir hata verir. Geofence'ler `name` + `kind` ile `update_or_create` edilir.
- **Neden:** Metre cinsinden doğru yarıçap (test: tüm köşeler 15 km ± 100 m, alan 706 km² ≈ π·15²). 64 köşe, relay'in her batch'te çalıştıracağı `ST_Contains` için yeterince hassas ve ucuz. Koordinatları koda gömmek referans veriyle çelişebilirdi.
- **Alternatif:** Koda gömülü koordinatlar. Bağımsız çalışır ama iki doğruluk kaynağı olur.

## D-024 — `prune_positions` Faz 1'de

- **Tarih:** 2026-10-05 (Faz 1)
- **Karar:** PLAN §5'teki retention komutu modellerle birlikte Faz 1'de yazıldı (`make prune`). Zamanlanmış çalıştırma (cron) henüz yok.
- **Neden:** Komut yalnızca `positions` modeline bağlı ve test edilmesi kolay. Zamanlama Faz 8'deki ops işleriyle birlikte ele alınacak.
- **Alternatif:** Faz 2'de ingest ile birlikte yazmak.
