# Hezarfen developer commands. Every tool runs inside containers; the host only
# needs docker, make and git.

COMPOSE ?= docker compose
# ingest runs as the host user so files it writes under data/ (and go.mod in dev) are yours
export HEZARFEN_UID ?= $(shell id -u)
export HEZARFEN_GID ?= $(shell id -g)
DEV_RUN  = $(COMPOSE) run --rm --no-deps

.DEFAULT_GOAL := help
.PHONY: help env dirs up up-prod down clean logs ps test test-backend test-ingest test-frontend \
        lint lint-backend lint-ingest lint-frontend seed prune dem record superuser shell-backend psql

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "created .env from .env.example")

dirs:
	@mkdir -p data/raw data/tiles data/reference

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
	$(COMPOSE) run --rm backend pytest

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

# One-off backend container with the scripts and data dirs mounted. It runs as the host
# user so downloads in data/ are not root-owned.
SEED_RUN = $(COMPOSE) run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
           -v "$(CURDIR)/scripts:/scripts:ro" -v "$(CURDIR)/data:/data" backend

seed: env dirs ## Load airports + provinces (ogr2ogr) and seed geofences (REFERENCE_OFFLINE=1 for fixtures)
	$(SEED_RUN) sh -c 'python manage.py migrate --noinput \
	    && REFERENCE_OFFLINE=$(REFERENCE_OFFLINE) sh /scripts/load_reference_data.sh \
	    && python manage.py seed_geofences'

prune: ## Delete position history older than POSITIONS_RETENTION_DAYS
	$(COMPOSE) exec backend python manage.py prune_positions

dem: ## Build DEM, hillshade tiles and COG (Phase 7)
	@echo "dem: implemented in Phase 7"

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
