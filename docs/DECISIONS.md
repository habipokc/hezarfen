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

## D-025 — Ingest container'ı host kullanıcısıyla çalışır

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** `ingest` servisi hem prod'da hem dev'de `user: "${HEZARFEN_UID:-1000}:${HEZARFEN_GID:-1000}"` ile çalışır; Makefile `id -u`/`id -g` değerlerini export eder. Dev imajında `HOME=/tmp`, `GOCACHE=/tmp/go-cache` ve `/go` herkese yazılabilir. Go cache volume'ları yeni adlarla (`go-mod`, `go-cache`) açıldı.
- **Neden:** Faz 0'dan kalan sorun: distroless `nonroot` (uid 65532) bind mount edilen `./data/raw`'a yazamıyordu; dev container root olduğu için de `go.mod` ve raw kayıtlar root'a ait oluyordu. Host uid'si ile her iki sorun birden çözülüyor.
- **Alternatif:** `data/raw`'ı named volume yapmak (kayıtlar host'tan zor erişilir) ya da dosyaları sonradan `chown` etmek.

## D-026 — Dev imajlarına ayrı `:dev` etiketi

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** `docker-compose.override.yml` dev imajlarına `hezarfen-<servis>:dev` etiketi veriyor (relay için ayrı `hezarfen-relay:dev`).
- **Neden:** Faz 0'dan kalan gizli bir hata: dev ve prod target'ları aynı varsayılan etiketi (`hezarfen-ingest`) paylaşıyordu. `make up-prod` sonrası `make test-ingest` distroless prod imajında çalıştı; imaj `sh -c` argümanlarını yok saydı ve ingest'i sonsuza kadar başlattı (test "takıldı"). relay ile backend aynı etiketi paralel build edince de "already exists" hatası çıkıyor, bu yüzden relay'in etiketi ayrı.
- **Alternatif:** Her dev komutundan önce `--build` (yavaş ve kırılgan).

## D-027 — Ingest paket yapısı: `clean` paketi ve `source.Frame`

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** PLAN'daki `internal/{config,opensky,source,store,publish,geo}`'ya ETL'in "clean" adımı için `internal/clean` eklendi. Kaynaklar ortak `Source` interface'iyle (`Name`, `Next(ctx) (Frame, error)`) `Frame` döndürür: snapshot + `Retime` + `Restart` + `Credits`. Null alanlar `sql.Null*` yerine pointer.
- **Neden:** Temizleme kuralları hem kaynak hem depodan bağımsız, saf ve TDD'ye en uygun parça. Pointer'lar JSON `null`'ı doğrudan karşılıyor ve pgx dizilerinde `NULL` olarak gidiyor; `sql.Null*` hem JSON hem dizi tarafında ek dönüşüm isterdi.
- **Alternatif:** Kuralları `source` veya `store` içine gömmek.

## D-028 — Toplu yazım: `unnest` dizileri, tek transaction, yazma hatasında da yayın

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** Her döngü tek transaction. `aircraft` → `aircraft_latest` → `positions` sırasıyla, her tablo için tek `INSERT … SELECT FROM unnest($1::text[], …)` ifadesi; üçü tek `pgx.Batch` ile tek ağ turunda gider. `aircraft_latest` yalnızca daha yeni `ts` ile güncellenir; `aircraft` güncellemesinde null gelen callsign eskisini silmez. Veritabanı yazımı başarısız olsa bile Redis'e yayın yapılır.
- **Neden:** `COPY` en hızlısı ama `ON CONFLICT` yapamaz (staging tablo gerekir); 60–100 satırlık batch'te `unnest` farkı ölçülemez ve idempotency'yi korur. Canlı harita tarihçe tablosundaki bir sorun yüzünden donmamalı; relay zaten yeniden başlarken PostGIS'ten okur.
- **Alternatif:** `COPY` + geçici tablo + `INSERT … SELECT`; satır başına `INSERT`.

## D-029 — Replay: kayıt zamanında temizle, sonra duvar saatine taşı

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** Replay, kayıtları dosya adına göre (`YYYY-MM-DD/HHMMSS.json.gz`, alt dizinler dahil) sıralar, aralıkları `REPLAY_SPEED`'e bölerek bekler ve sonsuz döngüde oynatır. Temizleme kayıttaki zamanlar üzerinde çalışır; kabul edilen kayıtlar `Retime` ile duvar saatine taşınır. 60 sn'den uzun boşluklar (ayrı kayıt oturumları) beklenmez, yeni segment başlar. Döngü başa sardığında `Restart` ile jump filtresi sıfırlanır. Kaynak dizin `REPLAY_DIR` (varsayılan `$DATA_DIR/raw`).
- **Neden:** Zaman kaydırılmazsa eski `ts`'ler "son 60 sn" penceresine hiç girmez. Zamanı hızla birlikte sıkıştırıp sonra temizlemek ise 5× hızda 250 m/s'lik uçağı 1.250 m/s gösterir ve jump filtresi her şeyi atar.
- **Alternatif:** Orijinal zamanlarla yayınlamak (downstream bozulur); hız çarpanını jump eşiğine yansıtmak (fiziksel anlamı kaybolur).

## D-030 — Jump filtresi ayrıntıları

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** Hız, uçağın son *kabul edilen* fix'ine göre hesaplanır; reddedilen fix çapayı taşımaz. Aynı çapaya karşı 3 ardışık red olursa çapa hatalı sayılır ve yeni fix kabul edilir (loglanır). Aynı veya daha eski `ts`'de kontrol yapılmaz (OpenSky son konumu tekrarlar; veritabanı `ON CONFLICT` ile eler). 10 dakika görülmeyen uçağın çapası unutulur.
- **Neden:** Tek bir hatalı ilk fix, çapa hiç güncellenmezse uçağın bütün izini sonsuza kadar reddettirir.
- **Alternatif:** Medyan/Kalman tabanlı filtre (bu proje için fazla).

## D-031 — Sentetik trafik modeli

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** İrtifa, süreye değil uçulan mesafeye bağlı: `min(seyir, s·0,08, (D−s)·tan3°)`. Seyir irtifası, profilin tepe noktasının %85'i (en fazla 10.800 m, 300 m katı), böylece kısa bacaklarda da düz bir seyir bölümü kalıyor. Hız irtifaya bağlı (75 → 128 → 230 m/s). Uçuşların %75'i LTFM/LTFJ'ye gidip geliyor; %20'si bölgeyi kenardan kenara geçen yabancı overflight. İnişten sonra 60–180 sn park. Havalimanları DB'den (large/medium, bbox içi), DB boşsa gömülü listeden. Varsayılan `SYNTHETIC_SEED=1`.
- **Neden:** Mesafe tabanlı profil, her rota uzunluğunda tırmanış ile alçalmanın sığmasını garanti ediyor. Hub ağırlığı geofence uyarılarını test edilebilir kılıyor (testte 30 dakikada ≥10 uçak). Sabit seed sayesinde her hot reload tabloya 60 yeni uçak eklemiyor.
- **Alternatif:** Zamana bağlı faz makinesi (kısa rotalarda tırmanış bitmeden alçalma gerekir); rastgele seed (tablo şişer).

## D-032 — Live mod: anonim erişime izin, adaptive eşik, raw zone

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** `SOURCE_MODE=live` credential olmadan da çalışır (anonim, uyarı loglanır); `auto` ise yalnızca credential varsa live seçer. Adaptive eşik `OPENSKY_DAILY_CREDITS`'in %20'si (varsayılan 4.000 ya da anonimde 400). 429'da kaynak `Retry-After` kadar bekleyip tekrar dener; 5xx ve ağ hatalarında istemci 1-2-4 sn backoff ile 3 kez dener. Token süresi dolmadan 60 sn önce yenilenir ve 401'de bir kez yenilenir. Raw dosyalar duvar saatine (UTC) göre adlandırılır, geçici dosyaya yazılıp `rename` edilir, izinleri 0644.
- **Neden:** Anonim live, credential gelmeden gerçek veriyi denemeyi sağlıyor. Atomik yazım, aynı dizini okuyan replay'in yarım dosya görmemesi için.
- **Not:** 10 sn'lik poll günde 8.640 istek eder; 4.000 kredi yaklaşık 11 saat yeter, adaptive moddan sonra 30 sn'lik aralıkla yaklaşık 6,7 saat daha. Sürekli canlı yayın için `POLL_INTERVAL_SECONDS=20` önerisi README'de.
- **Alternatif:** Live için credential zorunluluğu.

## D-033 — Gerçek OpenSky fixture'ı repoda

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** `make record` (`scripts/record_fixture.sh`) ile anonim erişimle 25 snapshot (10 sn arayla, yaklaşık 80 uçak, toplam ~110 KB) alındı ve `ingest/testdata/opensky/2026-10-05/` altına commit'lendi. Parser ve replay testleri bu kaydı kullanıyor.
- **Neden:** PLAN §4: ağ varsa küçük bir gerçek kayıt. Gerçek veri, sentetikte olmayan durumları (stale konumlar, kategori 0, yerdeki uçaklar) içeriyor: kayıtta konumların yaklaşık %12'si 15 sn'den eski.
- **Alternatif:** Sentetik çıktıdan fixture üretmek (ağ olmasaydı yedek yol buydu).

## D-034 — Go store/publish entegrasyon testleri geçici şemada

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** `store` testleri `INGEST_TEST_DATABASE_URL` varsa çalışır: geçici bir şema açar, tabloları `CREATE TABLE … (LIKE public.x INCLUDING ALL)` ile Django'nun migrate ettiği tablolardan kopyalar ve `search_path`'i o şemaya çevirir. `publish` testi `INGEST_TEST_REDIS_URL` ile ayrı bir kanalda (`test.positions.batch`) çalışır. `make test-ingest` iki değişkeni de verir; CI'daki Go job'ında yoktur ve testler atlanır.
- **Neden:** Gerçek DDL'e (unique kısıt, identity, `db_default`) karşı test etmek gerekiyor, ama geliştirme verisine dokunmadan. Pub/sub kanalları Redis veritabanları arasında ortak olduğu için çalışan relay test mesajlarını görmemeli.
- **Alternatif:** CI'da Go job'ına PostGIS ekleyip Django migrate çalıştırmak (Faz 8'de değerlendirilebilir).

## D-035 — ICD 1.2: uçak başına `ts`, ek metrikler

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** `positions.batch/v1` içindeki her uçağa konum zamanı `ts` eklendi; `/metrics`'e `cycles`, `poll_interval_seconds`, `last_positions_inserted`, `last_subscribers`, `rejected_total` eklendi. Şema sürümü değişmedi.
- **Neden:** Gerçek veride konum zamanı, döngü zamanından 15 sn'ye kadar geride olabilir; relay'in (Faz 4) doğru "son görülme" hesaplaması için gerekli. Alan eklemek ICD §9'a göre geriye uyumlu.
- **Alternatif:** Relay'in envelope `ts`'ini kullanması (15 sn'ye kadar hata).

## D-036 — `/healthz` döngü tazeliğine bağlı değil

- **Tarih:** 2026-10-05 (Faz 2)
- **Karar:** `/healthz`, süreç ayakta olduğu sürece 200 döner. Döngü sağlığı `/metrics`'teki `last_poll_at` ve `error_count` ile izlenir (Faz 8 ops paneli).
- **Neden:** Live modda 429 sonrası bekleme saatler sürebilir; healthcheck buna bağlansaydı Docker container'ı gereksiz yere "unhealthy" yapar, `restart` ile de kredi harcayan bir döngüye sokardı.
- **Alternatif:** `last_poll_at`'e göre 503 dönmek.

## D-037 — DRF + drf-gis + drf-spectacular, django-filter yok

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** djangorestframework 3.18.1, djangorestframework-gis 1.3.0, drf-spectacular 0.30.0, shapely 2.1.2. Sorgu parametreleri (`bbox`, `since`, `active`, `type` …) `hezarfen/api/params.py` içindeki saf fonksiyonlarla elle ayrıştırılıyor. Paylaşılan API kodu `hezarfen/api/`, endpoint'ler ilgili app'lerde (`tracking/api.py`, `geofencing/api.py`, `reference/api.py`).
- **Neden:** Az ve basit filtre var; elle ayrıştırma her 400 yanıtını ICD §7.1 biçiminde ve doğru kodla (`invalid_bbox`, `window_too_large`) vermeyi kolaylaştırıyor. Saf fonksiyonlar DB'siz test edilebiliyor.
- **Alternatif:** django-filter `FilterSet` (bağımlılık + hata biçimini ayrıca uyarlamak gerekirdi).

## D-038 — Tek hata biçimi: özel DRF exception handler

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `hezarfen.api.errors.exception_handler` her hatayı `{"error": {"code", "message", "details"}}` biçimine çeviriyor. `ApiError` açık kod taşıyor; serializer `ValidationError`'larında `invalid_geometry` gibi bilinen kodlar üst seviyeye çıkarılıyor, diğerleri `invalid_parameter`. DRF'in kendi hataları `default_code` ile geliyor (`parse_error`, `method_not_allowed`). DB bağlantı hatası 503 `unavailable`. Bilinmeyen `/api/` yolları catch-all ile JSON 404.
- **Neden:** Frontend tek bir hata yolu yazabilsin; ICD §7.1 sözleşmesi.
- **Alternatif:** DRF varsayılanı (`{"detail": …}` ve alan bazlı dict; biçim duruma göre değişiyor).

## D-039 — API'de kimlik doğrulama yok, CSRF yok

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `DEFAULT_AUTHENTICATION_CLASSES = []`, `AllowAny`. Geofence CRUD dahil her şey açık.
- **Neden:** Tek kullanıcılı yerel demo/portföy projesi; PLAN'da kullanıcı hesabı yok. Authentication sınıfı olmayınca `SessionAuthentication` da yok, dolayısıyla tarayıcıda admin oturumu açık olsa bile POST'lar CSRF'e takılmıyor.
- **Alternatif:** Token auth ya da geofence yazımını admin oturumuna bağlamak. Dışarı açılacaksa (Faz 8) yeniden değerlendirilecek.

## D-040 — En yakın havalimanı: KNN aday + metrik yeniden sıralama

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `ORDER BY geom <-> point LIMIT 8` (ORM'de `GeometryDistance`) ile 8 aday alınıyor, adaylar sferoid üzerindeki metre mesafesine (`Distance`) göre yeniden sıralanıp en yakını seçiliyor.
- **Neden:** `<->` geometry'de düzlemsel derece mesafesi kullanıyor; 41°K'de bir boylam derecesi enlem derecesinden ~%25 kısa, yani derece cinsinden en yakın, metre cinsinden en yakın olmayabiliyor (testte somut örnek var). İki aşama hem index'i kullanıyor hem doğru sonuç veriyor (RAG'deki "top-k getir, sonra rerank" kalıbı).
- **Alternatif:** `geography` KNN (ifade üzerinde ayrı GiST index gerekir) ya da `ORDER BY ST_Distance` (index kullanmaz, her satırı hesaplar).

## D-041 — İz: ham SQL `ST_MakeLine(geom ORDER BY ts)`, 24 saat sınırı

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `/api/aircraft/{icao24}/track` tek bir aggregate sorgu: `ST_MakeLine(geom ORDER BY ts)`, min/max ts ve nokta sayısı. 2'den az nokta varsa `geometry: null` (RFC 7946 LineString en az iki konum ister). `since` en fazla 24 saat geriye gidebilir, daha eskisi `window_too_large`. Bilinmeyen uçak 404.
- **Neden:** Sıralı birleştirme DB'de tek geçişte yapılıyor; satırları Python'a taşımaya gerek yok. 24 saat sınırı sentetik modda (2 sn tick) bir uçağın bir haftalık izinin 300 bin noktalık yanıta dönüşmesini engelliyor.
- **Alternatif:** Noktaları ORM ile çekip GEOS `LineString` kurmak.

## D-042 — Playback: bucket başına son konum, nginx gzip, sayfalama yok

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `DISTINCT ON (bucket, icao24) … ORDER BY bucket, icao24, ts DESC` ile her bucket'ta her uçağın en son konumu. Frame `ts`'i bucket başlangıcı (bucket'ın katlarına hizalı, ilk frame `start`'tan önce başlayabilir); boş bucket'lar dönmüyor. Varsayılanlar: `end = now`, `start = end − 15 dk`, `bucket = 10` (1–600). Pencere > 2 saat → `window_too_large`. Sıkıştırma nginx'te (`gzip on; gzip_proxied any; gzip_types application/json …`).
- **Neden:** Ölçüm: 15 dakikalık pencere 1,19 MB → gzip ile 208 KB. 2 saat yaklaşık 9,5 MB / 1,6 MB gzip; tek istekte kabul edilebilir ve frontend'de sayfalama mantığı gerektirmiyor. Sıkıştırma proxy'de olunca Django CPU harcamıyor ve bütün JSON yanıtlar faydalanıyor.
- **Alternatif:** Zaman bazlı sayfalama (`next` ile sonraki pencere), Django `GZipMiddleware`.

## D-043 — Geofence doğrulaması shapely'de, yayın commit sonrası

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `geofencing/validation.py`:
  - Yalnızca Polygon kabul ediliyor, en fazla 1000 vertex, koordinatlar geçerli aralıkta olmalı.
  - Geçersiz poligona `make_valid` uygulanıyor; sonuç tek poligon değilse (ör. kelebek → iki üçgen) hangi kuralın bozulduğu (`explain_validity`) ve kaç parçaya bölündüğü söylenerek reddediliyor.
  - Alan 0,25–20.000 km² arasında olmalı. Alan, poligonun kendi enleminde dereceyi metreye ölçekleyen yaklaşık eşit-alan dönüşümüyle hesaplanıyor.
  - Poligon bölge bbox'ıyla kesişmeli.
  - `kind` istemciden alınmıyor; her zaman `user_drawn`.
  - `geofences.changed/v1` mesajı `transaction.on_commit` ile yayınlanıyor; Redis hatası loglanıyor ama isteği bozmuyor.
- **Neden:** shapely istek sürecinde, DB'ye gitmeden ve ayrıntılı hata sebebiyle doğruluyor; PostGIS yalnızca temiz şekil saklıyor. Commit sonrası yayın, relay'in değişikliği görmeden cache'ini yenilemesini engelliyor.
- **Alternatif:** Doğrulamayı PostGIS'te (`ST_IsValid`, `ST_Area(geography)`) yapmak; pyproj ile gerçek eşit-alan projeksiyonu (ek bağımlılık, sınır kontrolü için gereksiz hassasiyet).

## D-044 — İl sınırları: `ST_Simplify` 0,01°, 5 ondalık

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `/api/provinces/` `ST_Simplify(geom, tol, preserveCollapsed=true)` döndürüyor. Varsayılan tolerans 0,01° (yaklaşık 1,1 km), `?simplify=0…0.1` ile değiştirilebilir (0 = orijinal). Koordinatlar 5 ondalığa yuvarlanıyor.
- **Neden:** Ölçüm: Natural Earth 10m zaten genelleştirilmiş (81 il, 9856 vertex). 0,005 sadece 6242'ye inerken 0,01 4407'ye indiriyor; yanıt 206 KB'tan 98 KB'a düşüyor. Bölgenin tamamını gösteren zoom'da bir piksel ~1 km, fark görünmüyor. `preserveCollapsed` küçük adaların kaybolmasını önlüyor.
- **Alternatif:** `ST_SimplifyPreserveTopology` (komşu il sınırları arasındaki boşlukları o da çözmüyor); vector tile (Faz 7+ için aşırı).

## D-045 — `/api/stats` ingest durumu

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `ingest: {"status": "ok"|"stale"|"starting"|"unreachable", "metrics": {…}|null}`. Backend `INGEST_METRICS_URL`'den (`http://ingest:8080/metrics`) 1 sn timeout ile çekiyor; `last_poll_at` 60 sn'den eskiyse `stale`.
- **Neden:** Frontend ve ops paneli tek alana bakarak durumu gösterebilsin; ham metrikler de ayrıntı için duruyor. Ingest kapalıyken endpoint yine 200 dönüyor.
- **Alternatif:** Metrikleri Redis'e yazdırmak (ingest'e yeni sorumluluk).

## D-046 — Sıçrama filtresinde 1 sn tolerans (Faz 2 hatası)

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `clean` sıçrama hızını `mesafe / (dt + 1)` ile hesaplıyor.
- **Neden:** Faz 3 smoke testinde synthetic modda `rejected_total.impossible_jump` değerinin 257'ye çıktığı görüldü. Her 30 sn'de bir 16 uçak (230 m/s seyirdekiler) reddediliyordu. Zaman damgaları tam saniyeye kesildiği için 2 sn'lik gerçek aralık 1 sn görünebiliyor (11,00 → 12,99): 460 m / 1 sn = 460 m/s > 400. Her iki damganın kesme hatası toplamda 1 sn'den az olduğu için gerçek aralık en fazla `dt + 1`; bu en düşük olası hızı veriyor ve gerçek ışınlanmaları yine yakalıyor.
- **Alternatif:** Synthetic'te sanal saat kullanmak (yalnızca sentetiği düzeltirdi; gerçek veride de aynı kesme var).

## D-047 — REST `Aircraft` özellikleri `lon`/`lat` dahil

- **Tarih:** 2026-10-05 (Faz 3)
- **Karar:** `/api/aircraft/live` Feature'larının `properties`'i ICD `Aircraft` nesnesinin tamamı (`lon`, `lat` dahil); geometri ayrıca var. `id_field` kapalı.
- **Neden:** Frontend REST'ten gelen veriyle WebSocket `snapshot`/`delta`'daki veriyi aynı tiple işleyebilsin (`feature.properties` doğrudan bir `Aircraft`). Fazlalık uçak başına ~30 bayt.
- **Alternatif:** Konumu yalnızca geometride tutmak.

## D-048 — Channels sürümleri, `realtime` uygulaması, uvicorn kalıyor

- **Tarih:** 2026-10-05 (Faz 4)
- **Karar:**
  - Bağımlılıklar: channels 4.3.2, channels-redis 4.3.0 (`RedisChannelLayer`, `REDIS_URL`); dev bağımlılıkları pytest-asyncio 1.4.0 ve daphne 4.2.3.
  - daphne yalnızca testte: `channels.testing` paket olarak import edilirken daphne'yi istiyor. Sunucu her iki ortamda da uvicorn.
  - Gerçek zamanlı kod yeni bir `realtime` uygulamasında (state, outbox, consumer, relay, sorgular). Geofence state machine `geofencing/tracker.py`'de.
  - `relay` komutu `tracking`'ten `realtime`'a taşındı.
- **Neden:** uvicorn Faz 0'dan beri ASGI sunucusu ve WebSocket'i zaten destekliyor; ikinci bir sunucu gereksiz. Relay ile consumer aynı state/delta kodunu paylaştığı için tek uygulamada duruyorlar.
- **Alternatif:** Prod'da daphne (Channels'ın referans sunucusu). `RedisPubSubChannelLayer` (daha yeni, ama kapasite ve süre sınırı davranışı daha az belgelenmiş).

## D-049 — Backpressure: bekleyen delta'lar birleştiriliyor (ICD 1.4)

- **Tarih:** 2026-10-05 (Faz 4)
- **Karar:** Her bağlantının bir `Outbox`'ı ve soketi bekleyen tek bir sender task'ı var. Channel layer handler'ları yalnızca outbox'a yazıp hemen dönüyor.
  - Gönderilmeyi bekleyen bir delta varken gelen yeni delta onunla birleştiriliyor (`merge_deltas`: uçak başına son upsert veya remove kazanır).
  - Yeni `subscribe` bekleyen delta'yı siliyor; yerini snapshot alıyor.
  - Geofence olayları, heartbeat ve hata mesajları FIFO kuyrukta bekliyor, hiç düşürülmüyor. 1000'i aşarsa bağlantı 1013 koduyla kapatılıyor.
- **Neden:**
  - Yavaş bir istemcide `send` bloklansa bile handler'lar bekletilmiyor. Böylece channels-redis'in kanal başına 100 mesajlık kapasitesi dolmuyor ve mesajlar sessizce kaybolmuyor.
  - Birleştirme bellek sınırını canlı uçak sayısına bağlıyor ve yavaş istemciye her zaman güncel durumu veriyor.
  - ICD 1.3'teki "eski delta'ları at, sonra snapshot gönder" planı her taşmada bir DB sorgusu demekti; birleştirme hiç sorgu yapmadan aynı sonucu veriyor.
- **Alternatif:** Sabit boyutlu kuyruk + taşınca snapshot (ICD 1.3); en eski mesajı düşürmek (istemcinin durumu bozulur); yavaş istemciyi hemen kapatmak.

## D-050 — WebSocket'te Origin kontrolü

- **Tarih:** 2026-10-05 (Faz 4)
- **Karar:** `AllowedHostsOriginValidator`: Origin başlığındaki host `ALLOWED_HOSTS`'ta değilse handshake 403 ile reddediliyor. `ws_tail` `Origin: http://localhost:8800` gönderiyor.
- **Neden:** WebSocket'ler CORS'a tabi değil; başka bir sitedeki sayfa kullanıcının tarayıcısından soket açabilir (cross-site WebSocket hijacking). Bugün veri herkese açık ve kimlik doğrulama yok, ama kontrol bedava ve ileride kimlik doğrulama eklenirse zaten gerekecek.
- **Alternatif:** Kontrolsüz kabul (websocat gibi araçlarla başlıksız bağlantı kolaylaşırdı).

## D-051 — Geofence kontrolü: batch başına tek sorgu, cache yalnızca isimler

- **Tarih:** 2026-10-05 (Faz 4)
- **Karar:**
  - Her batch için tek sorgu: `unnest(icao24[], lon[], lat[])` ile aktif `geofences` tablosu `ST_Contains` üzerinden join ediliyor. Ingest'in insert'lerindeki dizi deseninin aynısı; GiST indeksi her noktayı önce kutusu tutan bölgelere daraltıyor.
  - Relay'in cache'i yalnızca aktif bölgelerin `id → name` haritası. `geofences.changed` gelince, Redis'e yeniden bağlanınca ve sorgu bilinmeyen bir id döndürünce yenileniyor.
- **Neden:**
  - Geometri DB'de kaldığı için bir bölgenin şekli değişince bir sonraki batch yeni şekle göre kontrol ediliyor; doğruluk cache'in tazeliğine bağlı değil.
  - Uçak başına sorguya göre (60 uçak → 60 gidiş-dönüş) yük bağlantı sayısından bağımsız.
  - Smoke testinde yeni bölgedeki giriş olayları, `geofences.changed` mesajından 55 ms önce yakalandı.
- **Alternatif:** Geçici tablo (her batch'te DDL ve ek gidiş-dönüş); `VALUES` listesi (parametre sayısı uçak sayısıyla büyür); geometrileri shapely `STRtree` ile bellekte tutmak (DB'ye hiç gitmez, ama plan PostGIS istiyor ve cache bayatlaması gerçek bir risk olur).

## D-052 — Geofence state machine kuralları

- **Tarih:** 2026-10-05 (Faz 4)
- **Karar:**
  - Durum, (uçak, bölge) çifti başına "içeride ya da değil".
  - Batch'te olmayan uçağın durumu değişmiyor: kaçan bir rapor çıkış sayılmıyor.
  - 60 sn görülmeyen uçak `exit` üretilmeden unutuluyor. Silinen ya da pasifleştirilen bölgenin çiftleri de olaysız atılıyor.
  - Aynı batch'te önce `exit`, sonra `enter` sıralanıyor.
  - Yeniden başlatmada durum, son 24 saatteki olaylardan kuruluyor: hâlâ canlı olan uçaklar için her çiftin son olayı `enter` ise çift içeride sayılıyor.
  - İlk kurulumda zaten içeride olan uçaklar için `enter` üretiliyor.
- **Neden:**
  - Sinyali kaybolan uçak için nerede olduğunu bilmeden "çıktı" demek yanlış bilgi olurdu (ör. LTFM'ye inip transponderini kapatan uçak).
  - Yeniden başlatmada `enter`'ların tekrarlanmaması kabul kriterinin parçası.
  - 24 saat sınırı `DISTINCT ON` taramasını sınırlı tutuyor; uçan bir uçak bir bölgede bu kadar kalmaz.
- **Alternatif:** Zaman aşımında son konumla `exit` yazmak; histerezis/debounce (sınırda gidip gelen uçak için; ihtiyaç görülürse eklenir).

## D-053 — Relay akışı: saniye sınırında flush, snapshot DB'den, önce yaz sonra yayınla

- **Tarih:** 2026-10-05 (Faz 4)
- **Karar:**
  - Relay tek bir asyncio döngüsü: okuyucu batch'leri `LiveState`'e uyguluyor ve geofence kontrolünü yapıyor; ticker her duvar saati saniyesinde `flush` ediyor.
  - Senkron ORM çağrıları `sync_to_async` ile ayrı bir iş parçacığında, her çağrıdan önce `close_old_connections()` ile.
  - Açılışta `LiveState` son 60 saniyedeki `aircraft_latest`'ten tohumlanıyor (pending değil). Consumer'ın snapshot'ı da DB'den okunuyor, relay'in belleğinden değil.
  - Geofence olayı önce `geofence_events`'e yazılıyor, sonra yayınlanıyor.
- **Neden:**
  - Snapshot ile REST aynı kaynaktan okuyor ve consumer süreci relay'e bağımlı olmuyor.
  - Olay mesajındaki `id` REST'te hemen bulunabiliyor.
  - Uzun ömürlü bir süreçte istek döngüsü olmadığı için bozuk bağlantılar elle geri dönüştürülüyor (DB yeniden başlarsa relay toparlanıyor).
- **Alternatif:** Snapshot'ı relay'den Redis'e yazdırmak (ikinci bir doğruluk kaynağı); senkron relay (channel layer async olduğu için her yayında `async_to_sync` gerekirdi).

## D-054 — Testlerde in-memory channel layer

- **Tarih:** 2026-10-05 (Faz 4)
- **Karar:** Testlerde autouse fixture `InMemoryChannelLayer` kullanıyor. Consumer testleri tam ASGI uygulamasına (Origin doğrulayıcı dahil) `WebsocketCommunicator` ile bağlanıyor. Relay testleri gerçek PostGIS'e `transaction=True` ile gidiyor. Async testlerin iş parçacığında kalan DB bağlantısını bir fixture kapatıyor.
- **Neden:** Deterministik ve hızlı; Redis layer'ın kendisi channels-redis'in sorumluluğu. Redis üzerinden uçtan uca yol smoke testte (`make ws`, dev ve prod) doğrulandı.
- **Alternatif:** Testlerde gerçek Redis layer (ayrı prefix ve temizlik gerekirdi).

## D-055 — Frontend sürümleri, yapı ve arayüz dili

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - maplibre-gl 6.12.0 (güncel kararlı; v6 yalnızca ESM, tipleri paketin içinde).
  - Bağımlılık `npm install --package-lock-only` ile ekleniyor, ardından imaj yeniden kuruluyor. Konteynerdeki `node_modules` imajdan gelen root sahipli bir anonim volume.
  - Kod `lib/` (saf, testli), `map/` (katman tanımları, ikon), `hooks/` ve `components/` olarak ayrıldı.
  - Arayüz metinleri İngilizce (kod, README ve API ile aynı dil). Türkçe yalnızca learn ve proje günlüklerinde.
- **Neden:** Saf mantık React'ten ve haritadan bağımsız olunca vitest ile node ortamında test edilebiliyor. Bağımlılıklar host'a kurulmuyor.
- **Alternatif:** react-map-gl gibi bir sarmalayıcı. Learn hedefi gereği MapLibre'nin imperative API'si doğrudan kullanıldı.

## D-056 — Basemap: OpenFreeMap `dark`, style JSON'u uygulama çekiyor, yedek style

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - Basemap `https://tiles.openfreemap.org/styles/dark`. Style JSON'u haritayı oluşturmadan önce `fetch` ile, 5 sn zaman aşımıyla çekiliyor.
  - Ağ hatası, HTTP hatası ya da geçersiz style gelirse satır içi yedek style kullanılıyor: düz arka plan ve demotiles glyph'leri. Arayüzde "Basemap unavailable" notu gösteriliyor.
  - Etiket fontu seçilen style'ın glyph sunucusuna göre belirleniyor (`Noto Sans Regular` / `Open Sans Semibold`).
- **Neden:**
  - Koyu zemin üzerinde renkli veri katmanları öne çıkıyor.
  - MapLibre'ye URL verilirse ve yüklenemezse harita boş kalıyor, yalnızca bir `error` olayı geliyor. Önceden çekince karar haritadan önce verilebiliyor.
  - Yedek style'da il sınırları ve uçaklar yine görünüyor.
- **Alternatif:** `map.on('error')` ile sonradan `setStyle` (eklenen katmanlar yeniden kurulmak zorunda kalırdı); kendi tile sunucusu (kapsam dışı).

## D-057 — Canlı katman: `Map<icao24, Feature>`, 1 sn throttle'lı `setData`, React'e yalnızca sürüm sayacı

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - `LiveStore` snapshot'ta tamamen yenileniyor, delta'da yamanıyor. Uçak başına en yeni `ts` kazanıyor; eşit `ts`'de sonraki mesaj kazanıyor (ICD §6.2).
  - `setData` istemcide de en fazla saniyede bir çağrılıyor (leading + trailing throttle), çünkü snapshot ve delta art arda gelebiliyor.
  - Uçak başına React state yok. Her çizimde bir `version` sayacı artıyor; sayı ve seçili uçağın canlı kaydı bu sayaca bağlı olarak türetiliyor.
- **Neden:** Yüzlerce uçak için React state'i ve render ağacı gereksiz. Haritaya giden tek yol `setData`, React yalnızca paneldeki birkaç değeri çiziyor.
- **Alternatif:** Uçakları React state'inde tutup her mesajda yeniden render etmek; `updateData` ile diff göndermek (MapLibre destekliyor, ama 1 sn'de yüz küsur nokta için tam `setData` yeterince ucuz, learn'de karşılaştırıldı).

## D-058 — Uçak ikonu: canvas'ta üretilen SDF; vurgu için feature-state'li circle katmanı

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - Uçak silueti açılışta 64×64 canvas'a çiziliyor, kaba kuvvet bir signed distance field'e çevriliyor ve `addImage(..., { sdf: true, pixelRatio: 2 })` ile ekleniyor.
  - Renk `icon-color` ile irtifaya göre (`interpolate`), yerdekiler gri, irtifası bilinmeyenler beyaz.
  - Hover ve seçim, uçakların altındaki bir `circle` katmanının opaklığıyla gösteriliyor; bu opaklık `feature-state`'ten okunuyor (`promoteId: "icao24"`).
- **Neden:**
  - Asset hattı gerekmiyor. Gerçek SDF (yalnızca maske değil) her boyutta keskin kenar ve halo veriyor.
  - `feature-state` yalnızca paint özelliklerini sürebiliyor, `icon-size` gibi layout özelliklerini süremiyor.
- **Alternatif:** İrtifa bandı başına ayrı renkli PNG'ler (renk geçişi kaba olurdu); seçim için ayrı bir source (her seçimde `setData`).

## D-059 — Subscribe bbox: viewport + %10 pay, 4 ondalık, aynısı tekrar gönderilmiyor

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - Viewport sınırları her yönde genişliğin/yüksekliğin %10'u kadar genişletiliyor, geçerli aralığa kırpılıyor ve 4 ondalığa yuvarlanıyor.
  - Hesap yalnızca `moveend`'de yapılıyor. Değer `useSyncExternalStore` ile React'e bağlanıyor; değişmeyen bbox aynı dizi nesnesi olarak dönüyor.
- **Neden:**
  - Küçük kaydırmalarda kenardaki uçaklar zaten yüklü oluyor.
  - Yuvarlama sayesinde kamera titreşimi yeni bir subscribe üretmiyor.
  - Harita React dışında bir "store"; `useSyncExternalStore` bunun resmi bağlantı noktası.
- **Alternatif:** `move` olayında (her karede) subscribe göndermek; paysız tam viewport.

## D-060 — WebSocket yeniden bağlanma: full jitter backoff, snapshot'ta sıfırlama, watchdog

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - Gecikme `[0,5 sn, min(30 sn, 0,5·2ⁿ)]` aralığında rastgele.
  - Deneme sayacı bağlantı açılınca değil, ilk snapshot gelince sıfırlanıyor.
  - 45 sn hiç frame gelmezse (üç kaçırılmış heartbeat) soket kapatılıp yeniden bağlanılıyor.
  - Tarayıcının `online` olayı bekleyen denemeyi hemen başlatıyor.
  - Durumlar: `connecting`, `live`, `waiting` (geri sayımla).
- **Neden:**
  - Jitter, sunucu yeniden başladığında bütün sekmelerin aynı anda bağlanmasını engelliyor.
  - "Kabul et ve hemen kapat" döngüsü de geri çekiliyor.
  - Ölü bir TCP bağlantısı `close` olayı hiç üretmeyebiliyor.
- **Alternatif:** Sabit aralıklı yeniden deneme; jittersiz üstel backoff.

## D-061 — Responsive düzen: 640 px altında iki durumlu bottom sheet

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - Masaüstünde sağda 340 px yüzen panel. 640 px altında aynı bileşen alttan açılan panel oluyor: kapalıyken yalnızca başlık (durum ve uçak sayısı), açıkken en fazla ekranın %70'i.
  - Bir uçak seçilince panel açılıyor. Sürükleme yok, başlığa dokunmak aç/kapa yapıyor.
  - Hangi düzenin kullanılacağına CSS karar veriyor; JS'te ekran genişliği okunmuyor.
- **Neden:** Tek bileşen, tek DOM. 375 px'de harita kullanılabilir alanın çoğunu koruyor.
- **Alternatif:** Sürüklenebilir çok durumlu sheet (jest kodu ve erişilebilirlik yükü; Faz 8'e bırakılabilir).

## D-062 — Bundle bölme, dev'de `window.__map`, tarayıcı smoke testi Playwright konteynerinde

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:**
  - maplibre-gl ayrı bir chunk (yaklaşık 279 KB gzip), uygulama kodu ayrı (yaklaşık 75 KB gzip).
  - Dev sunucusunda harita `window.__map` olarak açılıyor (konsoldan inceleme ve smoke test için; prod derlemesinde yok).
  - Tarayıcı kabul testi `make ui-smoke`: resmi Playwright imajı `--network host` ile `localhost:8800`'e bağlanıyor. WebSocket frame'lerini kaydediyor, ekran görüntülerini `data/ui-smoke/`'a yazıyor.
- **Neden:**
  - maplibre uygulama kodundan çok daha seyrek değişiyor; ayrı chunk uzun süre önbellekte kalıyor.
  - Kabul kriteri (yalnızca görünen bölgenin verisi geliyor) frame'lerden ölçülebiliyor.
  - Host'a tarayıcı ya da Node kurulmuyor.
- **Alternatif:** vitest ile jsdom üzerinde bileşen testi (WebGL yok, harita test edilemez); host'ta elle tarayıcı kontrolü (tekrarlanamaz).

## D-063 — Channel layer'da `socket_timeout: 15` (redis-py 8 ile channels-redis uyumsuzluğu)

- **Tarih:** 2026-10-05 (Faz 5, Faz 4 hatası)
- **Karar:**
  - `CHANNEL_LAYERS` host'u `{"address": REDIS_URL, "socket_timeout": 15}`.
  - Bir test, socket zaman aşımının channels-redis'in `brpop_timeout` değerinden (5 sn) büyük kaldığını doğruluyor.
  - Consumer'ın sender'ı gönderim sırasında istemci koparsa (`ClientDisconnected`, bir `OSError`) ERROR yerine debug logu yazıyor.
- **Neden:**
  - redis-py 8'de varsayılan `socket_timeout` 5 sn oldu. channels-redis kanalda 5 sn'lik `BZPOPMIN` ile bekliyor; istemci okuması, Redis'in boş yanıtıyla aynı anda zaman aşımına düşüyordu.
  - Sonuç: kanalına 5 sn mesaj gelmeyen her consumer `TimeoutError` ile kapanıyordu. Faz 4'te deltalar 2 sn'de bir aktığı için görünmedi; haritası henüz yüklenmemiş (subscribe göndermemiş) bir tarayıcı sekmesi ortaya çıkardı.
- **Alternatif:** redis-py'yi 7.x'e sabitlemek (eski sürüme bağlanmak); `socket_timeout: None` (ölü bir Redis hiç fark edilmezdi).

## D-064 — maplibre worker'ı Vite paketliyor (`?worker&url` + `setWorkerUrl`)

- **Tarih:** 2026-10-05 (Faz 5)
- **Karar:** `src/map/worker.ts`, `maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url` ile worker'ı import ediyor ve URL'i harita oluşturulmadan önce `setWorkerUrl` ile veriyor. Worker formatı `es`.
- **Neden:**
  - maplibre-gl 6, worker URL'ini çalışma anında kendi modül URL'inden türetiyor; Vite bunu statik olarak göremiyor.
  - Prod derlemesinde worker dosyası hiç üretilmiyordu. Dev'de de dep pre-bundling ana dosyayı worker'ın yanından taşıdığı için 404 alınıyordu.
  - Worker paylaşılan bir chunk'tan import yaptığı için dosyayı olduğu gibi kopyalamak yetmiyor; Vite worker'ı bağımlılıklarıyla tek dosyada paketliyor. Dev ve prod aynı yolu kullanıyor.
- **Alternatif:** `optimizeDeps.exclude` (yalnızca dev'i düzeltiyordu); worker'ı `public/`'e kopyalamak (sürüm yükseltmede elle güncellenmesi gerekirdi).

## D-065 — Geofence çizimi: terra-draw 1.36.0 + MapLibre adapter 1.4.1

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - `terra-draw` 1.36.0 ve `terra-draw-maplibre-gl-adapter` 1.4.1 (peer: maplibre-gl ≥ 4). Yalnızca polygon modu; kendini kesen halka çizim sırasında `ValidateNotSelfIntersecting` ile reddediliyor.
  - Adapter, style yüklendikten sonra kuruluyor (kendi kaynak ve katmanlarını ekliyor). Halka kapanınca mod `static`'e geçiyor; şekil, kaydedilene ya da vazgeçilene kadar ekranda kalıyor.
  - Halkayı kapatan tıklama terra-draw'ın `finish` olayından sonra MapLibre'nin `click`'ine de ulaşıyordu ve altındaki uçağı seçiyordu. `finish`'te bir bayrak kalkıyor, `setTimeout(0)` ile iniyor; çizim sürerken ve bu tıklamada uçak seçimi yapılmıyor.
  - Paket tembel yüklenmiyor: `index` chunk'ı ~345 kB (sıkıştırılmamış). Bunun ~270 kB'ı terra-draw; gzip'le ~50 kB. maplibre ayrı chunk'ta kalıyor.
- **Neden:** Plan terra-draw'ı adıyla istiyor. Çerçeveden bağımsız, MapLibre 6 ile çalışan güncel bir adapter'ı var; mapbox-gl-draw'ın MapLibre uyumluluğu yamalarla sağlanıyor.
- **Alternatif:** `@mapbox/mapbox-gl-draw` (resmi olarak Mapbox için); terra-draw'ı "Draw a zone" tıklanınca dinamik `import()` ile yüklemek (ilk yüklemede ~270 kB tasarruf; Faz 8'de bundle bütçesine bakılırken değerlendirilebilir).

## D-066 — Tüm uçaklara 2 dakikalık kuyruk: istemci tarafında, varsayılan açık

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - Kuyruklar sunucudan istenmiyor; istemci gördüğü fix'lerden üretiyor (`Tails`, uçak başına son 120 sn). Canlıda 1 sn'lik redraw ile aynı anda `tails` kaynağına yazılıyor; geçmiş modunda zaman çizelgesinden (`tailsAt`) hesaplanıyor.
  - Çizgi rengi uçak ikonuyla aynı irtifa ifadesi, opaklık 0,45. "Trails (2 min)" katman anahtarıyla kapatılabiliyor.
- **Neden:**
  - Ölçüm (headless Chromium, yazılımsal WebGL/SwiftShader, `setData` → `idle` medyanı): 60 uçak × 60 nokta ~200 ms, 300 × 60 ~120 ms, 1000 × 60 ~240 ms. Bu sayılar ilk ölçümün ısınma maliyetini ve canlı redraw'larla çakışmayı da içeriyor, gürültülü. Gerçek GPU'da daha hızlı; en kötü durumda bile 1 sn'lik redraw aralığının altında.
  - Synthetic modda ~60, OpenSky'da Marmara için birkaç yüz uçak bekleniyor.
  - Ek istek ve sunucu yükü yok. Sayfa açıldıktan sonra kuyruk 2 dakikada doluyor; bu kabul edilebilir.
- **Alternatif:** Yalnızca seçili uçağa iz (kuyruksuz); kuyrukları REST'ten toplu çekmek (her bbox değişiminde ağır bir sorgu).

## D-067 — Seçili uçağın izi: REST'ten 30 dakika + canlı uzatma

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - Seçimde `GET /api/aircraft/{icao24}/track` (varsayılan son 30 dk) çekiliyor. Sonra gelen her canlı fix, izin `end_ts`'inden yeniyse çizginin sonuna ekleniyor (`extendTrack`; değişiklik yoksa aynı nesne döner, `setData` atlanır).
  - İstek sürerken gelen canlı fix kaybolmuyor: yanıt geldiğinde son canlı kayıt bir effect event ile okunup ekleniyor.
  - İz React state'inde değil, bir ref'te tutuluyor ve doğrudan `track` kaynağına yazılıyor. Geçmiş modunda aynı kaynağı oynatıcı dolduruyor (pencere başından o ana kadarki yol).
- **Neden:** İz yalnızca haritada çiziliyor; React'in render etmesi gereken bir şey değil. REST'i periyodik tekrar çekmek yerine canlı akışla uzatmak hem ucuz hem gecikmesiz.
- **Alternatif:** İzi her 15 sn'de yeniden çekmek.

## D-068 — Playback mimarisi: tek REST isteği, istemcide saat

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - Geçmiş penceresi (15 dk – 2 saat, bitiş zamanı seçilebilir; varsayılan "son 1 saat") tek `GET /api/playback` isteğiyle çekiliyor.
  - Bucket pencereden hesaplanıyor: ~360 kare hedefi, 5 sn'nin katı (15–30 dk → 5 sn, 1 saat → 10 sn, 2 saat → 20 sn). 1 saatlik synthetic pencere ~21.600 konum ediyor.
  - Kareler uçak başına zaman sıralı fix listesine (`buildTimeline`) çevriliyor.
  - Oynatma `requestAnimationFrame` döngüsüyle ilerliyor: simüle zaman = gerçek geçen süre × hız (1×, 10×, 60×; varsayılan 10×), pencere sonunda duruyor. Sondayken play'e basılırsa baştan başlıyor.
  - Haritaya en fazla 20 çizim/sn yapılıyor. React'e saat 4 kez/sn bildiriliyor (kaydırıcı, saat, detay paneli).
- **Neden:**
  - Pencere en fazla 2 saat ve gzip'li; tek istek sonrası kaydırma, geri sarma ve hız değişimi ağ beklemeden oluyor.
  - Canlıdaki "≤ 1/sn setData" kuralı geçmiş modunda akıcılığı öldürürdü. 20/sn, geojson-vt'nin her `setData`'da yeniden tile'laması ile göz için akıcılık arasında bir denge.
- **Alternatif:** Sunucunun kareleri WebSocket'ten belirli hızda itmesi (sunucuda oturum başına saat; geri sarma ve hız değişimi için protokol gerekirdi); sayfalı ya da akışlı (NDJSON) çekme (2 saatlik sınırda gereksiz).

## D-069 — İnterpolasyon kuralları

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - Uçağın kendi fix zamanları (`ts`) arasında lon/lat lineer interpolasyonla hesaplanıyor.
  - Heading kısa yaydan dönüyor (350° → 10° geçişi 0°'dan geçer). İrtifa ve hız lineer. İki taraftan biri `null` ise önceki fix'in değeri kullanılıyor (değer uydurulmuyor).
  - İki fix arası 3 bucket'tan uzunsa arası köprülenmiyor. Uçak son fix'inden sonra bir bucket boyunca yerinde tutuluyor, sonra gizleniyor. İlk fix'inden önce görünmüyor.
- **Neden:**
  - Bucket 5–20 sn; 250 m/sn'deki bir uçak için ardışık fix'ler 1,25–5 km arayla geliyor. Bu mesafede düz lon/lat çizgisi ile büyük daire arasındaki sapma 1 metrenin altında; ikon boyutunun çok altında.
  - Büyük boşlukları köprülemek, olmayan bir düz uçuş icat ederdi (ör. inişten sonra başka pistten kalkış).
- **Alternatif:** Büyük daire (slerp) interpolasyonu; boşluklarda da interpolasyon.

## D-070 — Geçmiş modunda WebSocket kapanıyor

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - `useLiveSocket` bir `enabled` bayrağı alıyor; `false` olunca soket kapanıyor ve durum `paused` oluyor (rozet "History"). Canlıya dönünce bağlantı sıfırdan kuruluyor ve gelen snapshot store'u dolduruyor.
  - Mod değişiminde canlı store ve kuyruklar temizleniyor; oynatıcı da çıkarken `aircraft`, `tails` ve `track` kaynaklarını boşaltıyor.
- **Neden:** Plan aboneliğin askıya alınmasını istiyor. Açık bir soket boşuna delta taşır ve iki üretici aynı kaynağa yazmaya çalışırdı. Geri dönüşteki snapshot zaten tam durum veriyor.
- **Alternatif:** Soketi açık tutup mesajları yok saymak; sunucuya "unsubscribe" mesajı eklemek (ICD değişikliği gerektirirdi).

## D-071 — Geofence listesi ve doğrulama

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - `geofences` kaynağı artık bir URL değil, `useGeofences`'in çektiği veri. Tüm bölgeler gösteriliyor; pasifler soluk ve gri. `promoteId: 'id'`.
  - Kendi POST, PATCH ve DELETE işlemlerimizden sonra liste yeniden çekiliyor. Relay değişikliği `geofences.changed` ile kendisi öğreniyor; tarayıcıya ayrıca bir WebSocket mesajı gönderilmiyor.
  - Çizilen halka kaydetmeden önce istemcide kontrol ediliyor: en az 3 farklı köşe, en fazla 1000 köşe, alan 0,25–20.000 km² (küresel alan formülü), bölgeyle kesişim. Sunucunun shapely doğrulaması otorite olarak kalıyor; hatası formda gösteriliyor.
  - Silme onay istiyor; bölgenin olayları da siliniyor (`on_delete=CASCADE`).
- **Neden:**
  - Tek kullanıcılı yerel uygulama. Başka bir sekmenin yaptığı değişikliği anında görmek için ICD'ye yeni bir mesaj tipi eklemeye değmez.
  - İstemci ön kontrolü kullanıcıya anında geri bildirim veriyor ve gereksiz 400'leri önlüyor.
- **Alternatif:** `geofences_changed` WebSocket mesajı; sunucu kontrolüne tek başına güvenmek.

## D-072 — Olay bildirimleri: toast, liste, yanıp sönme

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:**
  - Canlı `geofence_event` üç şey yapıyor:
    - Toast: üstte, en fazla 4 tane, 6 sn sonra kayboluyor. Tıklanınca haritayı uçağa götürüp seçiyor.
    - Olay listesine ekleniyor.
    - Bölgeyi yanıp söndürüyor: `feature-state flash`, 350 ms aralıkla 3 kez. Yalnızca paint değişiyor, veri değişmiyor.
  - Yeni kaydedilen bir bölgenin içinde zaten bulunan uçaklar için hemen `enter` geliyor (D-052'nin "ilk kurulum" kuralı). `make ui-smoke` bu ilk toast'lardan sonra, sınırı gerçekten geçen bir uçağın toast'ını ayrıca bekliyor ve konumdan tarayıcıya gecikmeyi WebSocket frame'lerinden ölçüyor.
- **Neden:** Feature-state, kaynağı yeniden yüklemeden tek bir poligonun stilini değiştirmenin yolu. Toast sınırı, olay fırtınasında ekranın dolmasını önlüyor; tamamı listede kalıyor.
- **Alternatif:** Tarayıcı bildirimleri (Notification API; izin istemi gerektirir); yanıp sönmeyi CSS animasyonlu bir DOM marker ile yapmak.

## D-073 — nginx JS ve CSS'i de sıkıştırıyor

- **Tarih:** 2026-10-05 (Faz 6)
- **Karar:** `gzip_types` listesine `text/javascript`, `application/javascript`, `text/css` ve `image/svg+xml` eklendi.
- **Neden:** Bundle boyutuna bakarken JS'in sıkıştırılmadan gittiği görüldü. Faz 3'te liste yalnızca JSON için yazılmıştı. Dev'de terra-draw modülü 973 kB'tan 256 kB'a iniyor.
- **Alternatif:** Derleme sırasında önceden sıkıştırılmış `.gz` dosyaları üretip `gzip_static` (Faz 8'de prod imajı için değerlendirilebilir).

## D-074 — DEM araç zinciri: kendi küçük GDAL imajımız (Debian), `tools` profili

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** `make dem`, `scripts/dem/Dockerfile` ile kurulan `hezarfen-gdal` imajında çalışıyor (Debian trixie `gdal-bin` 3.10.3, `python3-gdal`, `python3-numpy`). Compose'ta `gdal` servisi `profiles: ["tools"]` ile tanımlı; `make up` onu başlatmıyor. Sentetik yedek de bu imajda numpy + GDAL Python bağlamalarıyla üretiliyor (planda rasterio yazıyordu).
- **Neden:** Resmî `ghcr.io/osgeo/gdal` imajı bu makinede "denied" ile çekilemedi (Docker Desktop'taki eski bir ghcr girişi; anonim çekme ayrıca çok yavaştı). Sahibin makinesinde de aynı sorun çıkabilirdi. docker.io + Debian paketleri hem çekilebilir hem sürümü sabit. Backend imajına `python3-gdal` eklemek olmazdı: backend Python 3.14 (python:slim), Debian'ın bağlamaları sistem Python'ı içindir.
- **Alternatif:** `ghcr.io/osgeo/gdal:ubuntu-small-3.13.3` (daha yeni GDAL, ama ghcr erişimine bağımlı); backend imajında pip ile GDAL derlemek (yavaş, ağır).

## D-075 — DEM verisi: Copernicus GLO-90, deniz = 0, kısmi indirme hata

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** Planlanan desen değişmemiş (`copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_N41_00_E028_00_DEM/...tif`). Bbox için 3×6 = 18 karo iniyor (~70 MB, `data/dem/src`'de önbellek). Kaynak karolarda nodata tanımlı değil, deniz 0. 404 "tamamı deniz olan karo" demek ve kabul ediliyor (mozaikte o alan 0 olur). Diğer her indirme hatası betiği durduruyor: aksi halde eksik bir kara karosu sessizce "deniz" olurdu. Hiç karo inmezse `DEM_SOURCE=auto` sentetik yüzeye düşüyor ve `meta.json` `"source": "synthetic"` diyor; UI ve README bunu belirtiyor.
- **Neden:** Yükseklik verisinde sessiz yanlış, açık hatadan kötüdür.
- **Alternatif:** GLO-30 (30 m; 9 kat veri, zoom 11 karoları için gereksiz); SRTM (daha eski, 60°K sınırı, boşluklu).

## D-076 — İki çıktı, iki projeksiyon ve resampling seçimleri

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** (1) Analiz için COG **EPSG:4326'da, kaynağın kendi ızgarasında** kırpılıyor (`gdal_translate -projwin`): yeniden örnekleme yok, her değer orijinal bir ölçüm. DEFLATE + float predictor, 512 blok, AVERAGE overview'lar, nodata −32767. (2) Hillshade için mozaik **EPSG:3857'ye bilinear** ile çevriliyor.
- **Neden:** Örnekleme endpoint'i ham değer istiyor, karo üretimi ise Web Mercator. Yükseklik sürekli bir büyüklük: nearest merdiven basamakları bırakır ve hillshade bunları çizgi çizgi gösterir; cubic kıyı ve uçurumlarda taşma (overshoot) yapabilir. Bilinear ikisinin ortası.
- **Alternatif:** Tek bir 3857 rasterından örnekleme (ikinci bir resampling hatası eklerdi); cubic.

## D-077 — Hillshade: Mercator z-factor ve saydam RGBA karolar

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** `gdaldem hillshade -az 315 -alt 45 -z 1.32`; z = 1/cos(bölgenin orta enlemi 40.75°). Gri çıktı `shade_rgba.py` ile siyah (gölge) / beyaz (ışık) + alfa'ya çevriliyor; düz zemin (1 + 254·sin 45° ≈ 181) ve deniz saydam. Zoom 6–11, `gdal2tiles --xyz -r average`, 900 karo (~54 MB). MapLibre'de `raster` katmanı, il sınırlarının altında, varsayılan açık, opaklık 0.6 (kaydırıcı 0.1–1).
- **Neden:** 3857'de yatay mesafeler 1/cos(φ) kadar şişer; z düzeltilmezse eğimler gerçeğinden düz görünür. Gri hillshade koyu altlığı ve tüm denizi griye boyardı; alfa ile yalnızca rölyef görünüyor. Zoom 11 (~58 m/piksel) 90 m'lik veri için yeterli; üstünde MapLibre overzoom yapıyor.
- **Alternatif:** MapLibre'nin yerleşik `hillshade` katmanı + terrain-RGB karoları (planın istediği GDAL pipeline'ını atlardı); multidirectional hillshade.

## D-078 — Yükseklik örnekleme: bilinear, nodata'da en yakın piksel, tek açık dataset

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** `/api/terrain/elevation` dört komşu piksel merkezinin bilinear ortalamasını döndürüyor (0.1 m). Komşulardan biri nodata ise en yakın piksel kullanılıyor; o da nodata ise `null`. Raster kenarı ile kenar piksel merkezleri arasında kalan nokta kenar piksele kenetleniyor. DEM kapsamı dışı → 400 `out_of_region`; DEM yoksa → 503 `terrain_unavailable` ("run `make dem`"). rasterio dataset'i süreç başına bir kez açılıyor ve bir kilitle korunuyor (dataset thread-safe değil, sync view'lar thread pool'da). Her istekte tek bir `stat` ile dosyanın inode/mtime'ı kontrol ediliyor; `make dem` dosyayı değiştirdiyse yeniden açılıyor. Matematik saf fonksiyonlarda (`terrain/sampling.py`, TDD).
- **Neden:** Nearest 90 m'lik basamaklar verir. −32767'yi bir ortalamaya katmak saçma sonuç üretir. Restart gerektirmeyen yeniden açma, eski inode'u okuyan backend tuzağını kapatıyor. Doğrulama: Uludağ 2506 m (gerçek 2543; 90 m'de zirve düzleşir), LTBY 786,5 m (OurAirports 788,8).
- **Alternatif:** PostGIS raster (`raster2pgsql` + `ST_Value`): veritabanını büyütür, Faz 7'nin COG/rasterio dersini atlar; `dataset.sample()` (nearest).

## D-079 — AGL tanımı ve "alçak uçuş" kuralı

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** AGL = `geo_alt − arazi` (yoksa `baro_alt − arazi`, "(baro)" etiketiyle). Geoid düzeltmesi yapılmıyor. "Low flight" rozeti: havada, AGL < 300 m hiçbir `airport_buffer` bölgesinin içinde değil (pasif olanlar dahil: havalimanı yakınlığı bir coğrafya bilgisi, uyarı ayarı değil) ve REST'in verdiği en yakın havalimanına 10 km'den uzak (yalnızca canlı modda; REST şimdiki konumu anlatır). 10 km kuralı tarayıcıda görülen bir yanlış pozitiften sonra eklendi: bölgesi olmayan Yenişehir'e yaklaşan bir uçak rozet alıyordu. Yalnızca seçili uçağın detayında hesaplanıyor; yükseklik ~100 m'lik hücre anahtarıyla (0.001°) önbellekleniyor, hücre değişince eski istek iptal ediliyor. Geçmiş modunda da oynatılan konum için çalışıyor.
- **Neden:** ADS-B geometrik irtifa genelde WGS84 elipsoidine göre, GLO-90 EGM2008 geoidine göre; bölgede fark ~36–40 m. Ayrıca GLO-90 bir DSM (bina ve ağaç tepesi dahil). 300 m eşiğinde bu belirsizlik kabul edilebilir; learn dosyası ve README açıkça yazıyor. Tüm uçaklar için AGL sunucu tarafında, relay veya ingest'te hesaplanmalıydı; bu fazın kapsamını aşıyor.
- **Alternatif:** PROJ geoid ızgarasıyla (egm08) düzeltme; AGL'yi relay'de her uçak için hesaplayıp haritada rozetlemek (Faz 8 sonrası fikir).

## D-080 — Hillshade katmanı `meta.json` varsa ekleniyor

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** Frontend `/tiles/hillshade/meta.json`'u okuyor. Dosya yoksa katman eklenmiyor ve panelde "run `make dem`" yazıyor. Varsa raster kaynağı `bounds`, `minzoom` ve `maxzoom` ile ekleniyor; `meta.json` nginx'te `no-cache`, karolar 7 gün önbellekli. Karo URL'si `location.origin` ile kuruluyor, `new URL()` ile değil.
- **Neden:** `make dem` çalıştırılmamış bir kurulumda harita yüzlerce 404 istemesin. Hata ayıklarken bulunan bir tuzak: `new URL()` `{z}` yer tutucularını `%7Bz%7D`'ye kodluyor; tüm karo istekleri 404 alıyordu. Aynı koşuda "canlıya dönüş" kontrolü de başarısız oldu; URL düzelince ikisi birden geçti.
- **Alternatif:** Katmanı her zaman eklemek ve 404'leri yok saymak.

## D-081 — Hillshade görünürlüğü katman gruplarının dışında

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** Hillshade, `LAYER_GROUPS` yerine kendi hook'unda (`useHillshade`) yönetiliyor: görünürlük + opaklık; panelde ayrı bir "Terrain" bölümü var.
- **Neden:** Katman stil yüklendikten sonra, `meta.json` geldiğinde eşzamansız ekleniyor. Görünürlük efekti katmandan önce çalışıp `setLayoutProperty` ile hata verirdi.
- **Alternatif:** `setGroupVisibility`'ye "katman yoksa atla" koruması eklemek (o zaman sonradan eklenen katman görünürlüğü kaçırırdı).

## D-082 — nginx yapılandırma değişikliği için restart

- **Tarih:** 2026-10-05 (Faz 7)
- **Karar:** `nginx/nginx.conf` tek dosya olarak bağlı. Dosyayı yeni bir inode ile yazan editörler veya araçlar sonrası `nginx -s reload` yetmiyor; `docker compose restart nginx` gerekiyor.
- **Neden:** Tek dosya bind mount'u container başlarken inode'a bağlanıyor. Bu fazda `meta.json` kuralı reload ile gelmedi.
- **Alternatif:** Klasör bağlamak (`./nginx:/etc/nginx/conf.d`); Faz 8'de değerlendirilebilir.

## D-083 — Ops paneli kimlik doğrulamasız, CSRF açık

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `/ops/` herkese açık; REST API ile aynı politika (yerel, tek kullanıcılı kurulum). Ama ops POST'ları Django'nun CSRF kontrolünden geçiyor: sayfa token'ı `<body hx-headers='{"X-CSRFToken": …}'>` ile her HTMX isteğine ekliyor; token'sız POST 403.
- **Neden:** Panel API'nin zaten verdiği yetkilerin ötesine geçmiyor: bölge açıp kapama `PATCH /api/geofences/` ile aynı, retention düğmesi yalnızca politika gereği zaten silinecek veriyi siliyor. CSRF ise farklı bir risk: başka bir sitenin, kullanıcının tarayıcısı üzerinden bu panele form göndermesini engelliyor ve maliyeti tek satır. (DRF tarafında kimlik doğrulama sınıfı olmadığı için CSRF orada devre dışı; D-039.)
- **Alternatif:** `staff_member_required` ile admin oturumu istemek. Gerçek bir kurulumda ilk yapılacak iş; demo ve smoke testleri için sürtünme ekliyordu.

## D-084 — Retention zamanlaması: ayrı `maintenance` servisi, basit döngü

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `manage.py maintenance` ayrı bir compose servisi olarak (backend imajı) çalışıyor. `ops/schedule.py::run_every` başlangıçtan 30 sn sonra ve sonra `RETENTION_INTERVAL_SECONDS`'ta (varsayılan 3600) bir `prune_positions` çalıştırıyor. Bekleme `threading.Event.wait(timeout)` ile: SIGTERM bir saat beklemeden döngüyü bitiriyor. Hatalı bir tur loglanıyor, döngü sürüyor. Healthcheck: her turdan sonra dokunulan heartbeat dosyası, `maintenance --check` yaşını aralığa göre değerlendiriyor.
- **Neden:** Plan "relay ya da ayrı görev" diyordu. Relay tüm ORM çağrılarını tek bir thread'de (`sync_to_async(thread_sensitive=True)`) çalıştırıyor; çok saniyelik bir DELETE o sırada geofence kontrollerini bekletirdi. Ayrı servis ~60 MB bellek, karşılığında izolasyon ve ayrı log.
- **Alternatif:** cron container'ı (bir araç ve log yönlendirmesi daha), Celery beat (broker, worker, beat: üç parça bir iş için), `pg_cron` (PostGIS imajına eklenti kurmak gerekirdi), relay içinde asyncio görevi (yukarıdaki thread sorunu).

## D-085 — Retention toplu (batch) siliyor

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `DELETE FROM positions WHERE id IN (SELECT id FROM positions WHERE ts < %s LIMIT 20000)` döngüsü; her parti kendi transaction'ı (autocommit). Sonuç `PruneResult(deleted, days, cutoff, seconds, batches)`. Komut, servis ve ops düğmesi aynı fonksiyonu kullanıyor.
- **Neden:** Tek bir `DELETE … WHERE ts < cutoff` bir günlük veride milyonlarca satırı tek transaction'da siler: kilitler ve WAL boyunca tutulur, replikasyon ve autovacuum geride kalır. Postgres'te `DELETE … LIMIT` yok, alt sorgu bu yüzden. İç SELECT `ts` üzerindeki BRIN index'iyle eski blokları buluyor. Önceki `QuerySet.delete()` tek ifadeydi.
- **Alternatif:** `positions`'ı zamana göre bölümlemek (partitioning) ve eski bölümü `DROP` etmek: silme anlık, VACUUM yok. Doğru uzun vadeli çözüm, ama migration ve ingest'in insert yolunu değiştiriyor; `learn/99`'da "sonraki adım" olarak yazıldı.

## D-086 — Ops düğmeleri "toggle" değil, açık hedef durum gönderiyor

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `POST /ops/geofences/{id}/active` gövdesinde `active=true|false` zorunlu (başka değer 400). Durum zaten istenen gibiyse hiçbir şey yazılmıyor ve `geofences.changed` yayınlanmıyor. Dönen `<tr>` bir sonraki düğmenin hedefini taşıyor.
- **Neden:** Toggle idempotent değil: çift tık, tekrar denenen istek ya da eski sekmeden gelen tık durumu geri çevirir. Açık hedef durumla aynı isteği iki kez göndermek zararsız. HTMX'te bu `hx-vals='{"active": "false"}'` kadar ucuz.
- **Alternatif:** `POST …/toggle`; daha kısa ama yarış koşullarına açık.

## D-087 — HTMX 2.0.11 vendor'landı; polling kuralları

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `htmx.min.js` 2.0.11 (Zero-Clause BSD, 52 kB) `backend/ops/static/ops/` altında repoda; Django static ve WhiteNoise sunuyor. Kendini yenileyen bölümler `hx-trigger="every 5s [document.visibilityState === 'visible']"` ve `hx-swap="outerHTML"`; parça şablonu polling yapan elemanın kendisi, yani tetikleyiciyi her yanıtta yeniden taşıyor. Tam sayfa da aynı parça şablonlarını `{% include %}` ediyor. Başarısız isteklerde (`htmx:sendError`, `htmx:responseError`) üstte bir uyarı bandı çıkıyor, sonraki başarılı swap'ta kayboluyor.
- **Neden:** CDN yok: panel çevrimdışı da çalışmalı ve CSP'de dış kaynak gerekmesin. 4.0 hâlâ `next` etiketinde; kararlı sürüm 2.0.11. Görünürlük filtresi arka plan sekmelerinin her 5 sn'de sorgu atmasını engelliyor. HTMX hata yanıtında swap yapmıyor; uyarı olmadan bayat sayılar güncel gibi görünürdü.
- **Alternatif:** SSE ya da WebSocket ile itme (HTMX'in `sse` uzantısı). 5 sn'lik bir operasyon tablosu için polling daha basit ve durumsuz.

## D-088 — Pozisyon tablosu özeti tam tarama yapmadan

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** Retention bölümündeki satır sayısı `pg_class.reltuples` tahmini (ANALYZE'dan; hiç analiz edilmediyse "not analysed yet"). En eski satır `ORDER BY id LIMIT 1` ile birincil anahtardan.
- **Neden:** On milyonlarca satırda `COUNT(*)` ve `MIN(ts)` saniyeler sürer; BRIN index'i MIN sorusuna cevap veremez (blok aralığı özeti, sıralı yapı değil). Tablo yalnızca ekleme alıyor; en küçük id en eski ekleme.
- **Alternatif:** `ts` üzerinde B-tree index (MIN anlık olurdu ama sıcak insert yoluna ikinci bir index yükü).

## D-089 — Ingest `/metrics`'e `daily_credits` (ICD 1.6)

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** IF-8'e `daily_credits` eklendi: live modda yapılandırılmış günlük bütçe, diğer modlarda `null`. Ops paneli kalan krediyi yüzde olarak gösteriyor.
- **Neden:** Bütçe (4000 / 400 / `OPENSKY_DAILY_CREDITS`) ingest'in kimlik bilgisi olup olmamasına bağlı; backend bunu bilmiyor. Bilgiyi bilen servisin yayınlaması doğru. Eklemeli değişiklik, sürüm kırılmıyor.
- **Alternatif:** Backend'de aynı kuralı yeniden kurmak (iki yerde aynı mantık, ayrışma riski).

## D-090 — CI tamamlandı: entegrasyon ve yığın job'ları

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `integration` job'ı: PostGIS + Redis servisleri, Django migrate, ardından Go store/publish testleri; `--- SKIP` görülürse job başarısız (D-034 kapandı). `frontend` job'ına `npm run build`. Eski `images` job'ı `stack` oldu: tüm imajları (`--profile tools` dahil) build ediyor, `make up-prod`, `make seed REFERENCE_OFFLINE=1`, `make smoke`; hata olursa servis logları. Workflow yerelde `make lint-ci` (actionlint 1.7.12 + shellcheck, container'da) ile doğrulandı; her job'ın komutları yerelde container'larda çalıştırıldı.
- **Neden:** Atlanan bir test geçen bir test gibi görünür; SKIP kontrolü bunu yakalıyor. Yığın job'ı kullanıcının yaptığını tekrarlıyor: "build oluyor" ile "ayağa kalkıp çalışıyor" ayrı şeyler.
- **Alternatif:** `act` ile workflow'u yerelde koşturmak: Docker soketi ve büyük runner imajı ister, servis container'ları desteği kısmi; GitHub'a geçince ilk gerçek koşu zaten görülecek. UI smoke'u (Playwright) CI'a eklemek: 2 GB imaj ve zamanlamaya bağlı adımlar (gerçek bir sınır geçişi beklemek) CI'da kırılgan olurdu.

## D-091 — nginx klasör olarak bağlandı; `absolute_redirect off`

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `./nginx:/etc/nginx/conf.d:ro` (D-082'nin çözümü; `sed -i` ile inode değiştiren düzenlemeden sonra `nginx -s reload` yeni ayarı aldı). `/ops` → `/ops/` yönlendirmesi nginx'te; `absolute_redirect off` ile `Location: /ops/`.
- **Neden:** Klasör bağlamada container dizini izliyor, dosyanın yeni inode'u görünüyor. `/ops` eğik çizgisiz gelince `^/(api|admin|ops|static)/` eşleşmiyor ve SPA'ya düşüyordu. nginx mutlak yönlendirmede kendi portunu (80) yazar; tarayıcı 8800'den geliyor.
- **Alternatif:** Konum regex'ini `(/|$)` yapmak ve yönlendirmeyi Django'nun `APPEND_SLASH`'ine bırakmak (bir istek fazladan backend'e gider).

## D-092 — terra-draw tembel yükleniyor

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `useDrawPolygon` terra-draw'ı ve MapLibre adaptörünü harita hazır olunca dinamik `import()` ile yüklüyor; yüklenene kadar "Draw a zone" düğmesi pasif. Ana paket 357 → 262 kB (gzip 107 → 84 kB); terra-draw kendi parçasında (46 kB gzip).
- **Neden:** Faz 6'dan kalan not. İlk boyamayı geciktiren kod, kullanıcıların çoğunun hiç basmadığı bir düğmeye aitti.
- **Alternatif:** Düğmeye basınca yüklemek (ilk tıklamada gecikme ve "yükleniyor" durumu gerekirdi).

## D-093 — Son retention çalışması Redis'te

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** Her çalışma `ops:retention:last` anahtarına JSON yazıyor (zaman, tetikleyen, silinen, süre); yazma ve okuma en iyi çaba (Redis yoksa panel "never" gösterir, silme yine yapılmıştır). Testler `test:ops:retention:last` anahtarını kullanıyor (conftest otomatik fixture), çünkü test süreci geliştirme yığınının Redis'ine bağlı.
- **Neden:** Tek bir "son durum" kaydı için migration'lı bir tablo fazla. Kaybolması zararsız: bir sonraki tur yeniden yazar.
- **Alternatif:** `retention_runs` tablosu (geçmişiyle birlikte; denetim izi gerekirse doğru yer).

## D-094 — PostGIS healthcheck'i TCP üzerinden

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `db` healthcheck'i `pg_isready -h 127.0.0.1 …` (compose ve CI servis container'ları).
- **Neden:** Temiz clone denemesinde `make up` başarısız oldu: backend'in ilk `migrate`'i "connection refused" alıp çıktı, `--wait` "unhealthy" dedi. postgres imajı boş volume'da init betiklerini (PostGIS eklentisi) yalnızca unix soketinden dinleyen geçici bir sunucuyla çalıştırıyor, sonra sunucuyu yeniden başlatıyor. Soketi soran `pg_isready` bu geçici sunucuya "hazır" diyordu. Geçici sunucu TCP dinlemediği için TCP kontrolü gerçek sunucuyu bekliyor. Hata yalnızca ilk kurulumda görünüyordu, yani geliştirme sırasında hiç görülmemişti; CI'daki taze servis container'ları da aynı riski taşıyordu.
- **Alternatif:** Backend başlangıcında migrate'i tekrar denemek (belirtiyi gizler, sebebi bırakır).

## D-095 — Geçmiş oynatma ilk veri karesinden başlıyor

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** `firstFrameTs` (saf, testli): oynatma ve sona gelince geri sarma pencerenin başı yerine ilk kaydedilmiş karede. Kaydırıcı aralığı tüm pencere olarak kalıyor.
- **Neden:** Temiz clone'da smoke'un "history aircraft on the map" adımı 0 uçak gördü: yığın 5 dakikalıktı, bir saatlik pencerenin ilk 55 dakikası boştu ve oynatma boşluktan başlıyordu. Kullanıcı da aynı şeyi görürdü: oynat düğmesine basıp boş bir harita.
- **Alternatif:** Pencereyi veriye göre daraltmak (kaydırıcı ölçeği değişir, "son 1 saat" seçimi anlamını kaybeder).

## D-096 — Temiz clone kontrolü ayrı proje adı ve portlarla

- **Tarih:** 2026-10-05 (Faz 8)
- **Karar:** Commit'lenecek ağaç (`git ls-files -co --exclude-standard`) scratch dizinine kopyalandı; `.env`'de portlar 8801/55433/56380, komutlar `COMPOSE="docker compose -p hezarfen-clean"` ile çalıştı: `make up`, `make seed`, `make smoke`, `make test`, `make dem DEM_SOURCE=synthetic`, `make ui-smoke`. Bitince `down -v`.
- **Neden:** `-p` compose dosyasındaki `name:`'i ezer; ayrı proje adı ayrı volume (boş veritabanı) ve ayrı container demek. Çalışan geliştirme yığınına ve verisine dokunmadan "ilk kez kuran biri" senaryosu. Bu kontrol iki gerçek hata buldu (D-094, D-095) ve bir smoke hatası (sentetik DEM'de checkbox etiketi).
- **Alternatif:** Ana yığını `make clean` ile silip yeniden kurmak (geliştirme verisi kaybolur, iki yığın yan yana denenemez).

## D-097 — Testler statik dosya derlemesine bağlı değil; yerel testler DEBUG kapalı

- **Tarih:** 2026-10-06 (Faz 8 sonrası, ilk GitHub CI koşusu)
- **Karar:** `tests/conftest.py`'de otomatik bir fixture testlerde `StaticFilesStorage` kullanıyor. `make test-backend` pytest'i `DJANGO_DEBUG=0` ile çalıştırıyor.
- **Neden:** İlk gerçek CI koşusunda üç ops testi `Missing staticfiles manifest entry for 'ops/ops.css'` ile düştü. CI'da `DJANGO_DEBUG` tanımlı değil, yani DEBUG kapalı; settings bu durumda WhiteNoise'un hash'li manifest depolamasını seçiyor, `{% static %}` de önceden `collectstatic` istiyor. Yerelde `.env`'deki `DJANGO_DEBUG=1` basit depolamayı seçtirdiği için hata hiç görünmedi. Ops paneli `{% static %}` kullanan ilk şablondu. Gerçek manifest CI'ın `stack` job'ında prod imajıyla (collectstatic + smoke'un hash'li htmx kontrolü) zaten sınanıyor.
- **Alternatif:** CI'a `collectstatic` adımı eklemek (Copilot önerisi). CI geçerdi ama yerel testler başka bir yoldan koşmaya devam ederdi; asıl sorun olan ortam farkı kalırdı.
