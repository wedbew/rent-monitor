# Deployments

One row per deployment of a merged `staging` commit to a host. Evidence class matters: **fake provider data** (planted
listing and comparables, real API/queue/worker/Postgres/engine) is not **real provider** evidence (an owner-authorised live
run). See `docs/RUNBOOK-DEPLOY.md`.

## OVH VPS-3 (current private-beta target)

Owner correction, 2026-10-14: target `vps-d1af13a5.vps.ovh.net` (`SERVER_NAME`), Frankfurt,
6 vCore, 12 GB RAM, 100 GB storage. OVH Manager shows Active. Codex authenticated as `deploy`
with the existing SSH key: Docker/Compose and 2 GiB swap are present; clean checkout at
`4127f79`, no running Docker containers and no app image. Host `.env` mode was restricted
from 664 to 600 without reading or changing its contents. No application was deployed in
this session and no host journey evidence exists.

| Date | Commit | Result | Journey evidence |
|---|---|---|---|
| 2026-10-14 | `3cdf0be` (merged `staging`) | **Deployed, private**: image built on the host; `check_env.py --private` leaves one error, `MAIL_FROM` is still Resend's onboarding sender (production mode refuses it, so registration and reset mail cannot be sent until a domain is verified); `bootstrap` ran (migrations at head, seed); `postgres`, `api`, `worker-audit`, `worker-ops` healthy; `/api/health` ok, `/readyz` db and queue ok; periodic jobs (`monitor`, `reconcile_queued_audits`, `billing_sweep`) ran. Billing is `disabled`, `AUDIT_PROVIDERS=real`, `RISK_FREE_RATE=0.055` is an **unsourced placeholder** (owner, 2026-10-14) | `journey_check.py` on the host: `ok: true`, events `progress x5, done`, `succeeded_degraded` (no vision), `result_matches_engine: true`, 1.96 s, rows cleaned up. **Fake provider data.** Separately, one live Otodom request from this host (Frankfurt) to the owner's listing: HTTP 200, `__NEXT_DATA__` present, `classify` OK (shape only, no values kept; single request, no sustained-load evidence) |
| 2026-10-19 | `4e6d28e` (merged `staging`, CI green on the merge commit) | **Deployed, private**: host checkout moved from `fe04449`; image built on the host; `check_env.py --private`: `0 error(s), 0 warning(s)`; `bootstrap` applied migrations `0012` to `0019` (expand-only: seller questions, media, corpus and history tables, risk-free rate table; `alembic_version` = `0019`); `postgres`, `api`, `worker-audit`, `worker-ops` healthy; `api` on `4e6d28e`. Rollback path: `fe04449` image is still on the host, but the schema is at `0019` so the previous image must be checked against it before use | `journey_check.py` on the host: `ok: true`, events `progress... done`, `succeeded_degraded` (`VISION_UNAVAILABLE`: no OpenRouter key on this host), `result_matches_engine: true` (setting used: no stored ECB rate yet), `cleaned_up: true`. **Fake provider data.** No live Otodom request in this deploy. The ECB rate refresh runs at 06:15 UTC; its first success is not yet observed on the host (see #417 for the journey check's comparison) |
| 2026-10-16 | `fe04449` (host unchanged; the tool was run from `staging` `6f162a8`, copied into the checkout and removed again) | **Bounded synthetic load, no deploy:** `scripts/load_check.sh` with 1, 5, 10 and 20 audits submitted at the same moment, billing disabled, nothing external called. All `succeeded_degraded` (no photos, so no vision), 20 audits finished in 24.4 s (median 14.0 s; the audit worker runs one at a time), API poll latency p95 0.09 s, **`pg_stat_activity` peak 28** of the gate's 70, worker-audit cgroup `memory.peak` 114.8 MB of 1.5 GiB (**7.1 %**); worker-ops idles at 92 MB of 256 MB (34 %, not caused by the run); every planted row removed (0 left); disk 12 %, memory 1.3 of 11.7 GB used before and after | **Not gate evidence yet:** no photos or floor plans (the vision path, the biggest memory user, did not run), no batch import running, no webhook traffic, no real Otodom data, one burst each. Gate 4 and 5 numbers above are a lower bound for a real audit mix, see L-041 |
| 2026-10-14 | same | Logical backup and scratch restore on the host: 36 tables identical in 1 s; nightly cron 03:17 installed for `deploy` (dumps in `~/backups`, 7 days, no offsite copy, L-014) | `restore_drill.sh`: OK |

Open before the beta is usable by people: a verified Resend sender and the real provider keys on the host (the host `.env`
had `KEY=   # comment` placeholders that Compose read as values; they were blanked, which showed `RESEND_API_KEY`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SENTRY_DSN` and the Better Stack, S3 and WAL-G entries were never filled in),
a sourced risk-free rate, and the domain: `renti.tech` in OVH needs DNS records and a TLS certificate before the `public`
profile (Caddy) may run, which is the owner's authorisation (`docs/RUNBOOK-DEPLOY.md` section 6).

**Domain and TLS, 2026-10-14:** with the owner's authorisation, `renti.tech` (OVH zone) now points its apex and `www` `A`
records at the VPS-3 IPv4 (TTL 300; they held OVH's parking address before) through the OVH CLI. Caddy (`--profile public`) obtained a
Let's Encrypt certificate for `renti.tech` (valid to 2027-01-12, renewed automatically). `https://renti.tech/api/health` answers 200,
`/readyz` and `/` answer 404, port 80 redirects to https. `PUBLIC_APP_URL=https://renti.tech` and `PUBLIC_HOST=renti.tech` are set on the
host, and `check_env.py` (without `--private`) leaves one error: no `RESEND_API_KEY`. **Still not usable by people:** no Resend key and
verified sender (the zone's SPF is OVH's own, so Resend's records still have to be added), no Google client, placeholder risk-free rate.
The repository is still public (PRE-DEPLOYMENT section 0). The OVH API credentials used for this were pasted into a chat and must be revoked.

Historical B-016 checks concern the old Prague VPS-1, `vps-ee6fa92e.vps.ovh.net`
(`SERVER_V1_NAME`), shown Stopped in the owner's screenshot. Its SSH/KVM/reboot errors
are not evidence about the current target.

## Local Docker (developer machine, not the beta host)

| Date | Commit | Result | Journey evidence |
|---|---|---|---|
| 2026-10-14 | `bc4825d` + RM-15 branch | amd64 Compose stack (`DOCKER_DEFAULT_PLATFORM=linux/amd64`): `make smoke` OK with the audit and ops worker lanes | `journey_check.py`: ok, events `progress x5, done`, `succeeded_degraded` (no vision), result equals the engine run in-process, 1.97 s, rows cleaned up. Fake provider data |
| 2026-10-14 | same | VPS overlay `compose.prod.yml` (secrets and env_file replaced by test values): all four services healthy, root filesystem read-only, no capabilities (`CapEff=0`), non-root, api 280 MiB of 512, worker-audit 87 MiB of 1.5 G | `journey_check.py`: ok, 1.56 s, cleaned up. Fake provider data |
| 2026-10-14 | same | `backup_db.sh` then `restore_drill.sh`: OK in 1 s, 30 tables with identical row counts | logical dump only (L-014) |

Note: the native arm64 image crashes at import (`cryptography` 50.0.2 wheel, SIGILL) under Docker Desktop on this Mac; the
x86_64 image (the VPS architecture) runs. See `docs/LIMITATIONS.md` L-021.
