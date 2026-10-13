# Delivery status

**The one place that says what works.** Updated by implementation PRs (`.agent/rules/delivery.md`), not by status-only PRs.
Hourly facts (open PRs, checks, who holds which issue) come from GitHub: `gh issue list --label ready`,
`uv run python scripts/delivery_metrics.py`. **Last verified:** 2026-10-13 against `staging` · by RM-184.

Written for the state after the PR that edits it merges; until then `staging` shows the previous text. Levels: **1** implemented (offline tests, merged) · **2** integrated (journey test through API, queue, Postgres, engine, with named
fakes) · **3** provider-verified (authorised sandbox/live evidence) · **4** launch-ready (release gates). A closed issue is level 1 at most.

## Journey (P0): sign in → submit sale listing → reserve credit → queue → context → engine → persist and retrieve

| Step | Level | Evidence | Missing |
|---|---|---|---|
| Sign in (Google ID token, magic link, sessions) | 1 | `rm_api.auth`, `tests/integration/test_auth.py` (#147); used by the journey test | Real Google and Resend never exercised (B-004); level 3 open |
| Parse and bound the listing reference | 2 | `rm_core.listing_ref` behind `POST /api/audits` (422 on SSRF-style refs) | none offline |
| Reserve credit, capture/release | 2 | `rm_core.ledger` called by the route and the worker; `tests/integration/test_audit_journey.py` | Plan-allowance path through the audit route is unit-tested in `test_ledger.py` only |
| Queue the analysis | 2 | `ProcrastinateEmailQueue.run_audit` defers `run_audit`; the test runs a real worker on the `audit` queue | Reconciler if the defer fails (#186) |
| Acquire listing and context | 1 | Pipeline takes injected `ListingSource` / `ContextProvider`; test uses `FakeSource`, `FakeContext`; Otodom client, snapshots, OSM clients exist | Rent comparables store (#106); real adapters (#187); live shape unverified (L-005) |
| Run the engine | 2 | `analyse_listing` runs in the worker; API result equals a direct engine run | CAPEX placeholders (L-007); accuracy unmeasured (#94); vision not called, so every success is `succeeded_degraded` |
| Persist and retrieve the canonical result | 2 | `audit.result` + typed columns copied from the analysis; `GET /api/audits/{id}` echoes it | none offline |
| Failure releases the reservation; duplicates do not double-charge; tenant isolation | 2 (narrow) | Covered: failures raised inside the async pipeline (RENT, fractional, gone, blocked, payload drift, crash, a slow listing fetch or context call hitting the deadline, unconfigured worker) release the charge; 6 simultaneous submits admit one; duplicate job delivery settles once; foreign audit is 404 | **Not covered:** the defer failing after commit (audit stays `queued`, credit reserved), worker death mid-run (stays `running`), and a blocking engine call (`asyncio.timeout` cannot interrupt synchronous code). All need #186 |
| Progress stream | 0 | `audit_event` table | #185 |

**Journey level once #192 is merged: 2, offline** (RM-184, `tests/integration/test_audit_journey.py`, 18 tests; real API, Postgres, ledger,
Procrastinate worker and engine; listing source and market context are named fakes). That is **not** live-provider validation
and not production readiness (L-015). Level 3 needs the owner's authorisation for a live fetch and sourced market data.

## Other capability

| Area | Level | Note |
|---|---|---|
| Platform (settings, logging, problems, health, flags, admin, GDPR export/erase, retention) | 1 | Admin and privacy tools are outside the P0 path |
| Billing (Stripe, BLIK, webhook, entitlements, VAT) | 0 | Spec only (`docs/STRIPE-SPEC.md`); sandbox access pending (B-003); `has_pro` logic exists |
| Ops (Compose, Caddy, WAL-G, backups, monitors) | 1 partial | Local Compose + smoke (health only, **not** a journey test); Caddy/WAL-G/backups not built |
| Market data, radar, screener | 0 | #106, #48, #49, #16, #21 |
| Frontend | 0 | Phase 2, needs explicit authorisation; design prototypes only |

## Backlog map (reconciled 2026-10-13)

Classes: **V** implemented and verified (offline) · **E** implemented, awaiting external validation · **P** partial · **R** ready ·
**B** blocked (dependency or owner) · **U** umbrella.

| Issue | Class | Next step / blocker |
|---|---|---|
| #13 audits | U, P | #184 = PR #192 (offline level 2, awaiting approval); #185 (SSE) and #186 (recovery) become **R** only after #192 merges; #187 blocked on #106 and live-fetch authorisation |
| #14 billing | U, B | Offline code can start after #184 (needs consumption path) and a money-PR approval; sandbox proof needs B-003. Slice it before `ready` |
| #15 ops | P | Compose done; Caddy, WAL-G, backups deferred (local-first strategy) |
| #16, #21 market batch and routes | B | Wait for #106, #48, #49 |
| #25 worker-ops | P | Part 1 merged (#157); reconciler arrives with #186; subscription tasks with #14 |
| #26, #27 invoices, disputes | B | Wait for #14; accountant (#41) for treatment |
| #28 API contract | P | OpenAPI + drift done (#175); schemathesis after #184; nightly live contract test is owner-authorised only |
| #32-#38 launch gates | B | Cannot run before their subjects exist; #38 is partly covered by auth tests (sign-out-everywhere, unverified link) but gate timing evidence is missing |
| #44 frontend | U, B | Phase 2; owner authorisation required |
| #48, #49 market-data contracts | R (off P0 path) | Fresh-import design; no dependency on P0 |
| #94 accuracy evaluation | B (owner) | Harness is **R** now; needs the owner's labelled listings |
| #106 comparable-rent store | R | Depends on #87 (merged); slice into store + cache first, importers second (LEGAL tags) |
| #39-#43 owner | owner | See *Owner actions* |
| #12, #17, #19, #20, #22, #23, #24, #30, #82, #84-#93, #157, #167 | V or E | Closed; E for those touching Google, Resend, Otodom or OpenRouter live |
| #6, #8, #9 headless autonomy | reopened as P | A headless run producing a merged PR is not yet demonstrated; see #177 |

## Owner actions (exact, smallest first)

1. Approve the money PR for #184 (ledger/quota paths) and the workflow PR #191; head SHAs go in `docs/BLOCKERS.md` *Approved*.
2. Authorise **one** live Otodom listing fetch from a dev machine to settle L-005 (listing shape), and the datacenter-IP test on the VPS (#42).
3. Provide the labelled listing set for #94 and CAPEX prices or a data source (B-015, L-007).
4. Stripe: grant sandbox access (B-003); request BLIK recurring activation (#39, has lead time).
5. Decisions still open: Pro allowance and free-tier scope (#43), market-data bootstrap (CONTEXT §9), exit-value anchor (B-014).
6. Approve the workflow PR (CI docs-only filter, dispatcher). Then enable the dispatcher after the canary: `gh variable set ENABLE_DISPATCH --body true`.

## Autonomy

Baseline (audit, 2026-10-13): `claude` workflow 231 runs, 224 skipped by design, 2 success, 2 failure, 3 cancelled; both failures
ended in ~2 s with zero model usage and $0 cost (an execution error before any model turn, logs in run 38182957497), and there is no
merged PR authored by a headless run. Canary results are recorded on #177 and, once the workflow PR lands, in `docs/AUTONOMY.md` *Canary log*.
