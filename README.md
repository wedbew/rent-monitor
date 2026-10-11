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
make check       # lint + types + test (run before pushing)
cp .env.example .env   # names only; fill values locally, never commit .env
make dev         # local Postgres 17 (Docker) + migrate + Procrastinate schema + seed; needs DATABASE_URL and PROCRASTINATE_DSN in .env
make migrate     # alembic upgrade head against $DATABASE_URL (postgresql+psycopg://…)
make seed        # plans, feature flags, admin role (set ADMIN_EMAIL); idempotent
make backup-drill  # dump and restore the dev database into a scratch DB and compare row counts
make db-down     # stop the dev database
```

Integration and migration tests start a throwaway Postgres 17 with Testcontainers (Docker required); set
`TEST_DATABASE_URL` to use an existing disposable database instead. Procrastinate's tables are applied separately by its
own CLI (`make procrastinate-schema`), not by Alembic. The dev stack is `deploy/compose.dev.yml` (Postgres 17 on 127.0.0.1;
set `POSTGRES_PORT` if 5432 is taken). `scripts/stripe_clock_customer.py` creates a Stripe test clock and customer
(test-mode key only). The production-shaped Compose stack arrives with RM-15.

## Stack

Python ≥ 3.12 (uv workspace), FastAPI, Pydantic v2, structlog. SQLAlchemy 2.0 async + psycopg 3 + Alembic (ADR 0007), Procrastinate 3.x. Planned per blueprint: Stripe (card + BLIK), Caddy, Postgres 17.

## Status

Phase 1 (backend only). Blueprint §4.8 steps done: none. Workspace skeleton (RM-2) and the data-plane baseline (models, Alembic, Postgres tests; RM-11) are in place; next is step 1, the engine foundation (greenfield, ADR 0001; open decisions in [`CONTEXT.md`](CONTEXT.md) §9).

## Project docs

| Doc | Purpose |
|---|---|
| [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) | Spec of record |
| [`docs/TOOLCHAIN.md`](docs/TOOLCHAIN.md) | CI, hooks, governance, agents |
| [`CONTEXT.md`](CONTEXT.md) | Orientation and POC porting map |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | Known limits register |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes |
| [`docs/adr/`](docs/adr) | Architecture decision records (0001 greenfield … 0007 pins) |
| [`docs/BLOCKERS.md`](docs/BLOCKERS.md) | Owner-only blockers agents stop on |
| [`docs/BACKLOG.md`](docs/BACKLOG.md) | Blueprint → issue traceability |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Milestones, dependencies and launch gates |
| [`docs/AUTONOMY.md`](docs/AUTONOMY.md) | Running agents in GitHub Actions, secrets, limits |
| [`docs/AGENT-BOT.md`](docs/AGENT-BOT.md) | Limited machine user for autonomous agents |
| [`docs/PRE-DEPLOYMENT.md`](docs/PRE-DEPLOYMENT.md) | Launch checklist (gates, security, legal, ops) |

## Development conventions

Agents and contributors follow [`.agent/agents.md`](.agent/agents.md).
