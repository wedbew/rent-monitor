.PHONY: sync test test-all invariants lint fmt types migrate

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

# Wired in the data-plane step (blueprint 4.8 step 2); needs alembic.ini + migrations/env.py.
migrate:
	@echo "migrate: not available yet (data-plane step)" && exit 1
