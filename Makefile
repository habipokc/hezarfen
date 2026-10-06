# Hezarfen developer commands. Every tool runs inside containers; the host only
# needs docker, make and git.

COMPOSE ?= docker compose
# ingest runs as the host user so files it writes under data/ (and go.mod in dev) are yours
export HEZARFEN_UID ?= $(shell id -u)
export HEZARFEN_GID ?= $(shell id -g)
DEV_RUN  = $(COMPOSE) run --rm --no-deps

.DEFAULT_GOAL := help
.PHONY: help env dirs up up-prod down clean logs ps test test-backend test-ingest test-frontend \
        lint lint-backend lint-ingest lint-frontend lint-ci seed prune ws smoke ui-smoke dem record superuser shell-backend psql

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "created .env from .env.example")

dirs:
	@mkdir -p data/raw data/tiles data/reference data/dem

up: env dirs ## Build and start the dev stack (hot-reload), wait until healthy
	$(COMPOSE) up -d --build --renew-anon-volumes --wait

up-prod: env dirs ## Start the production-like stack (no override file)
	DJANGO_DEBUG=0 $(COMPOSE) -f docker-compose.yml up -d --build --wait

down: ## Stop the stack (keeps volumes)
	$(COMPOSE) down

clean: ## Stop the stack and delete its volumes (database included)
	$(COMPOSE) down -v

logs: ## Follow logs (make logs s=backend for one service)
	$(COMPOSE) logs -f --tail=100 $(s)

ps: ## Show service status
	$(COMPOSE) ps

test: test-ingest test-frontend test-backend ## Run all test suites

test-backend: ## pytest against the real PostGIS
	$(COMPOSE) up -d --wait db redis
	@# DEBUG off as in CI: .env's DJANGO_DEBUG=1 once hid a CI-only failure (D-097)
	$(COMPOSE) run --rm -e DJANGO_DEBUG=0 backend pytest

test-ingest: ## go test (store/publish integration tests use the stack's db and redis)
	$(COMPOSE) up -d --wait db redis
	$(DEV_RUN) ingest sh -c 'INGEST_TEST_DATABASE_URL="postgres://$$POSTGRES_USER:$$POSTGRES_PASSWORD@db:5432/$$POSTGRES_DB" \
	    INGEST_TEST_REDIS_URL=redis://redis:6379/0 go test ./...'

test-frontend: ## vitest
	$(DEV_RUN) frontend npm test

lint: lint-ingest lint-frontend lint-backend ## Run all linters / type checks

lint-backend:
	$(DEV_RUN) backend ruff check .
	$(DEV_RUN) backend ruff format --check .
	$(COMPOSE) run --rm backend python manage.py makemigrations --check --dry-run

lint-ingest:
	$(DEV_RUN) ingest sh -c 'go vet ./... && test -z "$$(gofmt -l .)"'

lint-frontend:
	$(DEV_RUN) frontend sh -c 'npm run typecheck && npm run lint'

ACTIONLINT_IMAGE ?= rhysd/actionlint:1.7.12
SHELLCHECK_IMAGE ?= koalaman/shellcheck:stable
lint-ci: ## Lint the GitHub Actions workflow (actionlint) and shell scripts (shellcheck)
	docker run --rm -v "$(CURDIR):/repo" -w /repo $(ACTIONLINT_IMAGE) -color
	docker run --rm -v "$(CURDIR):/mnt" -w /mnt $(SHELLCHECK_IMAGE) scripts/*.sh backend/docker/*.sh

# One-off backend container with the scripts and data dirs mounted. It runs as the host
# user so downloads in data/ are not root-owned.
SEED_RUN = $(COMPOSE) run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
           -v "$(CURDIR)/scripts:/scripts:ro" -v "$(CURDIR)/data:/data" backend

seed: env dirs ## Load airports + provinces (ogr2ogr) and seed geofences (REFERENCE_OFFLINE=1 for fixtures)
	$(SEED_RUN) sh -c 'python manage.py migrate --noinput \
	    && REFERENCE_OFFLINE=$(REFERENCE_OFFLINE) sh /scripts/load_reference_data.sh \
	    && python manage.py seed_geofences'

prune: ## Delete position history older than POSITIONS_RETENTION_DAYS now (the maintenance service also does it hourly)
	$(COMPOSE) exec backend python manage.py prune_positions

ws: ## Tail /ws/live/ through nginx (make ws args="--seconds 60 --bbox 28.5,40.8,29.5,41.4")
	$(COMPOSE) exec backend python manage.py ws_tail $(args)

smoke: ## curl checks of the running stack through nginx (health, live data, seed, terrain, /ops)
	BASE=http://localhost:$(or $(HEZARFEN_HTTP_PORT),8800) sh scripts/smoke_http.sh

UI_SMOKE_IMAGE ?= mcr.microsoft.com/playwright:v1.63.0-noble
ui-smoke: dirs ## Headless-browser check of the live map on localhost (screenshots in data/ui-smoke)
	@mkdir -p data/ui-smoke
	docker run --rm --network host --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
	    -e BASE=http://localhost:$(or $(HEZARFEN_HTTP_PORT),8800)/ -e OUT=/out \
	    -v "$(CURDIR)/scripts/ui-smoke:/src:ro" -v "$(CURDIR)/data/ui-smoke:/out" $(UI_SMOKE_IMAGE) \
	    sh -c 'cp -r /src /tmp/ui && cd /tmp/ui && npm install --silent --no-audit --no-fund && node smoke.mjs'

dem: env dirs ## Download the DEM, build the COG and hillshade tiles (DEM_SOURCE=auto|copernicus|synthetic)
	$(COMPOSE) --profile tools build gdal
	$(COMPOSE) --profile tools run --rm -e DEM_SOURCE=$(or $(DEM_SOURCE),auto) gdal sh /scripts/prepare_dem.sh

RECORD_DIR ?= ingest/testdata/opensky
record: env ## Record anonymous OpenSky snapshots (COUNT=25 INTERVAL=10 RECORD_DIR=ingest/testdata/opensky)
	@mkdir -p $(RECORD_DIR)
	$(COMPOSE) run --rm --no-deps --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
	    -e COUNT=$(or $(COUNT),25) -e INTERVAL=$(or $(INTERVAL),10) \
	    -v "$(CURDIR)/scripts:/scripts:ro" -v "$(CURDIR)/$(RECORD_DIR):/out" backend sh /scripts/record_fixture.sh

superuser: ## Create a Django admin user (interactive)
	$(COMPOSE) exec backend python manage.py createsuperuser

shell-backend: ## Django shell
	$(COMPOSE) exec backend python manage.py shell

psql: ## psql into PostGIS
	$(COMPOSE) exec db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'
