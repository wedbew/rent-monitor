# Renti — Project Context

> Orientation for humans and agents. Read this first, then `.agent/agents.md` (rules) and the section of
> `docs/BLUEPRINT.md` your ticket names. This file **summarises and links**; it does not replace them.
> If it disagrees with the blueprint, the blueprint wins and this file is stale — fix it (`rules/architecture.md`).
> **Living file:** every change that alters what is written here updates it in the same PR (`.agent/rules/context.md`).

**Last updated:** 2026-10-21 · by: RM-453 (interior: media store on the private rent-monitor bucket, default endpoint accepted, MEDIA_* mapper, local probe PASS); prior: RM-447 (interior 1/5: media store seam, ADR 0014, #284); prior: RM-439 (districts, cohort overview, experimental locality index); prior: RM-438 (explicit `unlimited_reports` account entitlement); prior: RM-282 (daily summaries count offers of dead runs, no first-seen count on a bootstrap day); prior: RM-282 (Rynek map, comparison and GUS context UI; place mapping and free tier); prior: RM-411 (Otodom live contract, gmina-level catalogue, manifest, worker-batch); prior: RM-48 (BDL registry, reference and refresh live-verified); prior: RM-422 (frontend Rynek page); prior: RM-421 (market read API: locations, detail, history); prior: RM-210 (ECB risk-free rate, migration 0019); prior: RM-387 (OCR and equipment evidence in the report); prior: RM-396 (BDL per-metric indicators); prior: RM-395 (rental daily summaries, migration 0017); prior: RM-392 (Otodom corpus importer, offline); prior: RM-391 (BDL persistence and ingestion, migration 0016); prior: RM-385 (Postgres rental corpus, migration 0015); prior: RM-386 (BDL source client and validator); prior: RM-277 (frontend credits and purchases); prior: RM-376 (media manifest, migration 0014); prior: RM-377 (Otodom rental corpus contracts, phase 1); prior: RM-378 (BDL location-context contracts, phase 1); prior: RM-28 (API contract fuzzing with Schemathesis); prior: RM-278 (frontend settings page); RM-374 (feature-gap, readiness and parallel-Claude foundation); prior: owner-confirmed complete feature batch (G-01–G-05 plus Otodom/BDL) (issue proposals not filed; see §10); prior: RM-347 (saved list paging to the 500 cap, PUT keeps an absent note); prior: RM-276 (frontend saved listings and notes); prior: RM-343 (frontend UI polish: report header, metric help, Otodom attribute labels, selects, alerts, analyses table); prior: RM-320 (frontend correctness rules); prior: RM-319 (frontend audit and re-verification); prior: RM-275 (frontend analyses collection); prior: RM-274 (frontend report page); prior: RM-273 (frontend new analysis and live progress); prior: RM-272 (frontend Pulpit); prior: RM-271 (frontend authentication and session boundary); prior: RM-270 (frontend shell, tokens, primitives, theme, navigation); prior: RM-269 (frontend e2e interaction gate, journey lane); prior: RM-268 (frontend typed client, fixtures, scenarios); prior: RM-267 (Phase 2 authorised, frontend foundation); prior: RM-266 (versioned DealAnalysis JSON Schema, REPORT-SCHEMA.md); prior: RM-265 (audit list keyset paging and filters, breaking list shape); prior: RM-264 (errors documented as problem+json in OpenAPI, L-027 resolved); prior: RM-263 (API smoke test and sample capture, `tests/smoke/`, L-028); RM-262 (V2 handoff verified, frontend plan and issues #263-#286, blueprint frontend sections); prior: owner-requested V2 light theme, renti.tech branding, navigation/hover motion, V2 frontend baseline and implementation/design-system/tooling handoff; prior: app-wide dashboard, URL/manual analysis, interior/listing workspaces, settings/legal placeholders and documentation; prior: RM-255 (owner-selected nightly new-offer imports and 90-day archive guide, #209 planning); prior: RM-246 (budget hold priced from the OpenRouter catalog); prior: RM-244 (vision and OCR stages in the audit); prior: RM-240 (rental-comparables importer, Listing.location_id); prior: RM-229 (support refunds, invoice access); prior: RM-219 (provider reversals); prior: RM-218 (Paddle webhook and grant); prior: RM-217 (pack checkout); prior: RM-216 (report credit lots); prior: RM-15 (beta deployment preparation, worker lanes); prior: RM-215 (Paddle catalog and client); prior: RM-205 (password recovery and change); prior: RM-204 (password login); prior: RM-203 (password registration); prior: RM-202 (password auth spec, ADR 0013); prior: RM-187 (real audit adapters); prior: RM-185 (audit progress SSE); prior: RM-186 (audit recovery); prior: RM-184 (audit journey slice 1); prior: RM-199 (owner-selected Paddle report-pack pilot and integration specification); prior: billing alternatives research, RM-197 (design V3), RM-106 (comparable-rent store), RM-42 (live Otodom probe, L-005/L-002), RM-177 (delivery loop, STATUS.md); prior implementation: RM-167 (OpenAPI), RM-20 (me, saved, admin), RM-82 (GDPR endpoints), RM-12 (auth), RM-157 (worker ops), RM-171 (decisions D-14, L-010)

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

Renti is a paid SaaS for Polish residential **buy-to-let investors**. A user pastes an Otodom **SALE** listing URL;
the system fetches it, reads the photos and floor plans with a vision LLM, anchors rent and price against market
data, and returns a deterministic 10-year cash-flow valuation (`DealAnalysis`): yield, IRR, MOIC, CAGR, tax, CAPEX,
**Max Bid**, and a grade. A second surface, the **727-city yield radar** and a bargain **screener**, ranks markets.

| Item | Decision (blueprint) |
|---|---|
| Host | One OVH VPS-3 (6 vCore, 12 GB), Docker Compose, Caddy + FastAPI + Procrastinate workers + Postgres 17, **no Redis** |
| Server runtime | **Python only.** Node exists only to build the SPA |
| Auth | Google ID token first (`google-auth`), email magic link second, own sessions in Postgres; email/password added by owner request (ADR 0013; registration RM-203, login RM-204, recovery and change RM-205) |
| Billing | Pilot direction: Paddle one-time 1/5/10-report packs, card + PLN BLIK; credit ledger. Integration spec only; product/accounting approval and final prices pending. Earlier Stripe subscription design retained as historical reference |
| Free tier | 3 audits on verified sign-up, yield radar top 20 (proposed) |
| Jobs / progress | Procrastinate queues; SSE via Postgres `LISTEN/NOTIFY` + `audit_event` replay |
| Monitoring | **Better Stack** free tier (ADR 0009): errors and traces via the `sentry-sdk` client, uptime monitor, backup heartbeat; replaces Sentry |
| Budget | ≈ $13.38 net/month infra; OpenRouter spend is COGS governed by the credit ledger |

**Phase 1 = backend** (blueprint §4.8 steps 1–5, plus step 8 batch tasks), done offline. **Phase 2 (the Vite/React SPA in
`frontend/`) was authorised by the owner on 2026-10-15** (`agents.md` §0, #267); delivery follows `docs/FRONTEND-PLAN.md`.
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
| **Entitlement** | A staff-granted per-account row (`app.account_entitlement`, RM-438); `unlimited_reports` skips credit charging (audit `charge_source = admin_free`) and opens all of Rynek. Granted by `scripts/grant_entitlement.py`, never inferred from an e-mail address |
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
| G13 | Reference gallery/fit-out/questions/redesign workflows contain useful requirements but local files, float price bands and synchronous subprocess APIs | Their presence in the reference does not establish delivery in this rebuild; current report evidence gaps are confirmed in L-044 | Rebuild stable media identity, typed factual evidence and persistent tenant operations; use the feature-gap guide in §10 |
| G14 | GUS reference has multi-level indicator/REIS context; README and dated reviews lag some current fixes, and some exporter work is uncommitted | A project reference in #48 is not an implemented location contract; powiat proxies and composite scores must not become precise gmina/property valuations | Owner requested location context for gmina/powiat/województwo, reports and agents on 2026-10-16; contract proposal in §10, current gap L-042; no POC artifact import |

## 6. Legal and GDPR hot-spots (where the POC did it; tag the new code that does the same)

Per `rules/legal-tags.md`, tag the new implementations of these; features stay.

| Where in the POC | Tag |
|---|---|
| `otodom_city_report/client.py`, `headers.py`, `deal_analyzer/fetch.py` (browser-like headers, `fake-useragent`, `_next/data`) | `LEGAL[scraping]` |
| `deal_analyzer/resolve.py` (URL / ID → listing) | `LEGAL[url-analysis]` |
| `deal_analyzer/images/download.py`, `vision.py`, `layout_vision.py`, `export_jpegs.py`, `redesign.py` | `LEGAL[images]`, `GDPR[processor]` (OpenRouter) |
| `price_intel/sources/moniter.py`, `cenogram.py`, `bdl.py`, `demography.py`; `deal_analyzer/nominatim.py`, `osm_distance.py` (OSM usage policy) | `LEGAL[third-party-data]` |
| BDL source client and observation validator (`services/rm_worker/clients/bdl.py`): GUS BDL requests, quota gate, resumable cursor | `LEGAL[third-party-data]`, `LEGAL[scraping]`, `GDPR[processor]` (RM-386) |
| BDL persistence and ingestion (`location_*` tables in `rm_core/db/models.py`, `rm_core/location_repo.py`, `rm_worker/clients/bdl_quota.py`, `rm_worker/tasks/location_context.py`): public statistics, no personal data | `LEGAL[third-party-data]`, `LEGAL[scraping]`, `GDPR[retention]` (RM-391) |
| BDL indicators (`packages/rm_core/location_indicators.py`): intensity, trend, parent/peer comparison, rank; public statistics, no personal data | `LEGAL[third-party-data]` (RM-396) |
| Raw `listing_snapshot.payload` (may contain seller name / phone) | `GDPR[personal-data]`, retention + erasure path |
| Report Markdown / API results that echo listing text or photos to other tenants | `LEGAL[republication]` |
| Otodom rental corpus contracts (`packages/rm_contracts/market.py`): whitelisted analytical offer fields only, no seller data | `LEGAL[scraping]`, `LEGAL[third-party-data]`, `GDPR[personal-data]` (RM-377) |
| Report vision evidence (`apps/deal_analyzer/vision.py`: `EquipmentObservation`, `floor_plan_text`, `notes`; `services/rm_worker/vision_stage.py`): OCR text and media-linked equipment from listing photos and plans | `LEGAL[images]`, `LEGAL[republication]`, `GDPR[processor]` (RM-387) |
| Otodom rental corpus persistence (`packages/rm_core/market_corpus.py`, `market_*` tables, migration 0015): listing facts only, no seller data | `LEGAL[scraping]`, `LEGAL[third-party-data]`, `GDPR[personal-data]` (RM-385) |
| Frontend Rynek map, comparison and context (`frontend/features/market/MarketMap.tsx`, `MarketExplorer.tsx`, `ContextSection.tsx`): aggregates and official boundaries, no personal data | `LEGAL[republication]`, `LEGAL[third-party-data]` (RM-282) |
| Place mapping, BDL context and free-tier access (`rm_core/location_mapping.py`, `location_profile.py`, `market_access.py`, `rm_api/market.py`), map geometry (`frontend/public/geo/`): public statistics and boundaries, no personal data | `LEGAL[third-party-data]`, `LEGAL[republication]`, `GDPR[personal-data]` (RM-282) |
| Otodom catalogue discovery (`services/rm_worker/importers/otodom_catalogue.py`, `scripts/seed_catalogue.py`, `docs/market/otodom-catalogue-v1.json`) and coverage manifest (`packages/rm_core/market_manifest.py`): location paths, names and counts only | `LEGAL[scraping]`, `LEGAL[third-party-data]` (RM-411) |
| Otodom corpus importer (`services/rm_worker/importers/otodom_corpus.py`, `fetch_corpus_search` in `clients/otodom.py` and `listing_source.py`, tasks `sync_corpus_location` and `dispatch_corpus_nightly` in `tasks/batch.py`): search tiles, whitelisted listing facts, no seller data | `LEGAL[scraping]`, `LEGAL[third-party-data]` (RM-392) |
| Rental daily summaries (`packages/rm_core/market_history.py`, `market_daily_summary`, task `publish_market_summaries`): aggregates of asking rents, no personal data | `LEGAL[third-party-data]`, `LEGAL[republication]`, `GDPR[personal-data]` (RM-395) |
| District capture and statistics (`rm_core/market_corpus.py` `_attach_districts`, `rm_core/market_history.py` `districts`, `CorpusImporter.sweep_districts`, tables `market_district`, `market_offer_district`): the site's district ids and names, no seller data | `LEGAL[scraping]`, `LEGAL[third-party-data]`, `LEGAL[republication]`, `GDPR[personal-data]` (RM-439) |
| Experimental locality index (`rm_core/location_index*.py`, `rm_api/market.py` ranking routes): derived from public GUS statistics | `LEGAL[third-party-data]`, `LEGAL[republication]` (RM-439) |
| Frontend Rynek (`frontend/features/market/`): the market aggregates above shown to signed-in users, asking rents only | `LEGAL[republication]` (RM-422) |
| Product media store (`packages/rm_core/object_store.py`, `MEDIA_*` settings, `scripts/probe_media_store.py`): normalised room photos and generated images in the private `rent-monitor` R2 bucket (default or EU endpoint), 30-day / 7-day retention | `LEGAL[images]`, `GDPR[processor]`, `GDPR[retention]` (RM-447) |
| Market read API (`services/rm_api/market.py`, `packages/rm_contracts/market_api.py`): the aggregates above served to signed-in users, statistics withheld under 10 priced offers | `LEGAL[third-party-data]`, `LEGAL[republication]`, `GDPR[personal-data]` (RM-421) |
| Media manifest (`packages/rm_core/media.py`, `services/rm_api/media.py`, `MediaEvidence` in `rm_core/db/models.py`): metadata and digests of listing photos and plans | `LEGAL[images]`, `LEGAL[republication]`, `GDPR[retention]`, `GDPR[erasure]` (RM-376) |
| Frontend saved listings (`frontend/features/saved/`): the person's free-text notes and listing ids | `GDPR[personal-data]`, `LEGAL[republication]` (RM-276) |
| Frontend credits and purchases (`frontend/features/billing/`): order state, invoice links, Paddle.js with the public client token | `GDPR[processor]`, `LEGAL[tax-invoice]` (RM-277) |
| Frontend settings (`frontend/features/settings/SettingsPage.tsx`): the account's e-mail and name, sessions' IP and user agent, data export, account deletion | `GDPR[personal-data]`, `GDPR[erasure]` (RM-278) |
| Frontend analyses cards/table (`frontend/features/analyses/list/AnalysesPage.tsx`, `AnalysesTable.tsx`), showing listing ids and asking-price summaries | `LEGAL[republication]` (RM-275, RM-343) |
| BDL registry, reference and refresh (`packages/rm_core/bdl_metrics.py`, `bdl_reference.py`, `services/rm_worker/importers/bdl_context.py`, `tasks/bdl_refresh.py`): public GUS statistics, no personal data | `LEGAL[third-party-data]`, `LEGAL[scraping]`, `GDPR[processor]` (RM-48) |
| Risk-free rate (ECB statistic: `services/rm_worker/clients/macro.py`, `services/rm_worker/tasks/macro.py`, `packages/rm_core/risk_free.py`, migration 0019) | `LEGAL[third-party-data]` (RM-210) |

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
and responsive interactive home, analyses-list and separate city-context prototypes with fictional fixtures. `design/v1/` holds the warm editorial direction; `design/v3/` (13 Oct) is a light-first alternative with an interactive login demo, report, market page and logo explorations; `design/v2/` is an architectural alternative, now light by default with a saved dark option, renti.tech logo/favicon, animated navigation and button/icon hover feedback with reduced-motion support, an app-wide dashboard, separate URL/manual analysis entry, local interior/listing-assistant design flows, settings/terms/privacy placeholder pages, and a dedicated analysis-page scaffold/UX contract (full analytic rendering deferred). Its analysis cards need replacement, pagination and a table-view option; Rynek is a placeholder omitting much of the available market data ([L-024](docs/LIMITATIONS.md#l-024--v2-analysis-collection-and-market-views-are-placeholders)). The owner selected V2 as the frontend starting point (2026-10-15); its principles are defined while placeholder layouts may evolve. The [implementation handoff](design/v2/implementation-guide.md) covers a proposed headless design system, tooling/CI and phased delivery. The handoff was verified against the code and turned into slice issues #263-#286 ([`docs/FRONTEND-PLAN.md`](docs/FRONTEND-PLAN.md), RM-262); the UI starts only after the API smoke test captures samples into the gitignored `data/` (#263). This remains a Phase 2 design artifact, not a production SPA;
`frontend/` and backend contracts are unchanged.

## 9. Open decisions (owner: you)

From the blueprint §5 and TOOLCHAIN §8, plus those found here. Do not guess on money, auth or anything irreversible.

- [x] `migrations` CI job on and required (RM-68)
- [x] `invariants` CI job on and required (RM-89): the four named tests exist (RENT, asking≠deed, admin fee, deterministic math); invariants 5 and 6 and the ±15% clamp are added by N-08/N-10
- [x] Port the POC? **No** — greenfield (ADR 0001, RM-2)
- [x] Market-data import policy (owner decision, 2026-10-14; #209 planning): use the owner-verified 727 Otodom locations; **2026-10-16 scope clarification: all catalogue locations are the completion target**, with offer-level Postgres storage, full bootstrap once, nightly last-24-hours new offers, immutable existing offers, 90-day age archive and durable daily trends. This and GUS BDL locality context are the next feature batch (feature-gap guide §0); a largest-city rollout is only intermediate. SIMC validation deferred; catalogue artifact, implementation and filtered-list contract verification remain pending. [Guide](docs/OTODOM-NIGHTLY-IMPORT.md).
- [x] Engine specification approved with amendments: `docs/ENGINE-SPEC.md` (RM-73); tax constants flagged for the accountant
- [x] Feature-batch scope (owner clarification, 2026-10-16): gallery, equipment/OCR, seller questions, manual source/uploads, Rynek and interior operations all remain required; Otodom/BDL expand that batch rather than deferring G-01–G-05. See feature-gap guide §0/§4. Exact provider/pricing choices remain open where noted.
- [ ] Separate analyst text-audit scope (§4.3); seller questions do not depend on enabling this mode.
- [x] VAT presentation: 100 zł shown gross (81.30 net + 23 %), Stripe prices tax-inclusive (D-03); accountant to confirm VAT-payer status (#41)
- [x] Pilot product direction: owner selected one-time Paddle packs of 1/5/10 reports, without subscriptions; [PADDLE-INTEGRATION.md](docs/PADDLE-INTEGRATION.md). Implementation and provider validation remain pending; supersede ADR 0005 with implementation.
- [ ] Pack pricing: owner suggested 5/40/70 PLN; recommended 10/40/70 PLN to make bulk packs cheaper per report and cover Paddle's fixed fee. Also decide signup reports (currently 3) and unused-unit expiry. Product/accounting unknowns: L-015/L-016.
- [ ] Pro allowance (40 is a placeholder until COGS is measured); free-tier scope
- [x] SQLAlchemy 2.0 and Stripe SDK pin at #14: ADR 0007 accepted (D-02)
- [ ] Gemini and Claude auth in Actions; GitHub plan for private-repo rulesets
- [x] D-13 Google links or creates accounts only for `@gmail.com` or a matching `hd`; others confirm by magic link (ADR 0010, RM-12)
- [ ] Polish legal review of Otodom scraping before charging (blueprint §5, not legal advice)
- [x] D-14 R2 backups in the EU jurisdiction (fixed at creation), `rentmonitor-backups`, WAL-G retention 14 days: decided (ADR 0011, RM-171)

## 10. Where to look

| Need | Open |
|---|---|
| Interior media store decision (private R2, default jurisdiction approved 2026-10-21, ADR 0014) and runtime-probe item B-025 (#284 research: `docs/INTERIOR-RESEARCH-2026-10-21.md`, prompt `docs/CLAUDE-INTERIOR-PROMPT-2026-10-21.md`) | `docs/adr/0014-product-media-object-store.md`, `docs/BLOCKERS.md` |
| October 21 owner approval of the existing `rent-monitor` bucket; Polish catalogue access routes (webePartners, Convertiser, Awin) and the #448-#451 follow-up | `docs/OWNER-DECISIONS-2026-10-19.md` (October 21 addendum), `docs/INTERIOR-POLAND-SOURCES-AND-FOLLOWUP-2026-10-21.md` |
| POC-is-reference and production bar | `.agent/rules/poc-reference.md`, `docs/adr/0001-greenfield-rewrite.md` |
| Expensive-to-reverse decisions (runtime, queue, auth, billing, host, pins) | `docs/adr/0002`–`0009` |
| Rules, invariants, git flow, PR template | `.agent/agents.md`, `.agent/rules/*.md`, `.github/pull_request_template.md` |
| Frontend correctness rules (session transitions, transport, copy, numbers, evidence) | `.agent/rules/frontend.md` (RM-320, from the 2026-10-15 audit) |
| Parallel Claude feature lanes, all shared-file conflicts, isolated writers and same-PR integration | `docs/PARALLEL-FEATURE-DELIVERY.md`, `.agent/rules/parallel-work.md`, `docs/parallel-handoffs/`; L-043 (current dispatcher still serial) |
| Initial Claude execution prompt for the complete feature batch after foundation merge | `docs/CLAUDE-FEATURE-GAP-KICKOFF.md` (RM-374) |
| Post-merge feature-gap audit and continuous-worker completion prompt | `docs/FEATURE-GAP-REVERIFICATION-2026-10-18.md`, `docs/CLAUDE-FEATURE-GAP-FINISH-PROMPT.md` (dated audit and execution instructions, not delivery claims) |
| Current delivery audit after OCR persistence, tested frontend gaps and next Claude prompt | `docs/DELIVERY-AUDIT-2026-10-19.md`, `docs/CLAUDE-DELIVERY-PROMPT-2026-10-19.md` (dated evidence and execution instructions; no launch claim) |
| Confirmed owner policies, delegated choices, beta/provider permissions and supplied key-name inventory | `docs/OWNER-DECISIONS-2026-10-19.md` (supersedes older open-policy questions; external sign-offs remain unconfirmed) |
| Authorized live vision-v2 sample, cost and source-association defects | `docs/LIVE-VISION-ID4DACX-2026-10-19.md` (photo/equipment stage only; no positive OCR or full journey claim) |
| Feature batch versus production readiness: corrected pasted assessment, covered/uncovered blockers and companion launch work | `docs/FEATURE-GAP-READINESS-COVERAGE-2026-10-17.md` (assessment, not delivery evidence) |
| Architecture, schema, Stripe, auth, tests | `docs/BLUEPRINT.md` §2–§4 |
| Launch-city Otodom bootstrap, nightly incremental imports, recovery and 90-day archiving | `docs/OTODOM-NIGHTLY-IMPORT.md` (phase 1 contracts in `packages/rm_contracts/market.py`, RM-377, L-048 to L-050; Postgres corpus and migration 0015 in RM-385, L-056 to L-060) (#209 planning; implementation pending); importer logic in RM-392 (L-070 to L-073); daily summaries in RM-395 (L-074 to L-079) |
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
| V2 frontend implementation, headless components, environment/linters/CI and Claude delivery checklist | `design/v2/implementation-guide.md`, `design/v2/design-system.md`, `design/v2/frontend-tooling.md`, `design/v2/implementation-checklist.md` |
| Frontend delivery plan: handoff verification, API smoke + samples in `data/` first, e2e interaction-coverage gate, slice issues | `docs/FRONTEND-PLAN.md` (RM-262) |
| Frontend audit (translations, Intl, session correctness, proposed frontend pipeline) and its re-verification on `staging` | `frontend/docs/AUDIT-2026-10-15.md`; limitations L-030–L-032; tracker #314 |
| Report (`DealAnalysis`) JSON Schema and its compatibility rule | `docs/deal-analysis.schema.json`, `docs/REPORT-SCHEMA.md` (RM-266) |
| Missing Rynek/manual/interior features and report photos/equipment/seller questions: source audit, existing-issue completeness, proposed tickets and implementation steps | `docs/FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md` (owner-requested audit; proposed issues not filed), L-044 |
| API smoke scenarios (every OpenAPI operation) and local response samples | `tests/smoke/`, `scripts/capture_api_samples.py`, `make api-samples` (RM-263, L-028) |
| Phase 2 design direction (prototype, principles, spec) | `design/README.md` (#44 input; no backend or rule change) |
| Owner-only blockers | `docs/BLOCKERS.md`, `.agent/rules/blockers.md` |
| Agent bot setup | `docs/AGENT-BOT.md`, `scripts/setup_agent_bot.sh` |
| Launch checklist (incl. back to private) | `docs/PRE-DEPLOYMENT.md` |
| POC architecture map and data flow | `~/Projects/otodom-rent-report/apps/ARCHITECTURE.md` |
| POC pipeline call order, config files | `…/apps/deal-analyzer/PIPELINE.md`, `config/*.yaml` |
| POC audit (origin of "audit 3.x" references) | `…/docs/APP_AUDIT_AND_ROADMAP.md` |
| POC limitations register | `…/apps/LIMITATIONS.md`, `…/apps/deal-analyzer/docs/LIMITATIONS.md` |
| BDL multi-level location context, indicator ranks, REIS-style fundamentals, audit/agent fact pack and issue amendments (owner-requested scope; implementation pending) | `docs/BDL-LOCATION-CONTEXT-CONTRACT.md`, L-042, L-045 to L-047; remaining policy decisions B-023; phase 1 code in `packages/rm_contracts/location_context.py` and `packages/rm_core/location_contracts.py` (RM-378); source client and validator in `services/rm_worker/clients/bdl.py` (RM-386, L-053 to L-055); persistence, quota gate and ingestion task (migration 0016) in RM-391, L-064 to L-069; per-metric indicators in RM-396 (L-080 to L-084) |
| GUS reference lessons (read-only; no artifact import; compare dated reviews with current source) | `~/Projects/gus-stats-poc/README.md`, `docs/REIS_V3_REVERIFICATION.md`, `REVIEW_ROADMAP.md`, `src/gus_stats_poc/{metrics,investment_score,analyze}.py` |
