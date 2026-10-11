# RentMonitor — Project Context

> Orientation for humans and agents. Read this first, then `.agent/agents.md` (rules) and the section of
> `docs/BLUEPRINT.md` your ticket names. This file **summarises and links**; it does not replace them.
> If it disagrees with the blueprint, the blueprint wins and this file is stale — fix it (`rules/architecture.md`).
> **Living file:** every change that alters what is written here updates it in the same PR (`.agent/rules/context.md`).

**Last updated:** 2026-10-11 · by: RM-22 (Otodom fetch client)

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
| Auth | Google ID token first (`google-auth`), email magic link second, own sessions in Postgres, **no passwords** |
| Billing | Stripe: card + BLIK subscription (100 zł/month), 30-day BLIK pass; credit ledger; VAT invoices via Fakturownia → KSeF |
| Free tier | 3 audits on verified sign-up, yield radar top 20 (proposed) |
| Jobs / progress | Procrastinate queues; SSE via Postgres `LISTEN/NOTIFY` + `audit_event` replay |
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

The new root workspace is `packages/*`, `services/api`, `services/worker`, and `apps/*` as each engine is built (blueprint §4.1);
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
| G1 | POC `output.py` models money as `float` (64 `float`, 0 `Decimal` mentions) | `agents.md` §3 bans float in **persisted or returned** money fields | `Decimal` everywhere including the engine; state the rounding rule; property tests. Semgrep `no-float-money` covers `packages/`, `services/`; extend it to `apps/` |
| G2 | POC `operating.py` computes with `* 12.0` floats | Same | Same; new `apps/` code is held to the same lint/type bar as `packages/` |
| G3 | `analyze_listing` is synchronous and calls `asyncio.run(...)` internally to fetch | Cannot run on the API event loop | New engine is async-clean or CPU-only and runs in the worker's killable child process (blueprint §4.5) |
| G4 | Blueprint's `auth/google.py` sample imports `requests`; TOOLCHAIN ruff bans `requests` in `services/` (TID251) | The sample would fail lint | Use `httpx`-based transport for `google-auth` or a scoped `per-file-ignores` entry with a comment |
| G5 | TOOLCHAIN was written without seeing the repo (says so) | Existing POC settings, tests and CI were unknown to it | Treat its numbers (e.g. "29 named tests") as proposals; verify against `pytest --collect-only` once ported |
| G6 | TOOLCHAIN asks to pin SQLAlchemy 2.1 / blueprint text says 2.0; Stripe SDK major unconfirmed | Pinned-API drift | Resolve the TOOLCHAIN §8 decisions 3–4 in an ADR; use `context7` before writing code |
| G7 | POC `DealAnalysis.schema_version` has 11 historic values (`1.0`…`1.10`); old `reports/final/*.json` must still load | `audit.schema_version` is a column; importers read legacy reports | New schema versions from `1`; no legacy-report importer unless the maintainer asks |
| G8 | POC has its own `AGENTS.md` and `.cursor/rules` (frontend sync, limitations, roadmap) | Conflicts with our rules | Do **not** copy them. Read their limitation lists as input; register only what still applies in `docs/LIMITATIONS.md` |
| G9 | POC engine hits third parties directly: Otodom, OpenRouter, GUS BDL, Moniter, Nominatim, Overpass | Tests must be offline | Each goes behind an injectable client with timeouts; fakes in `tests/` |
| G11 | `curl_cffi` in stream mode applies only a *low-speed* timeout, and closing a stream waits for the server to finish | A slow-drip server escaped every timeout and held the worker for the whole body | Hard `asyncio.timeout` around the request and cancel the stream task before `aclose()` (RM-22; tests in `test_otodom_transport.py`) |
| G10 | POC `.env` exists in the POC repo | Must never be read or copied | Use names from the POC `config.py` (`OTODOM_BASE_URL`, `OTODOM_HTTP_BACKEND`, `GEO_*`, `NOMINATIM_*`, `OVERPASS_URL`, `VALUATION_EVIDENCE_DIR`, `MODEL_ARTIFACT_PATH`, `SNAPSHOT_CUTOFF`, `DEAL_ANALYZER_MC_DRAWS`) only to build `.env.example` |

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
Do not start step N+1 with step N red. TOOLCHAIN §8 adds **Step 0** (pre-setup RM-1…RM-6: apply the tooling pack,
rulesets, Claude and Gemini apps, rename `agent-context/AGENTS.md`, commit the blueprint and ADRs).

**State of this repo (11 Oct 2026):** blueprint, toolchain, agent rules (`.agent/`, `.cursor/rules/`, `CLAUDE.md`, `AGENTS.md`),
CI/security workflows, pre-commit, semgrep rules and commit-message checker exist. RM-2 added the empty workspace (`rm-core`
settings + `LegalTag`, `rm-contracts` `ProblemCode`, `rm-api` `/api/health`, empty `rm-worker`), `Makefile`, `.env.example`,
`README.md`, `CHANGELOG.md`, `docs/LIMITATIONS.md`. ADR 0001 made the build greenfield. A first attempt to copy POC packages was
discarded. RM-11 added `packages/rm-core/.../db/` (all §3 models), `alembic.ini`, `migrations/` (baseline `0001`), Testcontainers fixtures and
`test_invariant_asking_is_not_deed`. RM-22 added `rm_core.{listing_ref,deadline,throttle,snapshots}`, `rm_worker.clients.otodom*`, `rm_worker.snapshot_service` and migration `0002` (`host_throttle`). RM-29 added `deploy/compose.dev.yml`, Makefile dev targets, `rm_core.seed`, `scripts/seed.py` and `rm_worker.app`. RM-18 added `rm_core.logging`/`observability`, `rm_api.{app,problems,middleware,health,deps}` (problem codes, `/healthz`, `/readyz`, session dependency). Still missing: `apps/`, `deploy/`, the other named invariant tests (the CI `invariants` job stays off
until they exist; do not stub them), Procrastinate worker bootstrap, `frontend/`. The `migrations` CI job can be switched on
(`ENABLE_MIGRATIONS_JOB=true` plus the `staging` required check) — an owner action, see §9.
Repo `wedbew/rent-monitor` is **public during development** (switch back to private before real keys or data: `docs/PRE-DEPLOYMENT.md` §0);
rulesets for `main` and `staging` are active; `staging` exists (PR #3 merged by admin bypass with `invariants` and `migrations` red).
Roadmap milestones, issue dependencies, gates and owner deadlines are in `docs/ROADMAP.md` (RM-47). New market-data planning gaps:
#48 requires metric provenance/completeness gates; #49 requires city coverage/deduplication policy. Both are fresh-import design,
not permission to copy POC or GUS-PoC artifacts.

## 9. Open decisions (owner: you)

From the blueprint §5 and TOOLCHAIN §8, plus those found here. Do not guess on money, auth or anything irreversible.

- [ ] Turn on the `invariants` / `migrations` CI jobs (they are skipped by default: set repo variables `ENABLE_INVARIANTS_JOB` / `ENABLE_MIGRATIONS_JOB` to `true`) and re-add both to the `staging` required checks, in the PR that makes them pass
- [x] Port the POC? **No** — greenfield (ADR 0001, RM-2)
- [ ] Market-data bootstrap: how the 727-city sidecars are produced fresh (fetch via new importers; no corpus copy)
- [ ] Engine specification: formulas, thresholds and grade cut-offs the maintainer wants (agents ask; do not transcribe from POC code)
- [ ] Which POC extras ship in Phase 1: redesign, seller-questions, analyst (§4.3)
- [ ] VAT presentation of 100 zł; Pro allowance (40 is a placeholder until COGS is measured); free-tier scope
- [ ] SQLAlchemy 2.0 vs 2.1; Stripe SDK major (ADR 0007 *proposes* 2.0 and an exact SDK pin at #14; owner confirms); Gemini and Claude auth in Actions; GitHub plan for private-repo rulesets
- [ ] Polish legal review of Otodom scraping before charging (blueprint §5, not legal advice)

## 10. Where to look

| Need | Open |
|---|---|
| POC-is-reference and production bar | `.agent/rules/poc-reference.md`, `docs/adr/0001-greenfield-rewrite.md` |
| Expensive-to-reverse decisions (runtime, queue, auth, billing, host, pins) | `docs/adr/0002`–`0007` |
| Rules, invariants, git flow, PR template | `.agent/agents.md`, `.agent/rules/*.md`, `.github/pull_request_template.md` |
| Architecture, schema, Stripe, auth, tests | `docs/BLUEPRINT.md` §2–§4 |
| CI, hooks, rulesets, MCP, skills | `docs/TOOLCHAIN.md` |
| Risk register and release gates | `docs/BLUEPRINT.md` §5–§6 |
| Headless agent (Actions), secrets | `docs/AUTONOMY.md` |
| Backlog (blueprint → issues) | `docs/BACKLOG.md` |
| Milestones, dependencies and launch gates | `docs/ROADMAP.md` |
| Agent bot setup | `docs/AGENT-BOT.md`, `scripts/setup_agent_bot.sh` |
| Launch checklist (incl. back to private) | `docs/PRE-DEPLOYMENT.md` |
| POC architecture map and data flow | `~/Projects/otodom-rent-report/apps/ARCHITECTURE.md` |
| POC pipeline call order, config files | `…/apps/deal-analyzer/PIPELINE.md`, `config/*.yaml` |
| POC audit (origin of "audit 3.x" references) | `…/docs/APP_AUDIT_AND_ROADMAP.md` |
| POC limitations register | `…/apps/LIMITATIONS.md`, `…/apps/deal-analyzer/docs/LIMITATIONS.md` |
| GUS reference lessons (read-only; no artifact import) | `~/Projects/gus-stats-poc/README.md`, `docs/REIS_V3_IMPLEMENTATION_VERIFICATION.md` |
