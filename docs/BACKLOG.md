# Backlog traceability: blueprint → issues

Checked against `docs/BLUEPRINT.md` on 2026-10-11. Every blueprint deliverable must map to an issue; when a new one appears,
add an issue and a row here (same PR). Labels: `phase-1`, `launch`, `owner`, `phase-2`, `blocked`. Order of work: `agents.md` §7.

| Blueprint | Deliverable | Issue |
|---|---|---|
| §1 | Host purchase, Poland, Ubuntu 24.04, Black Friday plan, datacenter-IP test | #42 |
| §1 | Compose limits, Caddy, host hardening, WAL-G image, backup container | #15 |
| §2 process model | Lifespan singletons, structlog, Sentry SDK (Better Stack, ADR 0009), Problem responses, `/healthz` `/readyz` `/api/health` | #18 |
| §2 route map | `/api/auth/*` | #12 |
| §2 route map | `/api/me`, `/api/saved`, `/api/admin/*` | #20 |
| §2 route map | `/api/audits` (create, list, get, SSE, cancel) | #13 |
| §2 route map | `/api/market/*`, `/api/screener/*` | #21 |
| §2 route map | `/api/billing/checkout`, `/portal`, `/webhook` | #14 |
| §2 frontend boundary | OpenAPI generation, contract tests, no TS finance code | #28 (SPA itself #44) |
| §2 listing contract, pipeline | Engine (extract, context, anchors, synthesize), invariants | #17 (blocked on spec; decisions #43) |
| §2 error contract | Problem codes, credit outcomes | #18, #13 |
| §2 scraping hygiene | `curl_cffi`, `host_throttle`, circuit breaker, 6 h snapshot sharing | #22 |
| §2 auth | Google ID token, magic link, sessions, rate limit, NOTIFY revocation | #12 |
| §2 Google Cloud setup | OAuth consent and client | #40 |
| §3 models, Alembic | All `app` tables, baseline migration, constraints | #11 |
| §3 flags | Flag tables and resolution | #19 (tables #11) |
| §3 quota | Ledger, usage periods, entitlements, `has_pro` | #19 |
| §3 Stripe lifecycle, BLIK, pass | Checkout, Portal, webhook state machine, passes | #14 |
| §3 BLIK | Stripe capability activation, Smart Retries, API pin | #39 |
| §3 VAT/KSeF | `vat_invoice` outbox, Fakturownia, KSeF states, on-demand invoice | #26 |
| §4.1 layout | Packages, services, `scripts/*`, `deploy/*` | #11, #15, #29 |
| §4.2 env | `.env.example`, typed settings | done (RM-2); extend per ticket |
| §4.3 compose, Caddy | `deploy/compose.yml`, `Caddyfile` | #15 |
| §4.4 bootstrap | Dev and prod bootstrap, seed script | #29, #15 |
| §4.5 a deps/ledger | Principal, quota dependency | #12, #19 |
| §4.5 b audits, worker, SSE | Submit, `run_audit`, child process, ProgressSink, SSE hub, reconciler | #13 |
| §4.5 c webhook | Idempotent webhook, checkout, grant_pass | #14 |
| §4.6 tests | Named tests, harness | #11 (harness), then each feature ticket |
| §4.7 backups, DR | WAL-G, nightly dump, restore drill, runbook | #15, gate #37 |
| §4.7 health table | Queue, host, money, OOM monitors | #25 |
| §4.8 step 1 | Engine foundation | #17 |
| §4.8 step 2 | Data plane | #11 |
| §4.8 step 3 | Auth | #12 |
| §4.8 step 4 | Audits | #13 |
| §4.8 step 5 | Billing | #14 |
| §4.8 step 6 | Frontend | #44 (Phase 2) |
| §4.8 step 7 | Ops | #15 |
| §4.8 step 8 | Market and screener tasks | #16 |
| §4.8 step 8, §5 | BDL metric contract, provenance, completeness/publication gates | #48 |
| §4.8 step 8, §5 | Otodom city coverage, partitioning and deduplication policy | #49 |
| §5 risk register | Legal review, accountant, IP test, cost | #41, #42, #24, L-001..L-003 |
| §5 open decisions | VAT display, allowance, free tier | #43 |
| §6 worker layout, memory admission | `worker-ops`, child memory cap, connection budget | #25, #13, #15 |
| §6 deadlines, fairness, AI budget | `Deadline`, throttle fairness, `ai_budget` | #13, #22, #24 |
| §6 disputes, refunds | `payment_issue`, dispute, refund, corrective invoice | #27 |
| §6 vision limits | ≤25 photos, 1,600 px, ≤2 plans, ≤4 calls | #23 |
| §6 release gates 1–7 | Gate evidence | #32–#38 |
| TOOLCHAIN §7 | ADRs | #31 |
| Rules (not in blueprint) | GDPR retention, deletion, export | #30 |
| Rules (not in blueprint) | Owner accounts: Resend, Better Stack, Umami, R2, domain | #40 |
| Rules (not in blueprint) | Legal/privacy docs, DPAs | #41 |

## Known gaps (deliberate)

**Next feature batch — owner direction, 2026-10-16:** [feature-gap guide §0](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md#0-next-implementation-batch-rynek-data-and-location-context). These deliverables are planned, not implemented:

| Deliverable | Existing owner / proposed missing slices |
|---|---|
| Durable media and report gallery | G-01 proposal in the feature-gap guide; existing report #274 is not completion of this feature |
| Factual equipment inventory and persisted OCR evidence | G-02 proposal |
| Grounded, durable seller questions | G-03 proposal; distinct from listing-writing assistant #285 |
| Manual source and photo uploads through the common audit pipeline | #283 / G-04 proposal |
| Persistent interior projects and concept/image operations | #284 / G-05 proposal |
| All verified 727 Otodom locations; full rental bootstrap and persistent offer-level Postgres corpus | #209/#49; OTO-01/02 proposals in the feature-gap guide; [fetch specification](OTODOM-NIGHTLY-IMPORT.md) |
| Nightly last-24-hours rental collection, durable coverage windows, restart/missed-night recovery | #16/#209; OTO-03 proposal |
| Daily rental cohort/trend history and freshness/coverage exposed in Rynek and audit context | #16/#21/#282; OTO-04 proposal |
| BDL gmina/powiat/województwo profiles, indicators/rankings, separate location index and report/agent context | #48/#21/#282; [contract and LCTX-01–03 proposals](BDL-LOCATION-CONTEXT-CONTRACT.md) |

Proposal labels are not filed GitHub issues. Create issue-owned implementation children under these parents; do not replace the existing import and BDL specifications with duplicate plans.

- Legacy-report and corpus importers from the original blueprint are dropped (ADR 0001, greenfield). Market data enters via fresh importers in #16.
- Gallery, equipment/OCR, seller questions, manual input, Rynek and interior tools are all owner-confirmed implementation scope (2026-10-16); market-data additions do not defer them. The separate analyst text-audit mode remains an open decision and is not required to implement seller questions.
