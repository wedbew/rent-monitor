# RentMonitor

Paid SaaS for Polish buy-to-let investors: paste an Otodom sale listing, get a deterministic 10-year deal valuation.
Single VPS, Docker Compose, Caddy + FastAPI + Procrastinate workers + Postgres 17, Python-only server.
Architecture lives in [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md); this file only says how to run things.

## How to run

```bash
make sync        # uv sync --all-packages --group dev
make test        # uv run pytest -m "not e2e" -q
make lint        # ruff check + format check
make types       # pyright
cp .env.example .env   # names only; fill values locally, never commit .env
```

Compose stack, migrations and seeds are not wired yet (see Status).

## Stack

Python ≥ 3.12 (uv workspace), FastAPI, Pydantic v2, structlog. Planned per blueprint: SQLAlchemy 2 async + Alembic,
Procrastinate, Stripe (card + BLIK), Caddy, Postgres 17.

## Status

Phase 1 (backend only). Blueprint §4.8 steps done: none. Workspace skeleton in place (RM-2); next is step 1, the engine foundation (greenfield, ADR 0001; open decisions in [`CONTEXT.md`](CONTEXT.md) §9).

## Project docs

| Doc | Purpose |
|---|---|
| [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) | Spec of record |
| [`docs/TOOLCHAIN.md`](docs/TOOLCHAIN.md) | CI, hooks, governance, agents |
| [`CONTEXT.md`](CONTEXT.md) | Orientation and POC porting map |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | Known limits register |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes |
| [`docs/PRE-DEPLOYMENT.md`](docs/PRE-DEPLOYMENT.md) | Launch checklist (gates, security, legal, ops) |

## Development conventions

Agents and contributors follow [`.agent/agents.md`](.agent/agents.md).
