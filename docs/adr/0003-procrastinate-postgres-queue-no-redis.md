# ADR 0003 — Procrastinate on Postgres; no Redis

- **Status:** accepted (blueprint decision table, "Job queue" and "Progress") · **Date:** 2026-10-11 · **Ticket:** RM-31

## Context
Jobs must survive restarts, be visible in SQL, and take part in the same transactions as the ledger. `arq` is in
maintenance-only mode; Celery plus Redis adds a stateful service for no gain at this scale.

## Decision
Procrastinate (async, Postgres-backed) runs the `audit`, `batch` and `ops` queues. Progress reaches browsers through SSE fed by
Postgres `LISTEN/NOTIFY`, with an `audit_event` table for replay via `Last-Event-ID`. There is no Redis and no `REDIS_URL`.
Procrastinate's own tables are applied with `procrastinate schema --apply`, not Alembic.

## Consequences
- All state lives in Postgres; API processes stay stateless; one backup covers queue and data.
- Connection budget matters: listeners and worker pools must stay under 70 of `max_connections=100` (blueprint §6, gate 5).
- A throughput ceiling exists (Postgres as broker); revisit only with measured evidence from the load harness.
- Pin the Procrastinate 3.x API through `context7` before writing code.
