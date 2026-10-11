.PHONY: sync test test-all invariants lint fmt types check migrate

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
