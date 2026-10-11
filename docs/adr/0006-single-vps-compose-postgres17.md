# ADR 0006 — One VPS, Docker Compose, Caddy, Postgres 17

- **Status:** accepted (blueprint §1 Option B) · **Date:** 2026-10-11 · **Ticket:** RM-31

## Decision
One OVH VPS-3 in Poland (6 vCore, 12 GB): Caddy, FastAPI, two worker pools and Postgres 17 under Docker Compose, about
$13.38/month net. Backups: nightly `pg_dump` plus WAL-G to Cloudflare R2 (14 d / 56 d), `age`-encrypted.

## Consequences
- One failure domain we control; no cold starts. Host loss is covered by the restore drill (gate 6, under 1 hour).
- Memory and connection budgets are estimates until gates 4 and 5 are measured; compose limits follow the resource matrix.
- Scaling out means a new ADR, not a quiet change.
