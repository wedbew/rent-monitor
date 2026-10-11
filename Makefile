.PHONY: sync test test-all invariants lint fmt types check migrate db-up db-down dev seed bootstrap backup-drill up down logs smoke

sync:
	uv sync --all-packages --group dev

test:
	uv run pytest -m "not e2e" -q

test-all:
	uv run pytest -q

invariants:
	uv run pytest -m invariant -q

lint:
	uv run ruff check . && uv run ruff format --check .

fmt:
	uv run ruff format . && uv run ruff check --fix .

types:
	uv run pyright

check: lint types test

# Applies Alembic migrations to $DATABASE_URL (postgresql+psycopg://...). Procrastinate's tables: see README.
migrate:
	uv run alembic upgrade head

COMPOSE = docker compose -f deploy/compose.yml

db-up:
	$(COMPOSE) up -d --wait postgres

db-down:
	$(COMPOSE) down

# Migrations + Procrastinate schema (once) + seed, idempotent; run on the host against $DATABASE_URL.
bootstrap:
	uv run python scripts/bootstrap.py

seed:
	uv run python scripts/seed.py

# Fresh local environment: Postgres 17, app schema, queue schema, seed data. Needs DATABASE_URL and PROCRASTINATE_DSN in .env.
dev: db-up bootstrap

backup-drill:
	./scripts/backup_drill.sh

# The whole app in containers (Postgres, bootstrap, API, worker).
up:
	$(COMPOSE) up -d --build --wait api worker

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

smoke:
	./scripts/smoke_docker.sh
