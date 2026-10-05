# Hezarfen developer commands. Every tool runs inside containers; the host only
# needs docker, make and git.

COMPOSE ?= docker compose
DEV_RUN  = $(COMPOSE) run --rm --no-deps

.DEFAULT_GOAL := help
.PHONY: help env dirs up up-prod down clean logs ps test test-backend test-ingest test-frontend \
        lint lint-backend lint-ingest lint-frontend seed dem record shell-backend psql

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "created .env from .env.example")

dirs:
	@mkdir -p data/raw data/tiles

up: env dirs ## Build and start the dev stack (hot-reload), wait until healthy
	$(COMPOSE) up -d --build --renew-anon-volumes --wait

up-prod: env dirs ## Start the production-like stack (no override file)
	$(COMPOSE) -f docker-compose.yml up -d --build --wait

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

test-ingest: ## go test
	$(DEV_RUN) ingest go test ./...

test-frontend: ## vitest
	$(DEV_RUN) frontend npm test

lint: lint-ingest lint-frontend lint-backend ## Run all linters / type checks

lint-backend:
	$(DEV_RUN) backend ruff check .
	$(DEV_RUN) backend ruff format --check .

lint-ingest:
	$(DEV_RUN) ingest sh -c 'go vet ./... && test -z "$$(gofmt -l .)"'

lint-frontend:
	$(DEV_RUN) frontend sh -c 'npm run typecheck && npm run lint'

seed: ## Load reference data and seed geofences (Phase 1)
	@echo "seed: implemented in Phase 1"

dem: ## Build DEM, hillshade tiles and COG (Phase 7)
	@echo "dem: implemented in Phase 7"

record: ## Record a small anonymous OpenSky fixture (Phase 2)
	@echo "record: implemented in Phase 2"

shell-backend: ## Django shell
	$(COMPOSE) exec backend python manage.py shell

psql: ## psql into PostGIS
	$(COMPOSE) exec db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'
