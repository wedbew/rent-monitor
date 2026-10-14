# Delivery status

**The one place that says what works.** Updated by implementation PRs (`.agent/rules/delivery.md`), not by status-only PRs.
Hourly facts (open PRs, checks, who holds which issue) come from GitHub: `gh issue list --label ready`,
`uv run python scripts/delivery_metrics.py`. **Last verified:** 2026-10-13 against `staging` · by RM-184.

Written for the state after the PR that edits it merges; until then `staging` shows the previous text. Levels: **1** implemented (offline tests, merged) · **2** integrated (journey test through API, queue, Postgres, engine, with named
fakes) · **3** provider-verified (authorised sandbox/live evidence) · **4** launch-ready (release gates). A closed issue is level 1 at most.

## Journey (P0): sign in → submit sale listing → reserve credit → queue → context → engine → persist and retrieve

| Step | Level | Evidence | Missing |
|---|---|---|---|
| Sign in (Google ID token, magic link, sessions) | 1 | `rm_api.auth`, `tests/integration/test_auth.py` (#147); used by the journey test; email/password registration and verification (RM-203, `tests/integration/test_password_register.py`, 17 tests) and password login (RM-204, `tests/integration/test_password_login.py`, 9 tests); recovery and change follow in #205 | Real Google and Resend never exercised (B-004); level 3 open |
| Parse and bound the listing reference | 2 | `rm_core.listing_ref` behind `POST /api/audits` (422 on SSRF-style refs) | none offline |
| Reserve credit, capture/release | 2 | `rm_core.ledger` called by the route and the worker; `tests/integration/test_audit_journey.py` | Plan-allowance path through the audit route is unit-tested in `test_ledger.py` only |
| Queue the analysis | 2 | `ProcrastinateEmailQueue.run_audit` defers `run_audit`; the test runs a real worker on the `audit` queue | Defer failure recovered by `reconcile_queued_audits` (RM-186, real Postgres + worker); proven offline only |
| Acquire listing and context | 1 | Pipeline takes injected `ListingSource` / `ContextProvider`; test uses `FakeSource`, `FakeContext`; Otodom client, snapshots, OSM clients exist | Real Otodom client + market context wired behind `AUDIT_PROVIDERS=real` (RM-187, tested offline against a fake transport and hand-built rental rows); comparable-rent importers (#106 slice 2) and a risk-free rate source (N-12) still missing, so real audits get a refused rent (L-018); live shape confirmed for one sale listing 2026-10-13 (L-005) |
| Run the engine | 2 | `analyse_listing` runs in the worker; API result equals a direct engine run | CAPEX placeholders (L-007); accuracy unmeasured (#94); vision not called, so every success is `succeeded_degraded` |
| Persist and retrieve the canonical result | 2 | `audit.result` + typed columns copied from the analysis; `GET /api/audits/{id}` echoes it | none offline |
| Failure releases the reservation; duplicates do not double-charge; tenant isolation | 2 | Failures inside the pipeline release the charge (RENT, fractional, gone, blocked, drift, crash, slow fetch hitting the deadline, unconfigured worker); 6 simultaneous submits admit one; duplicate delivery settles once; foreign audit is 404. **Recovery (RM-186, `tests/integration/test_audit_recovery.py`, `test_engine_child.py`):** failed enqueue re-deferred then completed; queued past deadline and worker death (`running` past deadline) fail `TIMEOUT` and release; healthy slow run untouched; reconciler idempotent under 3 concurrent runs; worker finish vs reconciler raced 12 times settles exactly once; a hung or dying engine is killed (process group) and releases; cancellation kills the child | Memory cap (`RLIMIT_AS`) is tested on Linux CI only (skipped on macOS); stalled Procrastinate `doing` rows are not cleaned (L-017) |
| Progress stream | 2 | `GET /api/audits/{id}/events` (SSE): replay from `Last-Event-ID`, NOTIFY wake-up with a 15 s safety poll, terminal `done`/`error` written in the same transaction as the status and the credit settlement, finished audits without stored events synthesised, foreign audit 404 (RM-185, `tests/integration/test_audit_events.py`, 10 tests); real Postgres NOTIFY and worker, offline fakes | Stages `vision`/`ocr`/`anchors` are not emitted until those steps exist; open-ended stream behaviour (keep-alive, lost wake-up, disconnect) is tested on the generator, not over a real socket |

**Journey level once #192 is merged: 2, offline** (RM-184, `tests/integration/test_audit_journey.py`, 18 tests; real API, Postgres, ledger,
Procrastinate worker and engine; listing source and market context are named fakes). That is **not** live-provider validation
and not production readiness (L-018). Level 3 needs the owner's authorisation for a live fetch and sourced market data.

## Other capability

| Area | Level | Note |
|---|---|---|
| Platform (settings, logging, problems, health, flags, admin, GDPR export/erase, retention) | 1 | Admin and privacy tools are outside the P0 path |
| Billing (Paddle pilot report packs, BLIK, webhook, credits, accounting) | 0 | Spec only (`docs/PADDLE-INTEGRATION.md`): owner selected one-time 1/5/10-report packs; final pricing, Paddle approval/sandbox and accountant review pending (L-015/L-016). Existing ledger/`has_pro` code is not a Paddle integration |
| Ops (Compose, Caddy, WAL-G, backups, monitors) | 1 partial | Local Compose + smoke (health only, **not** a journey test); Caddy/WAL-G/backups not built |
| Market data, radar, screener | 0 | #106, #48, #49, #16, #21 |
| Frontend | 0 | Phase 2, needs explicit authorisation; design prototypes only |

## Backlog map (reconciled 2026-10-13)

Classes: **V** implemented and verified (offline) · **E** implemented, awaiting external validation · **P** partial · **R** ready ·
**B** blocked (dependency or owner) · **U** umbrella.

| Issue | Class | Next step / blocker |
|---|---|---|
| #13 audits | U, P | #184 merged (#192, offline level 2); #186 recovery merged (#206); #185 SSE merged (#207); #187 adapters in review (RM-187), rental importers and vision/OCR are separate issues |
| #14 billing | U, B | Re-scope to Paddle packs per `PADDLE-INTEGRATION.md`; consumption depends on #184, money-PR review and pack/ledger slices. Paddle sandbox evidence replaces the earlier Stripe B-003 dependency for this pilot; final prices/provider acceptance pending |
| #15 ops | P | Compose done; Caddy, WAL-G, backups deferred (local-first strategy) |
| #16, #21 market batch and routes | B | Wait for #106, #48, #49 |
| #25 worker-ops | P | Part 1 merged (#157); reconciler arrives with #186; pilot payment/adjustment reconciliation with #14 replaces subscription tasks |
| #26, #27 invoices, disputes | B | Re-scope to Paddle invoice access, settlement and pack reversals; wait for #14 and accountant (#41) |
| #28 API contract | P | OpenAPI + drift done (#175); schemathesis after #184; nightly live contract test is owner-authorised only |
| #32-#38 launch gates | B | Cannot run before their subjects exist; #38 is partly covered by auth tests (sign-out-everywhere, unverified link) but gate timing evidence is missing |
| #44 frontend | U, B | Phase 2; owner authorisation required |
| #48, #49 market-data contracts | R (off P0 path) | Fresh-import design; no dependency on P0 |
| #94 accuracy evaluation | B (owner) | Harness is **R** now; needs the owner's labelled listings |
| #106 comparable-rent store | P | Store + sha256 cache done (level 1, offline, real Postgres). Open: fresh importers for rental comparables (`LEGAL[scraping\|third-party-data]`) and the hedonic refinement; slice them before `ready` |
| #39-#43 owner | owner | See *Owner actions* |
| #12, #17, #19, #20, #22, #23, #24, #30, #82, #84-#93, #157, #167 | V or E | Closed; E for those touching Google, Resend, Otodom or OpenRouter live |
| #6, #8, #9 headless autonomy | reopened as P | A headless run producing a merged PR is not yet demonstrated; see #177 |

## Owner actions (exact, smallest first)

1. Approve the money PR for #184 (ledger/quota paths) and the workflow PR #191; head SHAs go in `docs/BLOCKERS.md` *Approved*.
2. ~~Authorise one live Otodom fetch (L-005) and the datacenter-IP test (#42).~~ Done 2026-10-13: one sale listing returned 200 and parsed from the dev machine and from the OVH VPS-1. Single request each; sustained-load blocking is still unmeasured (L-002).
3. Provide the labelled listing set for #94 and CAPEX prices or a data source (B-015, L-007).
4. Paddle pilot: confirm pack prices (recommended 10/40/70 PLN), obtain product/prepaid-report acceptance and sandbox access, and have the accountant review settlement/KSeF treatment. Stripe sandbox (B-003) and recurring-BLIK activation (#39) are no longer pilot dependencies; issue records need reconciliation.
5. Decisions still open: pilot signup-report allowance and unused-report expiry (#43), market-data bootstrap (CONTEXT §9), exit-value anchor (B-014). Monthly Pro allowance is outside this pilot.
6. Approve the workflow PR (CI docs-only filter, dispatcher). Then enable the dispatcher after the canary: `gh variable set ENABLE_DISPATCH --body true`.

## Autonomy

Baseline (audit, 2026-10-13): `claude` workflow 231 runs, 224 skipped by design, 2 success, 2 failure, 3 cancelled; both failures
ended in ~2 s with zero model usage and $0 cost (an execution error before any model turn, logs in run 38182957497), and there is no
merged PR authored by a headless run. Canary results are recorded on #177 and, once the workflow PR lands, in `docs/AUTONOMY.md` *Canary log*.
