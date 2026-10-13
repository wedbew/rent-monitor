# Delivery status

**The one place that says what works.** Updated by implementation PRs (`.agent/rules/delivery.md`), not by status-only PRs.
Hourly facts (open PRs, checks, who holds which issue) come from GitHub: `gh issue list --label ready`,
`uv run python scripts/delivery_metrics.py`. **Last verified:** 2026-10-13 against `staging` · by RM-177.

Levels: **1** implemented (offline tests, merged) · **2** integrated (journey test through API, queue, Postgres, engine, with named
fakes) · **3** provider-verified (authorised sandbox/live evidence) · **4** launch-ready (release gates). A closed issue is level 1 at most.

## Journey (P0): sign in → submit sale listing → reserve credit → queue → context → engine → persist and retrieve

| Step | Level | Evidence | Missing |
|---|---|---|---|
| Sign in (Google ID token, magic link, sessions) | 1 | `rm_api.auth`, `tests/integration/test_auth.py` (#147) | Real Google and Resend never exercised (B-004); level 3 open |
| Parse and bound the listing reference | 1 | `rm_core.listing_ref` | Route that accepts it: S1 #184 |
| Reserve credit, capture/release | 1 | `rm_core.ledger`, `tests/integration/test_ledger.py`, `test_concurrency.py` | Called by no audit path yet: S1 |
| Queue the analysis | 0 | Only the email job is deferred (`rm_api.queue`) | `run_audit` task and deferral: S1 |
| Acquire listing and context | 1 (parts) | Otodom client, snapshots, OSM/geo, OpenRouter client with fakes | Comparables store merged (#106 slice 1, level 1), importers that fill it still missing; real adapters wired (S4 #187); live shape confirmed for one sale listing, 2026-10-13 (L-005) |
| Run the engine | 1 | `apps/deal_analyzer.analyse_listing`, goldens, 7 invariants | CAPEX prices are placeholders (L-007); accuracy unmeasured (#94) |
| Persist and retrieve the canonical result | 0 | `audit` table and typed columns exist | `GET /api/audits*`: S1 |
| Failure releases the reservation; duplicates do not double-charge | 0 | `ledger.settle` is idempotent; one-active-per-listing index exists | Wired and proven end to end: S1; crash recovery: S3 #186 |
| Progress stream | 0 | `audit_event` table | S2 #185 |

**Journey level today: 0** (no audit route, no audit task). Components are level 1. Target of S1: level 2 offline with fakes. That
is not live-provider validation and not production readiness.

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
| #13 audits | U, P | Slices #184 (**R**, P0), #185, #186 (after #184), #187 (blocked: #184, #106, live-fetch authorisation) |
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
| #106 comparable-rent store | P | Store + sha256 cache done (level 1, offline, real Postgres). Open: fresh importers for rental comparables (`LEGAL[scraping\|third-party-data]`) and the hedonic refinement; slice them before `ready` |
| #39-#43 owner | owner | See *Owner actions* |
| #12, #17, #19, #20, #22, #23, #24, #30, #82, #84-#93, #157, #167 | V or E | Closed; E for those touching Google, Resend, Otodom or OpenRouter live |
| #6, #8, #9 headless autonomy | reopened as P | A headless run producing a merged PR is not yet demonstrated; see #177 |

## Owner actions (exact, smallest first)

1. Approve or comment on the money PR for #184 (head SHA recorded in `docs/BLOCKERS.md`) when it is up.
2. ~~Authorise one live Otodom fetch (L-005) and the datacenter-IP test (#42).~~ Done 2026-10-13: one sale listing returned 200 and parsed from the dev machine and from the OVH VPS-1. Single request each; sustained-load blocking is still unmeasured (L-002).
3. Provide the labelled listing set for #94 and CAPEX prices or a data source (B-015, L-007).
4. Stripe: grant sandbox access (B-003); request BLIK recurring activation (#39, has lead time).
5. Decisions still open: Pro allowance and free-tier scope (#43), market-data bootstrap (CONTEXT §9), exit-value anchor (B-014).
6. Approve the workflow PR (CI docs-only filter, dispatcher). Then enable the dispatcher after the canary: `gh variable set ENABLE_DISPATCH --body true`.

## Autonomy

Baseline (audit, 2026-10-13): `claude` workflow 231 runs, 224 skipped by design, 2 success, 2 failure, 3 cancelled; both failures
ended in ~2 s with zero model usage and $0 cost (an execution error before any model turn, logs in run 38182957497), and there is no
merged PR authored by a headless run. Canary results are recorded on #177 and, once the workflow PR lands, in `docs/AUTONOMY.md` *Canary log*.
