# Claude deployment handoff — independent verification

Verified by Codex on 2026-10-14; local checks around 11:28 and current-host checks around 12:35 Europe/Warsaw.
Scope: check the supplied summary, verify beta-host reachability, test the owner's Otodom URL,
and prepare deployment instructions. No deployment, reboot, DNS change, provider payment, real
email delivery, or live customer-data write was performed. Host `.env` permissions were
restricted from 664 to 600 without reading its contents. These are local handoff notes, not a
new declaration of launch readiness in STATUS.md.

## Critical owner correction — use the new VPS

**Current deployment target: `vps-d1af13a5.vps.ovh.net` (`SERVER_NAME`).**
The owner clarified this at approximately 12:25 and supplied OVH Manager screenshots.
It is Active, VPS-3 2027, 6 vCores, 12 GB RAM, 100 GB storage, Ubuntu 26.04,
Frankfurt (DE), OpenStack region `os-de2`. The screenshot shows commitment date 2026-10-13;
billing, renewal and backup activation have not been independently checked.

**Legacy host: `vps-ee6fa92e.vps.ovh.net` (`SERVER_V1_NAME`).** The screenshot shows it
Stopped. It is the older 4 GB Prague VPS. Every earlier SSH/KVM/reboot diagnosis below
concerns that legacy host and must not be used as evidence about the current target.
The previous deployment instructions incorrectly treated it as current.

Codex checked the new hostname: port 22 immediately returned
`SSH-2.0-OpenSSH_10.2p1 Ubuntu-2ubuntu3.7`. The first batch login stopped at host-key
verification. The owner then accepted its ED25519 host key (already known locally by the
host's IP); their password-only `ubuntu` login was rejected with `Permission denied (publickey)`.
Codex's existing-key `ubuntu` login also failed. **Existing-key login as `deploy` succeeded.**
No SSH-agent identities were loaded; the client's existing on-disk keys supplied authentication.
Do not disable public-key authentication or try to re-enable passwords to fix access.

Next connection (owner's Terminal):

```bash
ssh deploy@vps-d1af13a5.vps.ovh.net
```

Authenticated current-host findings:

| Check | Result |
|---|---|
| Account | `deploy`, UID 1001, member of `docker` group |
| Architecture | `x86_64` |
| RAM | 11671 MiB total, approximately 11017 MiB available at inspection |
| Swap | 2 GiB `/swapfile`, unused; `vm.swappiness=10` |
| Disk | 96 GiB filesystem, 91 GiB available |
| Docker / Compose | 29.9.0 / v5.6.0 |
| Running Docker containers | None |
| App Docker images | No `rentmonitor-py` image listed |
| `/opt/rent-monitor` | Clean Git checkout at `4127f793e4903480fa0a22e72c3bd7fc0fb1cdfb`, behind verified target `3cdf0be` |
| Host `uv` | Not found in the noninteractive SSH PATH; use the built image for the env checker |
| Host `.env` | Exists, owned by `deploy`; mode was 664 and Codex restricted it to 600. Contents were not read or changed |

No app image was built, no service was started, no host reboot or SSH/firewall change was
performed on the new host. The deployed journey and Frankfurt Otodom transport test remain
pending. Do not treat absence of running Docker containers as a full system-service inventory.

The existing 4 GB Compose resource limits fit the 12 GB host as conservative initial
limits; do not increase concurrency or claim gate-4 measurements just because RAM grew.
Re-run Otodom reachability and the deployed journey on the new host: Prague/IP evidence
does not validate Frankfurt. **B-016's legacy-host recovery is not the new-host deploy
blocker.** Authenticated deploy access now works. Remaining work: verify effective private
environment prerequisites, fetch the merged commit, build/bootstrap/start, and collect host
journey/provider evidence. SSH service and firewall hardening were not independently audited.

## Historical legacy-host investigation — superseded as deployment target

**B-016 remains open.** One network-enabled SSH attempt to
`deploy@vps-ee6fa92e.vps.ovh.net` ended `Connection timed out during banner exchange`.
One TCP check each on ports 80 and 443 returned connection refused. Authentication was never
reached; this does not diagnose the underlying cause or exclude network filtering/fail2ban.
No further SSH attempts were made. The initial sandbox-only attempt could not resolve DNS and
was not a connection to the host.

OVH Manager/KVM could not be operated: the native browser tool returned
`Computer Use permissions are not granted`. No OVH credentials were read and no reboot was
submitted. The owner must reboot this VPS in OVH Manager, or provide usable Manager access.
Follow-up: the owner authorized using the OVH CLI. `ovhcloud` is installed, but
`ovhcloud vps get` reported an uninitialized API client with missing authentication.
The profile-name listing shows only `default`. No credential/configuration values were
read. The owner can run `ovhcloud login` and complete OVH authorization; then the agent can
execute `ovhcloud vps reboot vps-ee6fa92e.vps.ovh.net --wait` and check SSH recovery.
No reboot was submitted through the CLI.
Later owner evidence (11:47:36 Europe/Warsaw): `ovhcloud vps reboot ... --wait`
printed “reboot started”, then failed polling with `403 Client::Forbidden` /
“This call has not been granted”. The official CLI prints that message only after a
successful reboot POST; its waiter performs GET `/v1/vps/{serviceName}/tasks/{id}`.
The request was accepted, but completion is unconfirmed. Do not submit another reboot
just to fix polling. The token needs read permission on the task endpoint to use `--wait`.
Codex's process still lacks CLI authentication, so owner-shell credentials are not
available here. Unauthenticated SSH-banner checks at approximately 11:48 and 11:49
both timed out; no authentication attempts were made.
At 11:52:20 the owner reported `ssh ubuntu@...` failing with `No route to host`.
A subsequent Codex IPv4 TCP check timed out before connecting to port 22, unlike the
earlier accepted TCP connection with no banner. This establishes a reachability failure,
not its cause. Inspect the accepted reboot task in Manager and use KVM to distinguish
boot failure from guest-network/firewall/SSH failure before changing configuration.
The owner subsequently obtained a KVM console URL through `ovhcloud vps get-console-url`.
Codex opened it in the in-app browser: noVNC reported “Something went wrong, connection
is closed”; one reload had the same result. No guest screen or login prompt was visible.
This does not distinguish expired console authorization, browser connectivity, or provider
console/VM failure. Generate a fresh link and open it immediately in the owner's Chrome;
if that also fails, verify reboot state in Manager and ask OVH support to inspect the VM.
Console bearer tokens are intentionally omitted from these notes.
At 12:17 the owner reported 403 for both VPS GET and task listing. This confirms their
current API authorization lacks those read calls; a successful console/reboot call does
not grant general VPS read access. A subsequent Codex network check returned local
`Network is unreachable`; VM state remains unknown. A restricted diagnostic token with
GET `/vps/vps-ee6fa92e.vps.ovh.net` and GET `/vps/vps-ee6fa92e.vps.ovh.net/*` covers
state, the getter's datacenter lookup, and tasks. Configure it privately in the owner's
shell using OVH's documented credential environment variables, or inspect Manager instead.
If SSH still does not answer afterward, use KVM to inspect the host and run
`sudo systemctl restart ssh` as the recovery step from B-016. Inspect `ssh`, `ssh.socket`,
listening port 22, firewall and fail2ban status if necessary; do not change SSH/firewall policy
or reinstall the host without the owner's approval.

Host architecture, installed Docker, swap, hardening, checkout and current application state
could not be inspected. “Nothing deployed” remains the previous agent's recorded evidence;
this session confirms inaccessible SSH and closed HTTP ports, not an inventory of the host.

## Summary audit

| Claim | Independent finding |
|---|---|
| Merged staging HEAD `3cdf0be` | Confirmed: clean local checkout and GitHub staging both at `3cdf0be13d8bb93dafaec24287f93b6c73c2783f`; staging protection active |
| Journey #184 / PR #192 | PR #192 merged, all eight latest PR check results successful; journey integration tests pass locally |
| Recovery #186 / PR #206 | Merged; tests for redefer, expired queued/running audits, races and single settlement passed in the full suite |
| SSE #185 / PR #207 | Merged; replay, notification, tenant isolation, terminal events and generator disconnect/poll tests passed |
| Real adapters #187 / PR #208 | Merged; wiring and fake-transport/context tests pass. Live fetch/extraction of the supplied URL also passed in this session; live market context remains unverified |
| Password auth #201–#205 | Specs and implementation PRs #212–#214 merged; registration/login/recovery tests passed. Google/Resend provider operation was not tested |
| Paddle packs #215–#219, #229 | PRs #222, #225, #226, #228, #230, #231 merged with successful latest checks; offline catalog, checkout, webhook, provenance, reversal, refund and invoice tests pass. No Paddle sandbox/live transaction was made |
| Account-erasure FK fix | Confirmed in `rm_core.privacy.delete_account`: clears `BillingPurchase.grant_ledger_id` before deleting tenant ledger rows. Pack erasure integration test passes |
| Deployment preparation | Actual merged preparation PR is **#223**, commit `35aad11`. The stale STATUS.md reference to #224 was corrected locally |
| VPS permission edit included in #223 | Confirmed from the commit diff of `.agent/agents.md`. This session did not reconstruct the staging command used to create that commit |
| Replacement webhook PR | #227 is closed, its security check failed, and #228 is merged with successful security. The false-positive diagnosis and old-branch deletion were not independently revalidated |
| Workflow PR #191 open | Confirmed; untouched in this session |
| Owner approval record | Standing authorization exists in BLOCKERS.md. Historical chat approvals were not independently re-read; the awaiting-approval row for already-merged #192 is stale |
| Local deployment/backup evidence | Prior records are for `bc4825d` plus the deployment branch, before final billing merges. New current-source reproduction is recorded below |
| arm64 cryptography crash L-021 | Recorded in LIMITATIONS.md; not reproduced here. App containers used amd64 |
| Public Caddy/TLS config validation | Configuration exists; public TLS/domain behavior was not exercised here |
| WAL-G/offsite backup missing | Confirmed by scripts/runbook scope: logical dumps and scratch restores only |
| Owner items still open | GitHub issues #41, #43, #209, #210, #211 and #220 remain open |

**CI wording correction:** the live staging ruleset requires **seven** checks: lint, types,
test, security, pr-title, migrations, invariants. Eight checks succeeded on the reported
merged PRs; `types-ty-trial` is the additional check. Successful check completion timestamps
precede the reported merges for the handoff's merged PRs.

Merged-commit CI is green:
[CI](https://github.com/wedbew/rent-monitor/actions/runs/38540216802),
[security](https://github.com/wedbew/rent-monitor/actions/runs/38540218431).
CI logs report 1163 tests passed, 43 invariants passed, 5 migration tests passed, and clean
pyright. The local Linux-only skip is absent from the Linux CI suite.

## Checks rerun locally at the merged commit

| Command | Result |
|---|---|
| `uv run pytest -m 'not e2e' -q` | 1162 passed, 1 skipped in 83.33 s; skip is `test_engine_child.py` Linux RLIMIT_AS test |
| `uv run pytest -m invariant -q` | 43 passed, 1120 deselected in 3.48 s |
| `uv run pyright` | 0 errors, 0 warnings, 0 informations |

Neither `make ci` nor `make ci-full` was rerun by Codex. Historical claims of running
`make ci` before each push cannot be proved from this checkout alone.

## Owner's listing: real fetch and extraction

[Otodom listing](https://www.otodom.pl/pl/oferta/torun-starowka-przedzamcze-16-42-m-lokal-inwestycyjny-ID4D73T)

One live request used the application's `CurlCffiTransport`, normalized reference `ID4D73T`,
`classify`, and `extract_listing`; 30 s total budget, no application retry loop, no storage.
Only bounded listing fields were printed; seller names, contact data, description and full
payload were not saved or printed. No images/OCR/paid provider calls were made.

```json
{
  "evidence_class": "one-live-dev-machine-fetch-and-extraction",
  "ref": "ID4D73T",
  "http_status": 200,
  "bytes": 545693,
  "classify": "OK",
  "category_type": "SELL",
  "category_name": "FLAT",
  "extract": "OK",
  "listing": {
    "kind": "SALE",
    "price_pln": "219000",
    "area_m2": "16.42",
    "rooms": 1,
    "admin_fee_pln": "320",
    "city": "Toruń",
    "warnings": ["build_year_missing"]
  }
}
```

The generic web tool separately returned 403 for the full URL. The application transport
succeeded from this Mac; neither observation establishes reachability from the VPS.

This was **not a complete real-provider audit or investment report**. Without imported
rent comparables, `MarketContext` supplies the engine's refused rent estimate; without
`RISK_FREE_RATE`, the audit fails `CONTEXT_UNAVAILABLE` and releases its credit. Vision is
not invoked, so successful audits are degraded. Do not invent rent, a risk-free rate or a
meaningful Max Bid for this listing. Recheck this URL through the deployed worker only
after the required inputs are supplied; record fetch and whole-journey evidence separately.

## New isolated local Compose evidence

Current source at `3cdf0be` was mounted read-only into cached `rentmonitor-py:local`
amd64 runtime containers. The lockfile is unchanged since `bc4825d`. Postgres 17 used the
cached native arm64 image. Resource limits and application hardening came from the VPS
overlay. Project `rm-codex-verification` used a new local database volume and loopback API
port 18081; existing services were untouched. No owner `.env` was loaded: Compose used
`--env-file /dev/null`, service `env_file` entries were removed, and all credentials were
disposable test values. Mail, billing and telemetry were disabled. The rate `0.05` was a
**synthetic test-only input**, not an owner-approved beta/production rate.

A fresh image build was attempted but stopped when registry/base-image resolution stalled.
This is current-source runtime evidence, **not a successful fresh build of the deployment
image**, and not a fully amd64 stack or a VPS resource/load measurement.

`scripts/journey_check.py` returned:

```json
{
  "run_id": "3f0e9e41",
  "evidence_class": "fake-provider-data",
  "events": ["progress", "progress", "progress", "progress", "progress", "done"],
  "stages": ["fetch", "extract", "context", "synthesize", "persist", "persist"],
  "status": "succeeded_degraded",
  "error_code": "VISION_UNAVAILABLE",
  "grade": "E",
  "result_matches_engine": true,
  "elapsed_s": 1.56,
  "ok": true,
  "cleaned_up": true
}
```

API/audit-worker/ops-worker: `read_only=true`, `cap_drop=[ALL]`,
`no-new-privileges=true`, user `app`, limits 512/1536/256 MiB respectively.
API effective capabilities were zero. **These hardening properties apply to app containers;
the production overlay does not apply the same read-only/capability block to Postgres.**
Post-run memory snapshot: Postgres 76.82 MiB/1 GiB, API 261.9 MiB/512 MiB,
audit worker 88.72 MiB/1.5 GiB, ops worker 87.08 MiB/256 MiB. This is a snapshot, not
`memory.peak` or release gate 4 evidence.

Logical backup: 137231-byte dump; scratch restore: **36 app tables with identical exact
row counts, 1 s**. This does not establish point-in-time recovery, offsite durability,
queue-table comparison, a fresh-host RTO, or release gate 6. The stack is stopped after
verification; its disposable local volume is retained. Temporary configuration and dump
are removed after verification.

## Concrete deployment instructions for Claude — new VPS target

1. Read `.agent/agents.md`, `docs/PRE-DEPLOYMENT.md`, `docs/BLOCKERS.md` and
   `docs/RUNBOOK-DEPLOY.md`. Resume #15 on `vps-d1af13a5.vps.ovh.net`; its SSH banner
   already answers and **existing-key access as `deploy` works**. The checkout, Docker
   and swap already exist; inspect remaining effective settings. Keep deployment private and
   do not change workflows, DNS, firewall or SSH policy without the required authorization.
2. Verify host architecture, Docker/Compose version, swap, disk space and existing checkout
   without reading `.env`. Do not blindly rerun `setup-server.sh`: it changes SSH/firewall
   policy and restarts Docker. Inspect what already ran first. Compose must support
   `!override` and optional `env_file` syntax (Compose 2.24.4+;
   [Docker merge documentation](https://docs.docker.com/reference/compose-file/merge/)).
3. Fetch staging, verify the chosen SHA is merged and its CI is green. The verified target
   is `3cdf0be13d8bb93dafaec24287f93b6c73c2783f`. Recheck if staging has moved.
4. Resolve configuration prerequisites **before calling this beta usable**:
   owner-controlled secret provisioning, verified Resend sender, real rate with provenance,
   `AUDIT_PROVIDERS=real`, and `BILLING_PROVIDER=disabled`. Google client ID is a checker
   warning if absent, not a prerequisite for password-only authentication. Actual mail
   operation still needs verification. The repo is currently PUBLIC and PRE-DEPLOYMENT §0
   is unticked: follow that owner decision before installing live provider keys/customer data.
5. Use bash for the command block below. `setup-server.sh` does not install host `uv`.
   A checker run inside the built image avoids that dependency and validates the effective
   Compose-derived DSNs, instead of the localhost DSNs copied from `.env.example`.

```bash
cd /opt/rent-monitor
git fetch origin staging
git checkout --detach 3cdf0be13d8bb93dafaec24287f93b6c73c2783f
git merge-base --is-ancestor HEAD origin/staging
export IMAGE_TAG="$(git rev-parse --short HEAD)"
dc() { docker compose -f deploy/compose.yml -f deploy/compose.prod.yml "$@"; }
dc build
dc run --rm --no-deps --entrypoint python api scripts/check_env.py --private
# Continue only with zero checker errors and the owner prerequisites resolved.
dc run --rm bootstrap
dc up -d --wait postgres api worker-audit worker-ops
dc ps
dc exec -T api python scripts/journey_check.py --base-url http://localhost:8000
```

The checker may warn without Sentry; record accepted monitoring gaps. Never print
`docker compose config`, `docker inspect` environment arrays, host `.env`, session tokens
or provider secrets. Set the database password before the first Postgres volume start;
changing only the file later does not change the database role password.

6. Confirm `/api/health`, `/readyz`, worker liveness and queue processing. Workers have no
   explicit healthchecks in Compose; “up --wait says healthy” is not enough. Require journey
   `ok`, engine equality and cleanup. Test private browser auth through
   `ssh -L 8000:127.0.0.1:8000 deploy@vps-d1af13a5.vps.ovh.net`, with matching
   `PUBLIC_APP_URL=http://localhost:8000`; the journey checker supplies its cookie manually
   and does not verify a browser's handling of production Secure/__Host cookies over HTTP.
7. Provision a deploy-owned backup directory and actually install/verify the nightly job:
   the runbook describes cron but does not install it. Run logical backup + scratch restore;
   record resulting evidence, not a gate-6 completion. Preserve previous image for rollback;
   no `down -v`, live-DB restore or volume wipe.
8. Record host/date/SHA/result and redacted journey JSON in DEPLOYMENTS.md and STATUS.md
   according to the repo workflow. Reconcile B-016 as a legacy-host issue; do not claim
   the old VPS recovered when only the new VPS was tested.
   Keep real Otodom and sourced-market tests distinct from the planted journey check.

Other docs needing reconciliation in a future authorized change: STATUS.md's last-verified
header and Billing level-0 row contradict newer evidence/text; BLOCKERS.md retains stale
auth/invariant descriptions; deploy/README.md and INFRASTRUCTURE.md describe a separate
night-only batch worker, whereas current Compose runs `worker-ops` on `ops,batch` continuously.
PRE-DEPLOYMENT still contains Stripe/BLIK/Fakturownia launch gates despite the Paddle pilot.
Reconcile those with the approved product/spec decisions; do not silently waive release gates.

Paid launch remains blocked by owner decisions, provider acceptance/sandbox evidence,
legal/accounting review and unfulfilled release gates. No launch checklist item was ticked
by this verification session.
