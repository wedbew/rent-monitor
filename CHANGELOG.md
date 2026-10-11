# Changelog

All notable user- and operator-visible changes. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- CI: `migrations` job enabled and required on `staging` (squawk + pytest-alembic); migrations now run with `lock_timeout` 5 s and `statement_timeout` 5 min; `.env.example` rewritten with where-to-get comments and new names `RELEASE`, `POSTGRES_IMAGE`, `POSTGRES_PORT`, `ADMIN_EMAIL`, `STRIPE_PRICE_ID_PRO`, `OPENROUTER_CALL_ESTIMATE_USD`, `IMAGE_HOST_ALLOWLIST` (RM-67)
- Vision client: OpenRouter client (`OPEN_ROUTER_API_KEY`, 120 s total, 3 attempts, budget-gated, `usage.cost` kept as `Decimal`), box-wide cap of 4 calls in flight (Postgres advisory locks, self-healing), photo pipeline (https host allow-list `IMAGE_HOST_ALLOWLIST`, 10 MB / 40 MP caps, EXIF and GPS stripped, 1,600 px downscale, near-duplicate removal, 25 photo / 2 plan limits); new env names `OPENROUTER_CALL_ESTIMATE_USD`, `IMAGE_HOST_ALLOWLIST`; new dependencies `pillow`, `httpx` in rm-worker (RM-23)
- Otodom fetch client: strict listing-ref parser (SSRF-safe), `curl_cffi` transport with a hard total timeout and size cap, shared 1 req/s slots and a 15-minute circuit breaker in new table `app.host_throttle` (**operator action:** `make migrate`, migration `0002`), 6-hour cross-tenant snapshot reuse, typed errors `LISTING_GONE` / `UPSTREAM_BLOCKED` / `UPSTREAM_SCHEMA_DRIFT`; new dependency `curl-cffi` (RM-22)
- Dev environment: `deploy/compose.dev.yml` (Postgres 17, loopback only), `make dev|db-up|db-down|seed|procrastinate-schema|backup-drill`, idempotent `scripts/seed.py` (plans free/pro, flags `screener`/`redesign`/`analyst`, admin role from `ADMIN_EMAIL`), `rm_worker.app.app`, `scripts/stripe_clock_customer.py` (test-mode keys only); `alembic` now falls back to `DATABASE_URL` from `.env` (RM-29)
- API platform: structlog JSON logging with request/user/audit/job context and key-based redaction, Sentry init (off without `SENTRY_DSN`, PII scrubbed), RFC 9457 problem responses (new codes `VALIDATION_ERROR`, `NOT_FOUND`, `HTTP_ERROR`, `NOT_READY`), `X-Request-ID`, `GET /healthz` and `GET /readyz` (internal only; Caddy must block them), per-request session dependency, lifespan-owned engine and HTTP client; new env names `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `RELEASE` (RM-18)
- Data plane: SQLAlchemy 2 models for every blueprint §3 table in schema `app`, Alembic baseline `0001`, `make migrate`, Postgres 17 Testcontainers fixtures, pytest-alembic checks, `test_invariant_asking_is_not_deed`; **operator action:** run `make migrate` against the new database (RM-11)
- Workspace skeleton: `rm-core` (settings, `LegalTag` registry), `rm-contracts` (problem codes), `rm-api` (`GET /api/health`), `rm-worker` (empty), `.env.example` (RM-2)

### Changed
- Flat package layout: `packages/rm_core`, `packages/rm_contracts`, `services/rm_api`, `services/rm_worker` (folder = module, no `src/`, ADR 0008); no import or API change; run `uv sync --all-packages --group dev` again (RM-61, RM-63)
- Engines are written from scratch; the POC is reference only (ADR 0001) (RM-2)
