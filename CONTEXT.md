# RentMonitor — Project Context

> Orientation for humans and agents. Read this first, then `.agent/agents.md` (rules) and the section of
> `docs/BLUEPRINT.md` your ticket names. This file **summarises and links**; it does not replace them.
> If it disagrees with the blueprint, the blueprint wins and this file is stale — fix it (`rules/architecture.md`).
> **Living file:** every change that alters what is written here updates it in the same PR (`.agent/rules/context.md`).

**Last updated:** 2026-10-14 · by: RM-202 (ADR 0013 email + password auth spec and contracts; supersedes ADR 0004 on passwords); prior: RM-199 (owner-selected Paddle report-pack pilot and integration specification); billing alternatives research, RM-197 (design V3), RM-106 (comparable-rent store), RM-42 (live Otodom probe, L-005/L-002), RM-177 (delivery loop, STATUS.md); prior implementation: RM-167 (OpenAPI), RM-20 (me, saved, admin), RM-82 (GDPR endpoints), RM-12 (auth), RM-157 (worker ops), RM-171 (decisions D-14, L-010)

> **Greenfield (ADR 0001, `.agent/rules/poc-reference.md`):** the POC is read-only reference. Nothing is copied, moved or
> imported from it; the app is written from scratch to production quality. Sections below that say "POC" describe
> requirements and defects to avoid, not code to port.

**Sources:** `docs/BLUEPRINT.md` (architecture, 11 Oct 2026) · `docs/TOOLCHAIN.md` (quality, CI, governance, agents) ·
the POC repo `~/Projects/otodom-rent-report` (branch HEAD `b7dd5a9`, 11 Oct 2026; remote
`git@github.com:mm-dream-team/otodom-report.git`; reading commit `00ab3f9`, tree clean; earlier notes were taken at `b7dd5a9`).

**Confirmed vs inferred.** Everything under *Confirmed* was read in those three sources on 11 Oct 2026 (file listings,
`analyze.py`, `legal.py`, `config.py`, `pyproject.toml`, the POC `.md` docs). I did **not** read all ~34k lines of POC
Python, nor run its tests. Items marked *(inferred)* are conclusions to verify while porting.

---

## 1. What we are building

RentMonitor is a paid SaaS for Polish residential **buy-to-let investors**. A user pastes an Otodom **SALE** listing URL;
the system fetches it, reads the photos and floor plans with a vision LLM, anchors rent and price against market
data, and returns a deterministic 10-year cash-flow valuation (`DealAnalysis`): yield, IRR, MOIC, CAGR, tax, CAPEX,
**Max Bid**, and a grade. A second surface, the **727-city yield radar** and a bargain **screener**, ranks markets.

| Item | Decision (blueprint) |
|---|---|
| Host | One OVH VPS-3 (6 vCore, 12 GB), Docker Compose, Caddy + FastAPI + Procrastinate workers + Postgres 17, **no Redis** |
| Server runtime | **Python only.** Node exists only to build the SPA |
| Auth | Google ID token first (`google-auth`), email magic link, **email + password (Argon2id; specified in ADR 0013, not yet built)**; own sessions in Postgres. Passwords never attach to an account by email alone (ADR 0010, 0013) |
| Billing | Pilot direction: Paddle one-time 1/5/10-report packs, card + PLN BLIK; credit ledger. Integration spec only; product/accounting approval and final prices pending. Earlier Stripe subscription design retained as historical reference |
| Free tier | 3 audits on verified sign-up, yield radar top 20 (proposed) |
| Jobs / progress | Procrastinate queues; SSE via Postgres `LISTEN/NOTIFY` + `audit_event` replay |
| Monitoring | **Better Stack** free tier (ADR 0009): errors and traces via the `sentry-sdk` client, uptime monitor, backup heartbeat; replaces Sentry |
| Budget | ≈ $13.38 net/month infra; OpenRouter spend is COGS governed by the credit ledger |

**Phase 1 = backend only** (blueprint §4.8 steps 1–5, plus step 8 batch tasks). The Vite/React SPA is Phase 2; in
Phase 1 `frontend/` may only lose `server/*.ts`, `lib/cashflow.ts`, `lib/appreciation.ts` (`agents.md` §0).
Not launch-ready until the seven release gates in blueprint §6 pass.

## 2. Domain glossary

| Term | Meaning here |
|---|---|
| **Audit** | One user-initiated analysis of one listing; row in `app.audit`, ends in a terminal status that decides the credit outcome |
| **DealAnalysis** | Canonical JSON result of the engine (`output.py`, POC `schema_version` `"1.10"`). JSON is canonical, Markdown is a view |
| **Max Bid** | Highest price at which the deal still meets the return target; computed in Python only |
| **Sidecar** | Machine-readable market file (`{stem}.json` + `.md`) per city, kind and month; becomes a `market_sidecar` row |
| **Asking vs deed** | `asking` = advertised prices (Moniter, Otodom sale). `deed` = recorded transactions (GUS BDL, Cenogram). Never blended |
| **Admin fee / czynsz** | Building admin fee (`characteristics.rent` on Otodom). OPEX, never income |
| **Fractional ownership** | `udział`, `1/2 udziału`, `udział w spadku`. Rejected from rankings and audits |
| **Credit reserve → capture / release** | Credit held at queue time; captured only on `succeeded` / `succeeded_degraded` |
| **Pro / pass** | Subscription (allowance per invoice period) or one-off 30-day BLIK pass; `has_pro` fails closed 48 h after period end |
| **Principal** | The authenticated user object every tenant-owned query requires; foreign resources return 404 |
| **Tag** | `LEGAL[...]` / `GDPR[...]` source comments (`rules/legal-tags.md`) |

**Name collision to avoid:** the POC module `deal_analyzer.legal` is a *VAT / non-residential detector* (regex over the
listing text → `residential | vat_sale | non_residential`). It has nothing to do with our legal *tags* or `rm_core.legal`
(`LegalTag`). Keep the POC module's name and behaviour; never import one as the other.

## 3. The five invariants (and how the POC showed them — reference only)

Each needs a named `@pytest.mark.invariant` test (blueprint §4.6). Never delete, skip or weaken one.

| # | Invariant | POC mechanism (confirmed) | What to build (from scratch) |
|---|---|---|---|
| 1 | RENT is not a deal | `analyze_listing` raises `RentNotADeal(ad_id)` when `core.kind == "RENT"` (`analyze.py`) | Worker maps it to `rejected / RENT_NOT_DEAL`, releases the credit, **no vision call** |
| 2 | Asking ≠ deed | Separate sidecar stems (`bdl-sales-*`, `moniter-sales-*`, `otodom-sales-*`); Cenogram "never bootstrapped" (`ensure.py` raises) | `market_sidecar.price_basis` + `asking_is_not_deed` CHECK; `ContextRepository` returns distinct types |
| 3 | Admin fee is OPEX | `extract.py` parses czynsz; `operating.py` uses `admin_fee_monthly_pln` as an owner cost | Write a hand-built fixture test (`characteristics.rent = 600` → 600 OPEX, 0 income) |
| 4 | Deterministic math; LLM clamped ±15% | `cashflow.py`, `operating.py`, `synthesize.py`, `verdict.py` are Python; LLM only in `images/`, `analyst.py`, `fitout/agent.py`, `redesign.py` | Byte-identical `returns` block across two runs; clamp test |
| 5 | Fractional ownership rejected | `ownership.py` (`classify_ownership`, title patterns) in the analyzer; a *provisional* title-only guard in the screener | Keep both; test with `udział` fixtures |

## 4. POC as requirements: what to rebuild and what to avoid

Rule (ADR 0001): **write from scratch, production-ready; the POC is read-only reference.** Blueprint paths under `apps/` are where
the new packages live; they start empty and are built test-first from the blueprint contracts.

### 4.1 POC packages → what each tells us (confirmed from the POC tree; treatment = rebuild, never copy)

| POC path | Size (approx.) | CLI | Goes to | Treatment |
|---|---|---|---|---|
| `apps/deal-analyzer` | 141 `.py`, ~23.8k LOC non-test, ~62 test files | `deal-analyzer` | `apps/deal-analyzer` | **Rebuild.** Valuation, DCF, tax, verdict engine: specify formulas in issues first; `Decimal` money; seams native |
| `apps/otodom-city-report` | 25 `.py`, ~2.8k LOC | `otodom-report` | `apps/otodom-city-report` | Rebuild. Search scraper → `CityReport` and rental sidecars; `client.py` is the `_next/data` fetcher. Called from `worker-batch` |
| `apps/price-intel` | 24 `.py`, ~4.3k LOC | `price-intel` | `apps/price-intel` | Rebuild. GUS BDL, Moniter, Cenogram, demography. Drop `prototypes/` |
| `apps/otodom-investment-screener` | 35 `.py`, ~3.8k LOC | `investment-screener` | `apps/otodom-investment-screener` | Rebuild. CLI/interactive (`questionary`, `rich`); becomes `screener` tasks behind the flag; **human approval gate stays** |
| `apps/agent-context` | corpus only, **~65 MB** | none | `apps/agent-context` (export target) | Do not copy the corpus. Data enters via fresh, fetched-and-validated importers; small anonymised fixtures are hand-built for tests |
| `scripts/compare_rent_to_sale.py` | 1 script | — | `apps/` or `scripts/` *(decide)* | The 727-city yield radar comparator (README); that it produces the `yield_ranking` sidecars is *(inferred)* |
| `frontend/` | Vite + React deal desk | — | `frontend/` in **Phase 2** | Phase 1: do not copy. Later, delete `server/*.ts`, `lib/cashflow.ts`, `lib/appreciation.ts` |
| `docs/` (design prompts, audit) | — | — | not copied | `APP_AUDIT_AND_ROADMAP.md` is the audit the blueprint cites ("audit 3.1-2", "P0.3"); keep reachable by link |

The new root workspace is `packages/*`, `services/rm_api`, `services/rm_worker`, and `apps/*` as each engine is built (blueprint §4.1);
exclude `apps/agent-context` from the workspace. Each app gets its own `pyproject.toml`.

### 4.2 What the new platform replaces

| POC behaviour (confirmed) | Problem | Replacement |
|---|---|---|
| `analyze_listing(..., agent_context: Path, ensure=True)` reads sidecars from disk and **fetches missing context itself** by calling the city/price tools (`ensure.py`) | Disk coupling; network calls from inside the engine | `analyze_listing(ref, *, context: ContextRepository, progress: ProgressSink)`; filesystem implementations keep the CLI working; in the SaaS `ensure` is off and the batch workers own context refresh |
| Result written to `reports/final/{id}.json` via `report_store.publish_deal_report` | Filesystem as database (audit §2.2) | Persist to `audit.result` (JSONB) + typed columns copied from `DealAnalysis` |
| SQLite caches: `nominatim.py`, `geo_cache.py`, `osm_distance.py`, `corpus.py`, `outcomes.py`; DuckDB is a `deal-analyzer` dependency | Rate-limit `sleep` held inside an SQLite transaction (audit 3.1-3); locks across processes | Postgres tables; throttle outside the transaction (`host_throttle`) |
| `hedonic.py` SHA-256s every `otodom-rental-*.json` before each prediction | 100–300 ms per run (audit 3.1-2) | Cache key from sidecar `sha256` column |
| `requests` bridged into an `httpx` transport (`OTODOM_HTTP_BACKEND=requests`) | Blocking I/O in async code; trivially fingerprinted | `curl_cffi` with browser TLS impersonation behind the injectable client (blueprint §2; audit 3.2) |
| Frontend `server/plugin.ts` shells out to `uv run` per request, no queue | Unbounded processes, orphaned children, token burn | Procrastinate `audit` queue, concurrency 1, a child process with a 900 s `Deadline` and memory cap |
| Frontend `cashflow.ts` / `appreciation.ts` re-derive finance in TypeScript | Dual-engine drift; violates invariant 4 | API returns every number; a null renders as "not computed" |

### 4.3 Things the POC has that the blueprint does not mention — decide before building

1. **Interior redesign playground** (`redesign.py`, OpenRouter image-to-image, BOM totals, `frontend/server/redesign.ts`). The
   blueprint only reserves a `redesign` feature flag. Treat as Phase 2+; it sends listing photos to a third party →
   `LEGAL[images]`, `GDPR[processor]`.
2. **AI seller-questions** (`seller_questions.py`) and the **analyst** text-LLM audit (`analyst.py`, `AuditCreate.analyst`, Pro-only).
3. **Backtest / release-eval / model-artifact / corpus / outcomes** modules: offline evaluation tooling, not request-path.
   Build only if the maintainer schedules them; never wire into the request path.
4. **`apps/agent-context/AGENTS.md`**: TOOLCHAIN §7 requires renaming it to `INDEX.md` — tools load any file named
   `AGENTS.md` as instructions. Do this during the copy, and update the references in `apps/agent-context/README.md`.
5. **The 65 MB corpus.** Pre-commit blocks files over 1 MB, and `.gitignore` only ignores the *root-level* `/agent-context/`.
   Decide: commit a small fixture set only and import the full corpus from the POC out-of-band, or use Git LFS. *(open)*

## 5. POC defects and lessons found while reading (design them out)

| # | Finding | Why it matters | Suggested handling |
|---|---|---|---|
| G1 | POC `output.py` models money as `float` (64 `float`, 0 `Decimal` mentions) | `agents.md` §3 bans float in **persisted or returned** money fields | `Decimal` everywhere including the engine; state the rounding rule; property tests. Semgrep `no-float-money` covers `packages/`, `services/`, `apps/`, with rule tests in `.semgrep/rentmonitor.py` (RM-55) |
| G2 | POC `operating.py` computes with `* 12.0` floats | Same | Same; new `apps/` code is held to the same lint/type bar as `packages/` |
| G3 | `analyze_listing` is synchronous and calls `asyncio.run(...)` internally to fetch | Cannot run on the API event loop | New engine is async-clean or CPU-only and runs in the worker's killable child process (blueprint §4.5) |
| G4 | Blueprint's `auth/google.py` sample imports `requests`; TOOLCHAIN ruff bans `requests` in `services/` (TID251) | The sample would fail lint | Use `httpx`-based transport for `google-auth` or a scoped `per-file-ignores` entry with a comment |
| G5 | TOOLCHAIN was written without seeing the repo (says so) | Existing POC settings, tests and CI were unknown to it | Treat its numbers (e.g. "29 named tests") as proposals; verify against `pytest --collect-only` once ported |
| G6 | TOOLCHAIN asks to pin SQLAlchemy 2.1 / blueprint text says 2.0; Stripe SDK major unconfirmed | Pinned-API drift | Resolve the TOOLCHAIN §8 decisions 3–4 in an ADR; use `context7` before writing code |
| G7 | POC `DealAnalysis.schema_version` has 11 historic values (`1.0`…`1.10`); old `reports/final/*.json` must still load | `audit.schema_version` is a column; importers read legacy reports | New schema versions from `1`; no legacy-report importer unless the maintainer asks |
| G8 | POC has its own `AGENTS.md` and `.cursor/rules` (frontend sync, limitations, roadmap) | Conflicts with our rules | Do **not** copy them. Read their limitation lists as input; register only what still applies in `docs/LIMITATIONS.md` |
| G9 | POC engine hits third parties directly: Otodom, OpenRouter, GUS BDL, Moniter, Nominatim, Overpass | Tests must be offline | Each goes behind an injectable client with timeouts; fakes in `tests/` |
| G10 | POC `.env` exists in the POC repo | Must never be read or copied | Use names from the POC `config.py` (`OTODOM_BASE_URL`, `OTODOM_HTTP_BACKEND`, `GEO_*`, `NOMINATIM_*`, `OVERPASS_URL`, `VALUATION_EVIDENCE_DIR`, `MODEL_ARTIFACT_PATH`, `SNAPSHOT_CUTOFF`, `DEAL_ANALYZER_MC_DRAWS`) only to build `.env.example` |
| G11 | `curl_cffi` in stream mode applies only a *low-speed* timeout, and closing a stream waits for the server to finish | A slow-drip server escaped every timeout and held the worker for the whole body | Hard `asyncio.timeout` around the request and cancel the stream task before `aclose()` (RM-22; tests in `test_otodom_transport.py`) |
| G12 | A live listing (2026-10-13) has `ad.characteristics` as a **list**, not a mapping; the body also contains `captcha` on a normal 200 page | The admin-fee (czynsz) extraction cannot index by key; a marker match alone is not a block | Scan the list for the rent item (invariant 3 fixture); treat challenge markers only when `__NEXT_DATA__` is missing (L-005) |

## 6. Legal and GDPR hot-spots (where the POC did it; tag the new code that does the same)

Per `rules/legal-tags.md`, tag the new implementations of these; features stay.

| Where in the POC | Tag |
|---|---|
| `otodom_city_report/client.py`, `headers.py`, `deal_analyzer/fetch.py` (browser-like headers, `fake-useragent`, `_next/data`) | `LEGAL[scraping]` |
| `deal_analyzer/resolve.py` (URL / ID → listing) | `LEGAL[url-analysis]` |
| `deal_analyzer/images/download.py`, `vision.py`, `layout_vision.py`, `export_jpegs.py`, `redesign.py` | `LEGAL[images]`, `GDPR[processor]` (OpenRouter) |
| `price_intel/sources/moniter.py`, `cenogram.py`, `bdl.py`, `demography.py`; `deal_analyzer/nominatim.py`, `osm_distance.py` (OSM usage policy) | `LEGAL[third-party-data]` |
| Raw `listing_snapshot.payload` (may contain seller name / phone) | `GDPR[personal-data]`, retention + erasure path |
| Report Markdown / API results that echo listing text or photos to other tenants | `LEGAL[republication]` |

## 7. Pipeline to preserve (confirmed from blueprint §2 and POC `PIPELINE.md` headline)

`Fetch → Extract → Context → Images & Vision → Anchors → Synthesize → Emit`, emitted as the fixed-percentage stages
`fetch 5 · extract 15 · context 25 · vision 35 · ocr 60 · anchors 70 · synthesize 85 · persist 95`.
Engine limits per audit: ≤ 25 photos at ≤ 1,600 px long edge, ≤ 2 floor plans, ≤ 4 OpenRouter calls in flight, one
900 s deadline. Terminal states and credit outcomes: blueprint §2 error contract.

## 8. Order of work and where we are

1. Engine seams → 2. Data plane → 3. Auth → 4. Audits → 5. Billing → 7. Ops → 8. Market & screener (step 6, frontend, is Phase 2).
Order is gated by `Depends on:` lines, not step numbers (ADR 0012); only a red `staging` stops work. TOOLCHAIN §8 adds **Step 0** (pre-setup RM-1…RM-6: apply the tooling pack,
rulesets, Claude and Gemini apps, rename `agent-context/AGENTS.md`, commit the blueprint and ADRs).

**State of this repo:** see [`docs/STATUS.md`](docs/STATUS.md), the single delivery-state view (journey steps, evidence, backlog map,
owner actions). What exists is also derivable from `packages/`, `services/`, `apps/`, `migrations/` and `git log`; this file no longer
keeps a per-PR history. Standing facts: Phase 1 is backend only; `invariants` and `migrations` CI jobs are on and required; the
`wedbew/rent-monitor` repo is **public during development** (switch to private before real keys or data: `docs/PRE-DEPLOYMENT.md` §0);
rulesets for `main` and `staging` are active. Roadmap, gates and owner deadlines: `docs/ROADMAP.md`. Market-data planning gaps: #48
(metric provenance and completeness gates) and #49 (city coverage and deduplication) are fresh-import design, not permission to copy POC
or GUS-PoC artifacts. Delivery process: `.agent/rules/delivery.md`, ADR 0012.

**Design exploration (12 Oct 2026, maintainer request):** `design/` contains proposed UX principles, a documentation-state review,
and responsive interactive home, analyses-list and separate city-context prototypes with fictional fixtures. `design/v1/` holds the warm editorial direction; `design/v3/` (13 Oct) is a light-first alternative with an interactive login demo, report, market page and logo explorations; `design/v2/` adds a monochrome architectural alternative with new tokens, restrained motion, and a dedicated analysis-page scaffold/UX contract (full analytic rendering deferred). Neither is selected for production. This is a Phase 2 design artifact, not a production SPA;
`frontend/` and backend contracts are unchanged.

## 9. Open decisions (owner: you)

From the blueprint §5 and TOOLCHAIN §8, plus those found here. Do not guess on money, auth or anything irreversible.

- [x] `migrations` CI job on and required (RM-68)
- [x] `invariants` CI job on and required (RM-89): the four named tests exist (RENT, asking≠deed, admin fee, deterministic math); invariants 5 and 6 and the ±15% clamp are added by N-08/N-10
- [x] Port the POC? **No** — greenfield (ADR 0001, RM-2)
- [ ] Market-data bootstrap: how the 727-city sidecars are produced fresh (fetch via new importers; no corpus copy)
- [x] Engine specification approved with amendments: `docs/ENGINE-SPEC.md` (RM-73); tax constants flagged for the accountant
- [ ] Which POC extras ship in Phase 1: redesign, seller-questions, analyst (§4.3)
- [x] VAT presentation: 100 zł shown gross (81.30 net + 23 %), Stripe prices tax-inclusive (D-03); accountant to confirm VAT-payer status (#41)
- [x] Pilot product direction: owner selected one-time Paddle packs of 1/5/10 reports, without subscriptions; [PADDLE-INTEGRATION.md](docs/PADDLE-INTEGRATION.md). Implementation and provider validation remain pending; supersede ADR 0005 with implementation.
- [ ] Pack pricing: owner suggested 5/40/70 PLN; recommended 10/40/70 PLN to make bulk packs cheaper per report and cover Paddle's fixed fee. Also decide signup reports (currently 3) and unused-unit expiry. Product/accounting unknowns: L-015/L-016.
- [ ] Pro allowance (40 is a placeholder until COGS is measured); free-tier scope
- [x] SQLAlchemy 2.0 and Stripe SDK pin at #14: ADR 0007 accepted (D-02)
- [ ] Gemini and Claude auth in Actions; GitHub plan for private-repo rulesets
- [x] D-13 Google links or creates accounts only for `@gmail.com` or a matching `hd`; others confirm by magic link (ADR 0010, RM-12)
- [ ] Polish legal review of Otodom scraping before charging (blueprint §5, not legal advice)
- [x] D-15 Email + password sign-in added (owner, 2026-10-14): [ADR 0013](docs/adr/0013-email-password-auth.md), slices in #201. Proposed values still open for review: min length 10, Argon2id 19 MiB / 2 / 1, verification link 24 h; breach-corpus check deferred (L-017)
- [x] D-14 R2 backups in the EU jurisdiction (fixed at creation), `rentmonitor-backups`, WAL-G retention 14 days: decided (ADR 0011, RM-171)

## 10. Where to look

| Need | Open |
|---|---|
| POC-is-reference and production bar | `.agent/rules/poc-reference.md`, `docs/adr/0001-greenfield-rewrite.md` |
| Expensive-to-reverse decisions (runtime, queue, auth, billing, host, pins) | `docs/adr/0002`–`0009` |
| Rules, invariants, git flow, PR template | `.agent/agents.md`, `.agent/rules/*.md`, `.github/pull_request_template.md` |
| Architecture, schema, Stripe, auth, tests | `docs/BLUEPRINT.md` §2–§4 |
| Billing alternatives, MoR costs, Polish invoicing/KSeF scope and proposed Paddle evaluation | `docs/BILLING-ALTERNATIVES.md` (research, not an accepted spec) |
| Owner-selected pilot report packs, Paddle checkout/webhooks, credit provenance, refunds and implementation tests | `docs/PADDLE-INTEGRATION.md` (specification; no implementation evidence) |
| Google sign-in and session specification, as built (RM-12) and the owner's local setup notes | `docs/GOOGLE-AUTH-SPEC.md`; local handoff `docs/GOOGLE-AUTH-INTEGRATION.md` is gitignored |
| Resend local configuration and mailer integration instructions | `docs/RESEND-INTEGRATION.md` (owner's local handoff, gitignored; RM-12) |
| Umami analytics setup, verified script behaviour and the CSP finding | `docs/UMAMI-INTEGRATION.md` (owner's local handoff, gitignored; RM-143) |
| Better Stack Errors DSN, Python logs and verified source setup | `docs/BETTERSTACK-INTEGRATION.md` (owner's local handoff, gitignored; RM-18/RM-112) |
| CI, hooks, rulesets, MCP, skills | `docs/TOOLCHAIN.md` |
| Risk register and release gates | `docs/BLUEPRINT.md` §5–§6 |
| Headless agent (Actions), secrets | `docs/AUTONOMY.md` |
| Backlog (blueprint → issues) | `docs/BACKLOG.md` |
| Milestones, dependencies and launch gates | `docs/ROADMAP.md` |
| Delivery state (journey, backlog map, owner actions) | `docs/STATUS.md` |
| Autonomous delivery evidence, bottlenecks and proposed faster workflow (recommendations only) | `docs/DELIVERY-AUDIT.md` (RM-177) |
| Proposed Phase 2 UX principles and interactive design alternatives (fictional data; not production frontend) | `design/README.md`, `design/v1/`, `design/v2/design-principles.md`, `design/v2/main-view.html`, `design/v3/README.md` |
| Phase 2 design direction (prototype, principles, spec) | `design/README.md` (#44 input; no backend or rule change) |
| Owner-only blockers | `docs/BLOCKERS.md`, `.agent/rules/blockers.md` |
| Agent bot setup | `docs/AGENT-BOT.md`, `scripts/setup_agent_bot.sh` |
| Launch checklist (incl. back to private) | `docs/PRE-DEPLOYMENT.md` |
| POC architecture map and data flow | `~/Projects/otodom-rent-report/apps/ARCHITECTURE.md` |
| POC pipeline call order, config files | `…/apps/deal-analyzer/PIPELINE.md`, `config/*.yaml` |
| POC audit (origin of "audit 3.x" references) | `…/docs/APP_AUDIT_AND_ROADMAP.md` |
| POC limitations register | `…/apps/LIMITATIONS.md`, `…/apps/deal-analyzer/docs/LIMITATIONS.md` |
| GUS reference lessons (read-only; no artifact import) | `~/Projects/gus-stats-poc/README.md`, `docs/REIS_V3_IMPLEMENTATION_VERIFICATION.md` |
