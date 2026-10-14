# Delivery status

**The one place that says what works.** Updated by implementation PRs (`.agent/rules/delivery.md`), not by status-only PRs.
Hourly facts (open PRs, checks, who holds which issue) come from GitHub: `gh issue list --label ready`,
`uv run python scripts/delivery_metrics.py`. **Last verified:** 2026-10-13 against `staging` · by RM-184.

Written for the state after the PR that edits it merges; until then `staging` shows the previous text. Levels: **1** implemented (offline tests, merged) · **2** integrated (journey test through API, queue, Postgres, engine, with named
fakes) · **3** provider-verified (authorised sandbox/live evidence) · **4** launch-ready (release gates). A closed issue is level 1 at most.

## Journey (P0): sign in → submit sale listing → reserve credit → queue → context → engine → persist and retrieve

| Step | Level | Evidence | Missing |
|---|---|---|---|
| Sign in (Google ID token, magic link, sessions) | 1 | `rm_api.auth`, `tests/integration/test_auth.py` (#147); used by the journey test; email/password registration and verification (RM-203, `tests/integration/test_password_register.py`, 17 tests) and password login (RM-204, `tests/integration/test_password_login.py`, 9 tests) and recovery and change (RM-205, `tests/integration/test_password_recovery.py`, 12 tests) | Real Google and Resend never exercised (B-004); level 3 open |
| Parse and bound the listing reference | 2 | `rm_core.listing_ref` behind `POST /api/audits` (422 on SSRF-style refs) | none offline |
| Reserve credit, capture/release | 2 | `rm_core.ledger` called by the route and the worker; `tests/integration/test_audit_journey.py` | Plan-allowance path through the audit route is unit-tested in `test_ledger.py` only |
| Queue the analysis | 2 | `ProcrastinateEmailQueue.run_audit` defers `run_audit`; the test runs a real worker on the `audit` queue | Defer failure recovered by `reconcile_queued_audits` (RM-186, real Postgres + worker); proven offline only |
| Acquire listing and context | 1 | Pipeline takes injected `ListingSource` / `ContextProvider`; test uses `FakeSource`, `FakeContext`; Otodom client, snapshots, OSM clients exist | Real Otodom client + market context wired behind `AUDIT_PROVIDERS=real` (RM-187, tested offline against a fake transport and hand-built rental rows); comparable-rent importers (#106 slice 2) and a risk-free rate source (N-12) still missing, so real audits get a refused rent (L-018); live shape confirmed for one sale listing 2026-10-13 (L-005) |
| Run the engine | 2 | `analyse_listing` runs in the worker; API result equals a direct engine run | CAPEX placeholders (L-007); accuracy unmeasured (#94); vision not called, so every success is `succeeded_degraded` |
| Persist and retrieve the canonical result | 2 | `audit.result` + typed columns copied from the analysis; `GET /api/audits/{id}` echoes it | none offline |
| Failure releases the reservation; duplicates do not double-charge; tenant isolation | 2 | Failures inside the pipeline release the charge (RENT, fractional, gone, blocked, drift, crash, slow fetch hitting the deadline, unconfigured worker); 6 simultaneous submits admit one; duplicate delivery settles once; foreign audit is 404. **Recovery (RM-186, `tests/integration/test_audit_recovery.py`, `test_engine_child.py`):** failed enqueue re-deferred then completed; queued past deadline and worker death (`running` past deadline) fail `TIMEOUT` and release; healthy slow run untouched; reconciler idempotent under 3 concurrent runs; worker finish vs reconciler raced 12 times settles exactly once; a hung or dying engine is killed (process group) and releases; cancellation kills the child | Memory cap (`RLIMIT_AS`) is tested on Linux CI only (skipped on macOS); stalled Procrastinate `doing` rows are not cleaned (L-017) |
| Progress stream | 2 | `GET /api/audits/{id}/events` (SSE): replay from `Last-Event-ID`, NOTIFY wake-up with a 15 s safety poll, terminal `done`/`error` written in the same transaction as the status and the credit settlement, finished audits without stored events synthesised, foreign audit 404 (RM-185, `tests/integration/test_audit_events.py`, 10 tests); real Postgres NOTIFY and worker, offline fakes | Stages `vision`/`ocr`/`anchors` are not emitted until those steps exist; open-ended stream behaviour (keep-alive, lost wake-up, disconnect) is tested on the generator, not over a real socket |

**Journey level: 2, offline** (RM-184 to RM-187: `tests/integration/test_audit_journey.py`, `test_audit_recovery.py`, `test_audit_events.py`, `test_audit_context.py`; real API, Postgres, ledger, Procrastinate worker, engine child and, with `AUDIT_PROVIDERS=real`, the Otodom client and market context behind a fake HTTP transport and hand-built rental rows). The same journey ran against the amd64 Compose stack on 2026-10-14 (`scripts/journey_check.py`, fake provider data, see `docs/DEPLOYMENTS.md`); **it also ran on the private beta host VPS-3 (`vps-d1af13a5.vps.ovh.net`, commit `3cdf0be`, 2026-10-14, fake provider data) and one live Otodom request from Frankfurt returned 200 (see `docs/DEPLOYMENTS.md`).** That is **not** live-provider validation
and not production readiness (L-018). Level 3 needs the owner's authorisation for a live fetch and sourced market data.

## Other capability

| Area | Level | Note |
|---|---|---|
| Platform (settings, logging, problems, health, flags, admin, GDPR export/erase, retention) | 1 | Admin and privacy tools are outside the P0 path |
| Ops (Compose, Caddy, WAL-G, backups, monitors) | 1 partial | Local Compose + smoke on separate audit and ops worker lanes; VPS-1 overlay with limits and hardening, secret-safe `check_env.py`, deployed-journey check (`journey_check.py`, fake-provider evidence, run on the local amd64 stack 2026-10-14, see `docs/DEPLOYMENTS.md`), logical backup and restore drill (L-014), runbook | **VPS-3 runs `3cdf0be` privately (api, two workers, Postgres healthy; journey check and restore drill passed on the host; nightly dump cron installed). Not usable by people yet: no verified mail sender, no provider keys, placeholder risk-free rate, no domain or TLS. B-016 concerns the old VPS-1.** Caddy/TLS is the opt-in public profile, untested against a domain; WAL-G, offsite backup, gate 4-6 evidence missing |
| Billing (Paddle pilot report packs, BLIK, webhook, credits, accounting) | 0 | Foundation merged as RM-215 (catalog from owner-approved snapshots only, injectable Paddle client with fake, disabled by default; `tests/unit/test_paddle_catalog.py`). Credit lots with provenance and the fixed lock order merged as RM-216 (`tests/integration/test_pack_lots.py`, hypothesis over operation sequences, concurrency, backfill migration test). Checkout intents with idempotency and ambiguous-creation recovery against a fake Paddle merged as RM-217 (`tests/integration/test_billing_checkout.py`, 21 tests). Signed durable webhook, grant worker and reconciliation against a fake Paddle merged as RM-218 (`tests/integration/test_paddle_webhook.py`, 27 tests, `tests/unit/test_paddle_signature.py`, 20). Provider refunds, chargebacks and their reversals applied to granted packs, with a billing hold for spent units, merged as RM-219 (`tests/integration/test_pack_reversals.py`, 11 tests, `tests/unit/test_billing_reversal_rules.py`). Support-initiated refunds (durable intent, used packs to review) and buyer invoice access merged as RM-229 (`tests/integration/test_pack_refunds.py`, 12 tests). **Billing is level 2 offline end to end; sandbox evidence (#220), the owner's price and allowance decisions (#43), Paddle acceptance and the accountant (L-015, L-016) are open, so nothing is sellable.** Spec (`docs/PADDLE-INTEGRATION.md`): owner selected one-time 1/5/10-report packs; final pricing, Paddle approval/sandbox and accountant review pending (L-015/L-016). Existing ledger/`has_pro` code is not a Paddle integration |
| Market data, radar, screener | 0 | #106, #48, #49, #16, #21 |
| Frontend | 0 | Phase 2, needs explicit authorisation; design prototypes only |

## Backlog map (reconciled 2026-10-13)

Classes: **V** implemented and verified (offline) · **E** implemented, awaiting external validation · **P** partial · **R** ready ·
**B** blocked (dependency or owner) · **U** umbrella.

| Issue | Class | Next step / blocker |
|---|---|---|
| #13 audits | U, P | #184, #185, #186, #187 merged (offline level 2). Open: rental importers #209, risk-free source #210, vision/OCR #211, live-provider evidence (owner), journey on the current VPS-3 |
| #14 billing | U, P | Paddle packs per `PADDLE-INTEGRATION.md`: P1-P5b merged offline (#215-#219, #229); P6 sandbox and acceptance #220 is owner-side. Nothing is sellable until the owner's prices, Paddle acceptance and the accountant |
| #15 ops | P | Offline preparation merged (#223: worker lanes, VPS overlay, env check, journey check, logical backup, runbook). Open: private env verification and deployment to the current VPS-3, public profile, WAL-G and offsite backup, gates 4-6 |
| #16, #21 market batch and routes | B | Wait for #106, #48, #49 |
| #25 worker-ops | P | Part 1 merged (#157); audit reconciler merged (#206); billing sweep and reconciliation merged (#228, #230) |
| #26, #27 invoices, disputes | P | Paddle invoice access (#231) and provider reversals (#230) merged offline; settlement and KSeF wait for the accountant (#41) |
| #28 API contract | P | OpenAPI + drift done (#175); schemathesis after #184; nightly live contract test is owner-authorised only |
| #32-#38 launch gates | B | Cannot run before their subjects exist; #38 is partly covered by auth tests (sign-out-everywhere, unverified link) but gate timing evidence is missing |
| #44 frontend | U, B | Phase 2; owner authorisation required |
| #48, #49 market-data contracts | R (off P0 path) | Fresh-import design; no dependency on P0 |
| #94 accuracy evaluation | B (owner) | Harness is **R** now; needs the owner's labelled listings |
| #106 comparable-rent store | P | Store + sha256 cache done (level 1, offline, real Postgres). Open: rental importers #209 (`LEGAL[scraping\|third-party-data]`), hedonic refinement |
| #39-#43 owner | owner | See *Owner actions* |
| #12, #17, #19, #20, #22, #23, #24, #30, #82, #84-#93, #157, #167 | V or E | Closed; E for those touching Google, Resend, Otodom or OpenRouter live |
| #6, #8, #9 headless autonomy | reopened as P | A headless run producing a merged PR is not yet demonstrated; see #177 |

## Owner actions (exact, smallest first)

1. ~~Approve the money PR for #184.~~ Done: the owner gave standing authorisation for backend work including auth, ledger and billing on 2026-10-14 (`docs/BLOCKERS.md` *Approved*). Still yours: the workflow PR #191.
1a. **Current VPS:** `vps-d1af13a5.vps.ovh.net` (`SERVER_NAME`), VPS-3 in Frankfurt, Active in the owner's 2026-10-14 screenshot. Codex authenticated as `deploy` with the existing key and inspected Docker/Compose, swap and the older checkout. Deployed 2026-10-14; remaining owner steps are in `docs/DEPLOYMENTS.md` (Resend domain, provider keys, risk-free rate, DNS and certificate for `renti.tech`). B-016 concerns the old stopped VPS-1 (`SERVER_V1_NAME`), not this target; no reboot of the new host is indicated by this evidence.
2. ~~Authorise one live Otodom fetch (L-005) and the datacenter-IP test (#42).~~ Done 2026-10-13: one sale listing returned 200 and parsed from the dev machine and from the OVH VPS-1. Single request each; sustained-load blocking is still unmeasured (L-002).
3. Provide the labelled listing set for #94 and CAPEX prices or a data source (B-015, L-007).
4. Paddle pilot: confirm pack prices (recommended 10/40/70 PLN), obtain product/prepaid-report acceptance and sandbox access, and have the accountant review settlement/KSeF treatment. Stripe sandbox (B-003) and recurring-BLIK activation (#39) are no longer pilot dependencies; issue records need reconciliation.
5. Decisions still open: pilot signup-report allowance and unused-report expiry (#43), market-data bootstrap (CONTEXT §9), exit-value anchor (B-014). Monthly Pro allowance is outside this pilot.
6. Approve the workflow PR (CI docs-only filter, dispatcher). Then enable the dispatcher after the canary: `gh variable set ENABLE_DISPATCH --body true`.

## Autonomy

Baseline (audit, 2026-10-13): `claude` workflow 231 runs, 224 skipped by design, 2 success, 2 failure, 3 cancelled; both failures
ended in ~2 s with zero model usage and $0 cost (an execution error before any model turn, logs in run 38182957497), and there is no
merged PR authored by a headless run. Canary results are recorded on #177 and, once the workflow PR lands, in `docs/AUTONOMY.md` *Canary log*.
