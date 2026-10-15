# Renti

Paid SaaS for Polish buy-to-let investors: paste an Otodom sale listing, get a deterministic 10-year deal valuation.
Single VPS, Docker Compose, Caddy + FastAPI + Procrastinate workers + Postgres 17, Python-only server.
Architecture lives in [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md); this file only says how to run things.

## How to run

```bash
make sync        # uv sync --all-packages --group dev
make test        # uv run pytest -m "not e2e" -q
make lint        # ruff check + format check
make types       # pyright
make check       # lint + types + test
make ci-fast     # the GitHub pipeline locally, fast (commits, lint, types, unit tests; ~1 min)
make ci          # everything CI runs: tests+coverage, invariants, migrations+squawk, semgrep, audit, gitleaks, actionlint (run before every push)
make ci-full     # make ci + the Docker smoke test
make hooks       # install git hooks incl. a pre-push that runs make ci-fast
cp .env.example .env   # names only; fill values locally, never commit .env
make up          # the WHOLE app in Docker: Postgres 17, bootstrap (migrations, queue schema, seed), API on :8000, audit and ops workers
make smoke       # build, start, check /api/health, /readyz, both workers and seed, then stop (Apple Silicon: DOCKER_DEFAULT_PLATFORM=linux/amd64, L-021)
make down        # stop the containers (add -v via docker compose to drop the data volume)
make dev         # only Postgres in Docker + bootstrap; run API/worker on the host with uv run
make migrate     # alembic upgrade head against $DATABASE_URL (postgresql+psycopg://…)
make seed        # plans, feature flags, admin role (set ADMIN_EMAIL); idempotent
make fe-install   # SPA dependencies (Node per frontend/.node-version, pnpm via corepack)
make fe-check     # the SPA gate: api drift, types, lint, css, format, tests, build
make fe-fixtures   # sanitised UI fixtures from the newest capture (frontend/test/fixtures)
make fe-dev       # Vite dev server, /api proxied to the local API
make api-samples  # run every API operation over loopback HTTP, keep the answers in data/api-samples/ (gitignored; POSTGRES_PORT=55432 if 5432 is taken)
make api-samples-clean  # delete every capture
make backup-drill  # dump and restore the dev database into a scratch DB and compare row counts
make db-down     # stop the dev database
```

Integration and migration tests start a throwaway Postgres 17 with Testcontainers (Docker required); set
`TEST_DATABASE_URL` to use an existing disposable database instead. Procrastinate's tables are applied separately by its
own CLI (`make procrastinate-schema`), not by Alembic. The stack is `deploy/compose.yml` (Postgres on 127.0.0.1;
set `POSTGRES_PORT` / `API_PORT` if 5432 / 8000 are taken; values come from `.env`, optional). `scripts/stripe_clock_customer.py` creates a Stripe test clock and customer
(test-mode key only). The production-shaped Compose stack arrives with RM-15.

## Stack

Python ≥ 3.12 (uv workspace), FastAPI, Pydantic v2, structlog. SQLAlchemy 2.0 async + psycopg 3 + Alembic (ADR 0007), Procrastinate 3.x. Billing pilot: Paddle one-time report packs (`docs/PADDLE-INTEGRATION.md`, off by default). Planned per blueprint: Caddy, Postgres 17, Better Stack monitoring (errors via the Sentry SDK, uptime, heartbeats; ADR 0009).

## Status

Phase 1 (backend only). The authoritative, dated delivery state, with evidence per journey step, is [`docs/STATUS.md`](docs/STATUS.md);
it also separates "implemented" from "integrated" and "verified against a real provider". Deployment: [`docs/RUNBOOK-DEPLOY.md`](docs/RUNBOOK-DEPLOY.md) and [`docs/DEPLOYMENTS.md`](docs/DEPLOYMENTS.md). Open decisions: [`CONTEXT.md`](CONTEXT.md) §9.

## Project docs

| Doc | Purpose |
|---|---|
| [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) | Spec of record |
| [`docs/TOOLCHAIN.md`](docs/TOOLCHAIN.md) | CI, hooks, governance, agents |
| [`docs/STATUS.md`](docs/STATUS.md) | Delivery state: journey, backlog map, owner actions |
| [`docs/OTODOM-NIGHTLY-IMPORT.md`](docs/OTODOM-NIGHTLY-IMPORT.md) | Implementation guide: launch-city bootstrap, nightly new offers, immutable prices and 90-day archive |
| [`CONTEXT.md`](CONTEXT.md) | Orientation and POC porting map |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | Known limits register |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes |
| [`docs/adr/`](docs/adr) | Architecture decision records (0001 greenfield … 0009 Better Stack) |
| [`docs/ENGINE-SPEC.md`](docs/ENGINE-SPEC.md) | Engine rules, approved with amendments (B-007 resolved) |
| [`docs/GOOGLE-AUTH-SPEC.md`](docs/GOOGLE-AUTH-SPEC.md) | Google sign-in, sessions and magic link as built (RM-12, awaiting review) |
| [`docs/ANALYTICS-SPEC.md`](docs/ANALYTICS-SPEC.md) | Umami loading, CSP options, event allow-list, consent notice (Phase 2) |
| [`docs/OBSERVABILITY-SPEC.md`](docs/OBSERVABILITY-SPEC.md) | Better Stack errors, logs, uptime, heartbeats, alerts (spec) |
| [`docs/R2-SPEC.md`](docs/R2-SPEC.md) | R2 buckets, tokens, WAL-G, restore drill, alerts (spec) |
| [`docs/STRIPE-SPEC.md`](docs/STRIPE-SPEC.md) | Stripe catalog, Checkout, webhook contract, sandbox runbook, tests (spec) |
| [`docs/RESEND-SPEC.md`](docs/RESEND-SPEC.md) | Transactional email: wiring, catalog, bounces, domain checklist (spec) |
| [`docs/deal-analysis.schema.json`](docs/deal-analysis.schema.json) | JSON Schema of the report in `result` (`scripts/gen_report_schema.py`, rules in [`docs/REPORT-SCHEMA.md`](docs/REPORT-SCHEMA.md)); a test fails if it drifts |
| [`docs/openapi.json`](docs/openapi.json) | Generated OpenAPI schema (`scripts/gen_openapi.py`); a test fails if it drifts from the app |
| [`docs/RUNBOOK-GDPR.md`](docs/RUNBOOK-GDPR.md) | Retention, erasure, export, restore re-erasure |
| [`frontend/README.md`](frontend/README.md) | SPA bootstrap, scripts, dependency decisions, browser support |
| [`docs/FRONTEND-PLAN.md`](docs/FRONTEND-PLAN.md) | Phase 2 frontend plan: V2 handoff verification, API smoke and samples first, e2e coverage gate, issues #263-#286 |
| [`design/`](design/README.md) | Phase 2 design direction: interactive prototype, principles, spec (#44 input) |
| [`docs/BLOCKERS.md`](docs/BLOCKERS.md) | Owner-only blockers agents stop on |
| [`docs/BACKLOG.md`](docs/BACKLOG.md) | Blueprint → issue traceability |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Milestones, dependencies and launch gates |
| [`docs/DELIVERY-AUDIT.md`](docs/DELIVERY-AUDIT.md) | Autonomous delivery audit: GitHub throughput, bottlenecks and proposed faster workflow (RM-177) |
| [`docs/AUTONOMY.md`](docs/AUTONOMY.md) | Running agents in GitHub Actions, secrets, limits |
| [`docs/AGENT-BOT.md`](docs/AGENT-BOT.md) | Limited machine user for autonomous agents |
| [`docs/PRE-DEPLOYMENT.md`](docs/PRE-DEPLOYMENT.md) | Launch checklist (gates, security, legal, ops) |

## Development conventions

Agents and contributors follow [`.agent/agents.md`](.agent/agents.md).
