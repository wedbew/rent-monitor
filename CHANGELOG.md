# Changelog

All notable user- and operator-visible changes. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- API platform: structlog JSON logging with request/user/audit/job context and key-based redaction, Sentry init (off without `SENTRY_DSN`, PII scrubbed), RFC 9457 problem responses (new codes `VALIDATION_ERROR`, `NOT_FOUND`, `HTTP_ERROR`, `NOT_READY`), `X-Request-ID`, `GET /healthz` and `GET /readyz` (internal only; Caddy must block them), per-request session dependency, lifespan-owned engine and HTTP client; new env names `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `RELEASE` (RM-18)
- Data plane: SQLAlchemy 2 models for every blueprint §3 table in schema `app`, Alembic baseline `0001`, `make migrate`, Postgres 17 Testcontainers fixtures, pytest-alembic checks, `test_invariant_asking_is_not_deed`; **operator action:** run `make migrate` against the new database (RM-11)
- Workspace skeleton: `rm-core` (settings, `LegalTag` registry), `rm-contracts` (problem codes), `rm-api` (`GET /api/health`), `rm-worker` (empty), `.env.example` (RM-2)

### Changed
- Engines are written from scratch; the POC is reference only (ADR 0001) (RM-2)
