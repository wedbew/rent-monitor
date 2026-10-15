# Deploy runbook: private beta on the OVH VPS

Current target: **`vps-d1af13a5.vps.ovh.net` (`SERVER_NAME`), VPS-3, 12 GB, Frankfurt**
(owner correction, 2026-10-14; `docs/INFRASTRUCTURE.md`). The older Prague VPS-1
`vps-ee6fa92e.vps.ovh.net` is `SERVER_V1_NAME` and is not the deployment target.

Scope: one host, Docker Compose, **private beta**: the API and Postgres listen on `127.0.0.1` only and are reached
through an SSH tunnel. Public exposure (Caddy, TLS, DNS) is a separate, opt-in step that needs `docs/PRE-DEPLOYMENT.md` to be
ticked first. Files: `deploy/compose.yml` (base), `deploy/compose.prod.yml` (VPS limits and hardening),
`deploy/Caddyfile` (public profile), `scripts/check_env.py`, `scripts/journey_check.py`, `scripts/backup_db.sh`,
`scripts/restore_drill.sh`. Every deployment is logged in `docs/DEPLOYMENTS.md`.

Rules: deploy only a commit that is merged to `staging` and green; never read or print `.env` values; no volume wipes, DNS or
firewall changes without the owner's yes (`docs/BLOCKERS.md`, `.agent/agents.md` §4).

## 0. One-time host preparation (owner or agent over a working SSH session)

1. `deploy/setup-server.sh` has run (deploy user, key-only SSH, UFW 22/80/443, swap, Docker). Evidence: `ssh deploy@host true`.
2. `git clone` the repo to `/opt/rent-monitor` as `deploy`; `git checkout <merged staging commit>`.
3. Create `/opt/rent-monitor/.env` from `.env.example` **on the host**, mode 600, with real values (never committed, never
   pasted into chats). Required for the beta: `APP_ENV=production`, `PUBLIC_APP_URL` (`http://localhost:8000` for the tunnel with
   `--private`), `POSTGRES_PASSWORD` (24+ random characters), `RESEND_API_KEY` and a verified `MAIL_FROM`, `GOOGLE_CLIENT_ID`,
   `AUDIT_PROVIDERS=real`, `RISK_FREE_RATE` (owner input). The settings in `compose.prod.yml` derive `DATABASE_URL` and
   `PROCRASTINATE_DSN` from `POSTGRES_PASSWORD`.
4. `uv run python scripts/check_env.py --env-file .env --private` must print `0 error(s)`. It reports names and reasons only.
5. Set `POSTGRES_PASSWORD` **before the first start**: Postgres applies it only when the data volume is created. Changing it later
   needs `ALTER USER` inside the database as well as in `.env`, otherwise `bootstrap` fails with `password authentication failed`.

## 1. Deploy a commit

Every `docker compose` command needs `--env-file .env` (the compose files live in `deploy/`, so Compose would otherwise
look for `deploy/.env`) and `IMAGE_TAG` (kept in `.env` on the host). `.env` must never carry `KEY=   # comment` lines:
Compose reads the comment as the value; `.env.example` keeps comments on their own line and `check_env.py` refuses a value
that starts with `#`. Run the checker inside the built image (the host has no `uv`):
`dc run --rm --no-deps --entrypoint python api scripts/check_env.py --private`.

```bash
cd /opt/rent-monitor && git fetch && git checkout <sha> && export IMAGE_TAG=$(git rev-parse --short HEAD)
C="docker compose -f deploy/compose.yml -f deploy/compose.prod.yml"
$C build                              # tags rentmonitor-py:$IMAGE_TAG
$C run --rm bootstrap                 # migrations (expand-only), Procrastinate schema, seed: idempotent
$C up -d --wait postgres api worker-audit worker-ops
$C ps                                 # all healthy
```

Migrations must be backward compatible with the previous image (expand, deploy, contract), which is what makes the rollback
below safe.

## 2. Verify (a health check alone is not enough)

```bash
$C exec -T api python scripts/journey_check.py --base-url http://localhost:8000   # prints one JSON object
# One REAL listing through the deployed stack (one Otodom request; numbers and codes only, throwaway user removed):
#   cat scripts/live_audit_check.py | ssh <host> "... $C exec -T api sh -c 'cat > /tmp/l.py && PYTHONPATH=/app/scripts python /tmp/l.py --listing <otodom url>'"
```

Expected: `"ok": true`, events `progress... done`, `"result_matches_engine": true`, `"cleaned_up": true`. Evidence class **fake
provider data** (planted listing and comparables): it proves API -> queue -> worker -> Postgres -> engine child -> result on
this host, not Otodom or market data. Record the JSON (it has no secrets) in `docs/DEPLOYMENTS.md`. Real-provider evidence is a
separate, owner-authorised run (one listing, `STATUS.md` level 3).

Private access for people: `ssh -L 8000:127.0.0.1:8000 deploy@host`, then use `http://localhost:8000`.

## 3. Roll back

```bash
git checkout <previous-sha> && export IMAGE_TAG=<previous-short-sha>   # the previous image is still on the host
$C up -d --wait api worker-audit worker-ops                           # no bootstrap: the schema is only ever expanded
```

If the failure is data, restore (section 4) into a scratch database first and compare before touching the live one. In-flight
audits are safe across a restart: the worker stops its engine child and the reconciler fails and refunds anything left running
past its deadline (#186).

## 4. Backups and restore evidence

Nightly (cron as `deploy`): `BACKUP_DIR=/var/backups/rentmonitor scripts/backup_db.sh`. It writes a mode-600 `pg_dump`, checks it
is readable, keeps 7 days. Restore drill, against a scratch database, never the live one:
`scripts/restore_drill.sh /var/backups/rentmonitor/rm-<stamp>.dump` prints the elapsed time and whether every table's exact row
count matches. **Limits (L-014):** no offsite copy yet (R2 upload is credentialed and wired later), no WAL-G point-in-time
recovery, so the RPO is the cron interval and no RTO has been measured on this host; release gate 6 stays open.

## 5. Initial resource limits (originally sized for VPS-1, 4 GB)

These conservative ceilings also fit the current 12 GB VPS-3. They have not been measured
on that host; do not automatically raise limits or worker concurrency before gate-4 evidence.

`compose.prod.yml`: postgres 1 G, api 512 M, worker-audit 1.5 G (the engine child is capped inside it by
`AUDIT_CHILD_MEMORY_MB`), worker-ops 256 M, caddy 64 M; containers drop all capabilities, run read-only with a 64 MB `/tmp`
and `no-new-privileges`. Two worker lanes: `worker-audit` (queue `audit`, concurrency 1) and `worker-ops` (`ops,batch`,
concurrency 2), so a long audit can never starve mail, the reconciler or the monitors. These are ceilings sized on paper; gate 4
(20 representative audits, `memory.peak`) replaces them with measurements.

## 6. Public exposure (not part of the private beta)

Needs, in order: the owner's DNS change (B-005), `PUBLIC_HOST` and `PUBLIC_APP_URL=https://<domain>` in `.env`,
`check_env.py` without `--private`, then `$C --profile public up -d --build caddy` (the image is built from
`deploy/web.Dockerfile`: the SPA and the Caddyfile together; `GOOGLE_CLIENT_ID` from `.env` is passed as the public
build argument for the Google button). Caddy terminates TLS, hides `/healthz` and `/readyz`, streams SSE unbuffered,
proxies `/api/*` and serves the SPA (RM-281). Rebuild `caddy` on every deploy so the HTML and its assets match. Do not open it before the `docs/PRE-DEPLOYMENT.md` sections for security,
privacy and legal are ticked with evidence.

## 7. When something is wrong

`$C logs --tail=100 <service>`; `$C ps`; `curl -s localhost:8000/readyz` inside the api container. Never `down -v` (that deletes
the database volume). Stop and ask the owner for anything that wipes data, changes DNS or the firewall, or needs a secret.
