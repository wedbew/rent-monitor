# Deploy handoff: Frankfurt VPS-3 (2026-10-14)

Purpose: let an independent agent verify the beta target and the deployment steps without relying on the author's claims.
This records what is known and what is not. The deployment itself is ticket #15; nothing here was deployed or probed.

## Target (owner correction, 2026-10-14)

| Item | Value | Status |
|---|---|---|
| Host | OVH VPS-3, Frankfurt, `vps-d1af13a5` | stated by the owner; not independently verified |
| Old host | OVH VPS-1, Prague, `vps-ee6fa92e` | stopped; B-016 (SSH banner timeout) concerns it only |
| Size | blueprint VPS-3: 12 GB, 6 vCore | inferred; confirm on the host (`free -m`, `nproc`) |
| Access | `deploy` user, owner's key (`.agent/agents.md` §4) | key install on this host unverified |

## Verify first (read-only, in order)

1. `ssh deploy@<host> true` answers within seconds. If the banner times out, stop and add a blocker row; do not retry in a loop (lockout risk).
2. `free -m`, `nproc`, `df -h /`, `uname -m` (the image is x86_64), `docker --version`.
3. `deploy/setup-server.sh` evidence: key-only SSH, UFW 22/80/443, swap, Docker (`docs/RUNBOOK-DEPLOY.md` §0).
4. DNS and firewall untouched; public exposure is out of scope.

## Deploy (only a merged, green `staging` commit)

Follow `docs/RUNBOOK-DEPLOY.md`. The limits in `deploy/compose.prod.yml` are the 4 GB values; raising them is a decision for
#15, not part of this handoff. Run `scripts/check_env.py` (never print `.env` values), then `scripts/journey_check.py`; record
date, commit and result in `docs/DEPLOYMENTS.md` and `docs/STATUS.md`. Fake-provider evidence is not live-provider evidence.

## Do not

- Read `.env` on the server, or put live provider keys or customer data on it (`docs/PRE-DEPLOYMENT.md` §0).
- Wipe volumes, reinstall the OS, or change firewall, SSH or DNS without the owner's yes.
- Tick `docs/PRE-DEPLOYMENT.md` items without evidence; the datacenter-IP check (L-002) must be repeated from this host.
