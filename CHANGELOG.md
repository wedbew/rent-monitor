# Changelog

All notable user- and operator-visible changes. Format: [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Data plane: SQLAlchemy 2 models for every blueprint §3 table in schema `app`, Alembic baseline `0001`, `make migrate`, Postgres 17 Testcontainers fixtures, pytest-alembic checks, `test_invariant_asking_is_not_deed`; **operator action:** run `make migrate` against the new database (RM-11)
- Workspace skeleton: `rm-core` (settings, `LegalTag` registry), `rm-contracts` (problem codes), `rm-api` (`GET /api/health`), `rm-worker` (empty), `.env.example` (RM-2)

### Changed
- Engines are written from scratch; the POC is reference only (ADR 0001) (RM-2)
