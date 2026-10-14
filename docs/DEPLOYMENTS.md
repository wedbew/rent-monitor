# Deployments

One row per deployment of a merged `staging` commit to a host. Evidence class matters: **fake provider data** (planted
listing and comparables, real API/queue/worker/Postgres/engine) is not **real provider** evidence (an owner-authorised live
run). See `docs/RUNBOOK-DEPLOY.md`.

## OVH VPS-1 (private beta)

| Date | Commit | Result | Journey evidence |
|---|---|---|---|
| none yet | | SSH to the host times out in the banner exchange; see `docs/BLOCKERS.md` B-016 | |

## Local Docker (developer machine, not the beta host)

| Date | Commit | Result | Journey evidence |
|---|---|---|---|
| 2026-10-14 | `bc4825d` + RM-15 branch | amd64 Compose stack (`DOCKER_DEFAULT_PLATFORM=linux/amd64`): `make smoke` OK with the audit and ops worker lanes | `journey_check.py`: ok, events `progress x5, done`, `succeeded_degraded` (no vision), result equals the engine run in-process, 1.97 s, rows cleaned up. Fake provider data |
| 2026-10-14 | same | VPS overlay `compose.prod.yml` (secrets and env_file replaced by test values): all four services healthy, root filesystem read-only, no capabilities (`CapEff=0`), non-root, api 280 MiB of 512, worker-audit 87 MiB of 1.5 G | `journey_check.py`: ok, 1.56 s, cleaned up. Fake provider data |
| 2026-10-14 | same | `backup_db.sh` then `restore_drill.sh`: OK in 1 s, 30 tables with identical row counts | logical dump only (L-014) |

Note: the native arm64 image crashes at import (`cryptography` 50.0.2 wheel, SIGILL) under Docker Desktop on this Mac; the
x86_64 image (the VPS architecture) runs. See `docs/LIMITATIONS.md` L-021.
