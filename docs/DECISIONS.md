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
