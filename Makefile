.PHONY: sync test test-all invariants lint fmt types check migrate db-up db-down dev seed procrastinate-schema backup-drill

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

COMPOSE_DEV = docker compose -f deploy/compose.dev.yml

db-up:
	$(COMPOSE_DEV) up -d --wait postgres

db-down:
	$(COMPOSE_DEV) down

# Procrastinate's own tables (public schema), applied by its CLI, not Alembic.
procrastinate-schema:
	uv run procrastinate --app=rm_worker.app.app schema --apply

seed:
	uv run python scripts/seed.py

# Fresh local environment: Postgres 17, app schema, queue schema, seed data. Needs DATABASE_URL and PROCRASTINATE_DSN in .env.
dev: db-up migrate procrastinate-schema seed

backup-drill:
	./scripts/backup_drill.sh
