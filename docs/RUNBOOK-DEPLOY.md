# Runbook: private-beta deployment (VPS-1, no public exposure)

Scope (RM-224, slice of #15): bring the compose stack up on one host with limits and hardening, prove the journey, take and
restore a logical backup. **Not covered** (stays on #15): Caddy/TLS/DNS, WAL-G and offsite backups, release gates 4-6
measurements. Deploying to the VPS and recording evidence there is blocked by B-016 (`docs/BLOCKERS.md`). Everything below was
written and unit-tested offline; the first real run is recorded in `docs/DEPLOYMENTS.md`.

## Files

| File | Purpose |
|---|---|
| `deploy/compose.yml` | Base stack: Postgres 17, `bootstrap`, `api`, `worker-audit` (queue `audit`, concurrency 1), `worker-ops` (queues `ops`, `batch`, concurrency 2) |
| `deploy/compose.vps1.yml` | VPS-1 overlay: memory/CPU limits, `read_only`, `cap_drop: ALL`, `no-new-privileges`, pids limit, Postgres not published |
| `scripts/check_env.py` | Secret-safe env check (names and rules only, never values) |
| `scripts/journey_check.py` | Sign in, submit, wait for a terminal state, read back; checks the credit is settled |
| `scripts/backup_db.sh`, `scripts/restore_drill.sh` | Logical dump (+ optional `age` encryption), restore into a scratch DB, compare row counts |

## 1. Prepare the environment file (on the host, never in the repo)

1. `cp .env.example .env`, then set at least `APP_ENV=production`, `PUBLIC_APP_URL=https://<domain>`, a random
   `POSTGRES_PASSWORD` (32+ chars), `ADMIN_EMAIL`. Leave `DATABASE_URL`/`PROCRASTINATE_DSN` out: compose sets the in-network URLs.
2. Keep `AUDIT_PROVIDERS=none` and `BILLING_PROVIDER=disabled` until their prerequisites exist (`RISK_FREE_RATE` for `real`, L-018).
3. `uv run python scripts/check_env.py .env --target vps` must print `OK`. It lists which secret-like names are set, never values.
4. `chmod 600 .env`.

## 2. Start

```bash
export COMPOSE_FILES="-f deploy/compose.yml -f deploy/compose.vps1.yml"   # also used by the backup scripts
make vps-config                                                           # render only; fails on a syntax error
docker compose $COMPOSE_FILES up -d --build --wait api worker-audit worker-ops
docker compose $COMPOSE_FILES ps
curl -fsS http://127.0.0.1:8000/api/health
docker compose $COMPOSE_FILES exec -T api python -c "import urllib.request as u; print(u.urlopen('http://localhost:8000/readyz').read())"
```

The API listens on `127.0.0.1:8000` only. Reach it from your machine with `ssh -L 8000:127.0.0.1:8000 deploy@<host>`.

## 3. Prove the journey

Create a verified account for the check (register + verify through the API, or `ADMIN_EMAIL` plus a password reset), then:

```bash
JOURNEY_EMAIL=... JOURNEY_PASSWORD=... uv run python scripts/journey_check.py \
  --base-url http://127.0.0.1:8000 --origin "$PUBLIC_APP_URL" --listing <otodom id>
```

With `AUDIT_PROVIDERS=none` the expected result is `terminal failed_internal` (or similar) with `charge released`: that proves
API, Postgres, queue, worker and ledger together. `--expect success` is for real providers. Exit 0 means pass.

## 4. Back up and restore drill

```bash
./scripts/backup_db.sh                                         # backups/rentmonitor-<stamp>.dump(.age) + .sha256
./scripts/restore_drill.sh backups/rentmonitor-<stamp>.dump    # checksum, restore to scratch DB, row counts, timing
```

Set `BACKUP_AGE_RECIPIENT` (public key) to encrypt; decrypting needs the private key via `AGE_IDENTITY`, kept off the host.
Dumps contain personal data (`GDPR[retention]`): keep `BACKUP_RETENTION_DAILY` copies (default 14), and after any real
restore re-apply erasures (`docs/RUNBOOK-GDPR.md`). This is the logical path only; it gives no point-in-time recovery.
Record the drill time in `docs/DEPLOYMENTS.md`.

## 5. Roll back / stop

`docker compose $COMPOSE_FILES down` keeps the `pgdata` volume. To go back to a previous image, check out the previous git tag
and rerun step 2. Migrations are expand-only, so an older image runs against a newer schema. Never `down -v` on the host
without a verified dump.

## 6. Troubleshooting

| Symptom | Check |
|---|---|
| A container restarts with `Read-only file system` | Something writes outside `/tmp`; the overlay allows only the `/tmp` tmpfs. Report it, do not drop `read_only` silently |
| `worker-audit` OOM-killed (`docker inspect` shows `OOMKilled`) | Lower `AUDIT_CHILD_MEMORY_MB` or raise the limit in the overlay; record in L-020 |
| Audit stays `queued` | `docker compose logs worker-audit`; the reconciler fails it `TIMEOUT` and releases the credit after the deadline |
| `readyz` returns 503 | `checks` in the body says `db` or `queue`; `bootstrap` must have exited 0 |
