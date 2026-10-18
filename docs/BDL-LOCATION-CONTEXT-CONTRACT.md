# BDL location context and rankings: contract proposal

**Date:** 2026-10-16. **Delivery state:** requirements and contract proposal; no BDL importer, location-profile API or REIS integration has been implemented here. `STATUS.md` remains the delivery-state source.

**Owner direction, 16 October:** inspect `/Users/marcin/Projects/gus-stats-poc` and include its useful location data/ranking capabilities in this app, covering gmina, powiat and województwo and providing context to the analyzing agent. This authorizes read-only reference inspection and establishes product scope. It does not select numerical score weights, publication thresholds or a data-import mechanism.

**Next batch:** the owner also confirmed that BDL and complete Otodom rental-market ingestion belong in the same next feature batch. The [feature-gap guide §0](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md#0-next-implementation-batch-rynek-data-and-location-context) coordinates the work; the [Otodom guide](OTODOM-NIGHTLY-IMPORT.md) specifies all-location Postgres storage, full bootstrap, nightly last-24-hours new offers and daily trend history. BDL annual statistical history and Otodom rental cohorts stay separately sourced/versioned; neither workstream is satisfied by the Rynek placeholder or one-city sample.

## 1. Does the existing BDL contract cover this?

**Only partially.** [Issue #48](https://github.com/wedbew/rent-monitor/issues/48) explicitly references the GUS project README and `docs/REIS_V3_IMPLEMENTATION_VERIFICATION.md`. It requires approved metrics, units, territorial grain, a versioned TERYT crosswalk, provenance, completeness gates and reconciliation. It does **not** explicitly require:

- location profiles and ancestry at all three requested administrative levels;
- current values, historical trends and parent/country comparisons;
- per-indicator peer ranks and percentiles;
- a separately versioned REIS-style location fundamentals index;
- structured context consumed by an audit/agent and displayed in its report;
- a hierarchical Rynek experience using the same published dataset.

There is no executable BDL contract module in the current app. `services/rm_worker/context.py:33` implements only rent-comparable loading and a configured risk-free rate. `packages/rm_core/db/models.py:667` defines price/rent sidecar kinds, not a socioeconomic observation/ranking model. Blueprint `/api/market/*` and #282 are broad market surfaces, not proof these location requirements are already covered.

**Required action:** extend #48 with the acceptance in §9; retain #49 for Otodom coverage; add explicitly linked implementation children for location analytics and report context. Proposed issue bodies are in §10. No GitHub issue was created or amended during this review.

## 2. Reference evidence and limits

Inspected GUS project HEAD **fd25b15b6f99c23949f7fad8c23b126e854bc4e6** and its current working tree. At inspection it had modifications to `docs/INVESTMENT_SCORE_REVIEW_AND_UPDATE_PLAN.md`, `scripts/export_web_data.py`, `web/app.js`, `web/style.css`, plus untracked `GUS_STATS_MIGRATION_PLAN.md`. Source findings involving those files describe that working tree, not solely the committed SHA.

Read the catalog, reference crosswalk, metric/ranking/scoring code, review roadmap and verification documents. No POC code was executed, data imported or remote GUS request made. Metadata marked verified in the POC is **reference evidence**, not freshly verified metadata or approved product input here.

| Source in `gus-stats-poc` | Confirmed useful capability |
|---|---|
| `catalog.json` | 24 requested raw metrics: 22 with reviewed variable IDs, two land-market metrics unresolved. |
| `units.json`; `src/gus_stats_poc/units.py` | Reviewed snapshot containing 2,479 whole gminas, 380 powiats, 16 województwa and country identity; resolution validates ancestry/levels. These are snapshot counts, not timeless constants. |
| `src/gus_stats_poc/metrics.py:18` | Ten derived age-share, per-population and floor-area indicators. Seven raw/derived metrics are explicitly powiat proxies. |
| `metrics.py`; `analyze.py` | Comparable windows, signed/percentage-point/ratio/share comparisons, competition ranks, midrank percentiles, eligible/expected counts and coverage. |
| `investment_score.py:94`, `:167`, `:449` | REIS v3 five-pillar score, family/temporal/cohort weights, completeness gates and diagnostic exclusions. |
| `boundary_changes.py`; `analyze.py:198` | Reviewed territorial-break exclusions and reasons, keeping raw observations while suppressing misleading comparable-growth ranks. |
| `analyze.py:567`; `scripts/export_web_data.py:510` | Current code writes a scoring specification and exporter reads one if present. Exporter still allows fallback to installed constants when absent. |
| `REVIEW_ROADMAP.md`, D2 | Historical nationwide fiscal/unemployment completion evidence. The README's older “six pending” text is superseded by D2; it is not a reason to omit those families. |
| `docs/REIS_V3_REVERIFICATION.md` | Historical defects and evaluation cautions. Several have subsequent fixes visible in current code; the dated finding list cannot be treated as the current defect list unchanged. |
| `GUS_STATS_MIGRATION_PLAN.md` | Untracked plan aimed at a separate ETL app, including raw/derived ownership and release coherence lessons. Its Airflow/dbt architecture and import permissions do not apply to RentMonitor. |

Current source has `missing_level` gates, ratio-based national cohort checks, `get_reis_spec()` and specification output. Thus the September follow-up's statements that these mechanisms are absent are stale for those specific code paths. Their numerical correctness and complete artifact lineage have **not** been re-tested in this audit. The present fallback to live scoring constants and heuristically inferred reference-cohort size remain design patterns to avoid.

## 3. Location information to include

The following inventory is a **candidate product catalog derived from reference metadata**. Pin fresh reviewed BDL variable signatures, units, source levels, availability and attribution before production activation. Preserve every observation's actual period; the newest year differs by metric.

| Family | Candidate measures | Native level in inspected catalog | How it helps a location profile |
|---|---|---|---|
| Population and age | Total; pre-working, working and post-working age; derived age shares | Gmina (BDL 6) | Population scale, age mix and comparable change. Do not equate population with households or actual rental demand. |
| Demographic movement | Net migration; natural increase; each per 1,000 population | Gmina | Direction and scale of demographic change; signed changes cannot use naive percent growth around zero. |
| Housing development | Completed dwellings, completed floor area, dwelling stock; per-population intensities | Gmina | Supply/development context. Higher construction is activity; it is not automatically better for rental yield. |
| Transaction market | Dwelling transaction count; median transaction PLN/m²; transaction intensity and price-median trends | Powiat (BDL 5) | Deed-market context, clearly labelled as powiat proxy when attached to a gmina. Median changes reflect changing sold-property mix, not guaranteed appreciation of the analyzed flat. |
| Permits | Dwellings covered by building permits; per-1,000 intensity | Powiat | Development pipeline context; distinguish annual total from overlapping cumulative periods. |
| Employment/income | Average gross earnings; standard registered unemployment rate | Powiat | Wider labor-market context; neither is measured household disposable income at the property's address. |
| Business/local unemployment | REGON entities, entities per 10,000 residents; unemployed as share of working-age population | Gmina | Business activity and local labor indicators. This unemployment denominator differs from the standard powiat rate. |
| Municipal receipts | Property-tax, municipal PIT/CIT receipts; PIT per resident; own revenue per resident | Gmina | Revenue capacity/context, not household income, tax rates charged on this flat, budget solvency or service quality. |
| Land prices/transactions | Two unresolved catalog entries | Unresolved | Explicitly unavailable; do not replace them with agricultural prices or municipal land disposals. New official-source research is a separate scope. |

Distinguish raw metrics from derived metrics and scored components. Reference REIS does not score all 22 inputs independently; some are descriptive and fiscal measures overlap. Preserve useful explanatory data even when it is excluded from the composite.

### Administrative hierarchy

- Resolve the property's actual gmina → powiat → województwo → Polska using a reviewed, versioned TERYT/BDL identity crosswalk. Retain leading zeros and gmina type, BDL level and parent IDs. BDL IDs and TERYT IDs are distinct identifiers.
- A city name/slug is not a unique territorial key. Use verified location mappings; where an Otodom locality/SIMC is available, map it to gmina explicitly. A postcode or same-name match alone is insufficient. Ambiguous location remains unresolved and may use only a labelled confirmed wider area.
- Cities with powiat rights have gmina and powiat administrative roles. Preserve both IDs/roles instead of dropping a level or counting the population twice. For urban-rural gminas, do not mix the whole gmina with its town/rural parts.
- Provide published powiat/województwo/country observations when available. Never create parent medians, unemployment rates or prices by averaging children. Sum only metrics whose contract explicitly declares additivity and compatible scope/period.
- Freeze territorial vintage and boundary exclusions with each release. A territory split can break a growth comparison without making its raw current value invalid.

## 4. Separate metric rankings from the composite index

### Indicator rankings

Each rank declares metric, unit level, level/change type, cohort scope/identity, period/window, direction, eligible/expected/missing/excluded counts and methodology version. A gmina metric can have national, województwo and powiat peer cohorts where meaningful. A powiat-native proxy is ranked **among powiats**, then shown to a gmina as parent context; it is not an independent gmina measurement.

Use deterministic tie/percentile rules and declare them. The reference uses competition ranks (1, 2, 2, 4) and midrank percentiles; a one-unit cohort has no meaningful relative percentile. Neutral size/price orderings should say “higher/lower,” not “better/worse.” For unemployment, explicitly state the chosen lower-is-favorable direction. Trend endpoints must match the benchmark window; never compare one area's 2015–2025 change to another's 2019–2024 change without an explicit unavailable state.

### Composite location fundamentals

The reference v3 candidate has five pillars: demographic demand **30%**, economic activity **20%**, powiat transaction activity/price momentum **20%**, housing development activity **15%**, municipal revenue capacity **15%**. It blends national/województwo percentiles at **65/35** and uses family-specific level/trend weights. These numbers describe the POC; **they are not an approved RentMonitor scoring policy**.

Include an explainable location-fundamentals index in the implementation scope, initially behind a separately controlled experimental/shadow release until the methodology is accepted. Return raw weighted points, calibrated percentile, national rank, component contributions, coverage and eligibility as distinct fields. Do not call a diagnostic available-input score a national rank. Do not reuse the property A–E/N financial grade or the rental-yield radar score.

Required protections:

1. Missing required families and positively weighted temporal components make the main score ineligible. Never let removal of an unfavorable observation produce a newly eligible stronger score. Diagnostic partial values can remain visible with missing reasons.
2. Freeze approved weights, direction, temporal/cohort policy, tie rules, minima and the authoritative reference population in a full specification and hash. Never infer national completeness from “at least 50 rows” or hard-code a permanent number of gminas.
3. Separate observation coverage, component coverage and eligible national-cohort share. The POC's 85% component, 70% national-share and 50-unit gates are candidates for review, not selected product thresholds. Expose exclusion composition by region/type; a large cohort can still be systematically biased.
4. Keep mixed vintage visible per component. A report labelled 2025 cannot relabel 2024 price observations as 2025. Comparable endpoints do not establish a continuous full annual series.
5. Municipal revenue comparability needs budget-type and methodology review. The reference flags ordinary gmina versus city-with-powiat-rights fiscal comparability and breaks in fiscal series. Publish the underlying facts with caveats; do not silently score incomparable receipts as municipal “financial health.”
6. Neither the relative score nor price-median change predicts a particular property's rent, yield or IRR. No new demographic/ranking multiplier may change approved engine finance without a separate ENGINE-SPEC decision and tests.

## 5. Proposed persisted and API contracts

These are design names, not existing tables or routes. Implement in small issue-owned slices.

| Record | Required content |
|---|---|
| `TerritoryReference` | Canonical IDs/type/level, parents, valid dates, reference/crosswalk hash, source, boundary-change annotations and reviewed locality mappings. |
| `BdlMetricDefinition` | Key/version, variable/signature, unit/scale/frequency, native/allowed aggregate levels, additivity, denominator/derivation, eligible attribute policy, direction and actual availability. |
| `BdlObservation` | Source unit/metric/year, raw/normalized value and attribute, null/suppressed/missing reason, capture/revision time and source hash. Money remains Decimal/NUMERIC/string. |
| `LocationPublication` | Immutable release ID, reference/catalog hashes, input digests, collection/completeness states, publication time and per-metric coverage/freshness. Atomic pointer to last valid release. |
| `LocationMetricView` | Requested unit plus actual measured unit/level, proxy flag, actual period/window, value/trend, benchmark rows, ranks/percentiles, sample/coverage/exclusion metadata and evidence IDs. |
| `LocationFundamentals` | Separate schema/algorithm/spec versions, raw points, percentile/rank, pillar/family contributions, coverage, eligibility/reasons, reference cohort and frozen specification. |
| `AuditLocationContext` | Audit/property location resolution, selected release IDs, fact/evidence projection, explicit unavailable/proxy/stale/boundary flags; immutable audit-time snapshot or versioned enrichment with disclosed creation time. |

**Do not put demographics under `bdl_deed`.** `MarketSidecar` currently requires asking/deed/rent semantics through the invariant CHECK; a population or unemployment observation has no price basis. Add separate typed observation/context records through an expand migration and documented blueprint change. Keep deed prices distinct from asking prices and contextual non-price statistics; do not weaken the existing CHECK.

Suggested read operations under #21:

- location search/resolve with canonical typed IDs;
- `GET /api/market/locations/{level}/{id}` for ancestry and a versioned profile;
- location metric history/comparisons and ranking queries with explicit cohort/window filters;
- `GET /api/audits/{id}/location-context` if context is a separately versioned audit enrichment, with the normal tenant-scoped 404 behavior.

Choose exact paths and context-in-result versus enrichment before implementation. Validate every response at runtime in the SPA and generate OpenAPI/types/sample scenarios. Apply agreed entitlements on the server. Public aggregates and private audit associations have different authorization needs; a public territorial ID must not reveal a tenant's audit.

## 6. How the analyzing agent and UI use the data

Expose an injectable `LocationContextRepository` read seam taking resolved territorial identity and an approved release/as-of policy. The worker loads a **bounded structured fact pack**, never the POC's web bundle or a directory of thousands of reports. Include location ancestry, selected indicator values/trends, parent comparisons, eligible ranks and score components, each with year, measured level/proxy label, provenance and caveats. Bound histories and benchmark rows; do not send all nationwide observations to a model.

Provide useful deterministic context first: for example, show a municipality's migration trend and its powiat's transaction-price median as two separately sourced facts. Report missingness instead of filling a location profile with a neighboring area's statistics. The financial engine should remain operable under its existing context/credit policy when optional socioeconomic context is unavailable; add a section-specific status, not an invented success or an undocumented whole-audit failure.

If an agent later summarizes these facts, it must cite evidence IDs, preserve period/level caveats and avoid causal claims or financial recalculation. A new narrative-generation role requires its own approved provider/prompt/privacy scope; this contract does not silently expand the engine LLM role. The existing deterministic report and question rules can consume the fact pack immediately once implemented. Seller questions may identify a confirmed data gap; they must not invent zoning plans, neighborhood developments or a property's defects from a municipal rank.

Show the same context in two places:

1. **Analysis report — “Kontekst lokalizacji”:** breadcrumb hierarchy; factual indicators; level versus change; source year/freshness; proxy labels; comparison explanations; optional experimental fundamentals breakdown; link to Rynek. Preserve the audit-time release when current data changes.
2. **Rynek:** browse/search gmina, powiat and województwo; drill to parent/child profiles; filter per-metric peer rankings; view trends and published higher-level aggregates. Composite gmina scores must not be averaged into a purported powiat/województwo score. Separate higher-level composites require their own methodology; until then show indicators/aggregates at those levels.

## 7. Acquisition and architecture

Use the GUS project as read-only requirements and defect evidence under current #48 rules. The owner's request permits inspection, but does not revoke #48's no-artifact-import rule. Do not copy its datasets, code, fixtures or `web/data` exports into this app. Freshly acquire approved source observations through injectable clients, bounded retries/deadlines, resumable pagination, shared quota accounting and Postgres checkpoints; reconstruct small test fixtures independently.

An alternative future dependency on a separately operated ETL publication needs an explicitly approved, versioned upstream contract: ownership, freshness/completeness, identity, access, provenance, failure behavior and deployment dependency. The GUS migration plan is a proposal for another destination, not evidence such a service exists. Do not add Airflow/dbt/SQLite coordination or a second runtime to RentMonitor by following that plan verbatim.

Use frozen full input/reference releases and distinguish collection time from source revision time. Partial fetches cannot silently become national publications. Retry only unfinished work, preserve the last valid release, and make concurrent publication idempotent. Snapshot retention and operational cadence remain implementation decisions. The Otodom rental 90-day cohort is unrelated to annual BDL statistical history.

Pure statistical computations belong in newly written Python analytical modules; financial calculations stay exclusively in `apps/deal_analyzer`. API/worker orchestration and React consume published results. Source terms/attribution and applicable `LEGAL[third-party-data]`/`LEGAL[republication]` tags apply. This audit makes no legal conclusion about reuse.

## 8. Delivery slices and evidence

> **Status (2026-10-18):** LCTX-01 phase 1 (contract models and pure ranking, gate and comparison logic) is implemented offline in `packages/rm_contracts/location_context.py` and `packages/rm_core/location_contracts.py` (RM-378). Persistence, importer and API are phase 2. LCTX-01b part 1 (injectable source client, quota gate, resumable cursor and observation validator, `services/rm_worker/clients/bdl.py`, RM-386) is implemented offline; persistence, cursor, shared quota and the resumable ingestion task (migration 0016, RM-391) are implemented offline; the reference loader, reviewed bindings and the indicator/ranking publication slice remain.

1. **#48 contract/reference slice:** metric-definition and territory models; metadata validation; explicit scope/threshold decisions; fixtures; no network in tests.
2. **BDL ingestion slice:** approved annual metrics/native and parent levels; raw/attribute provenance; resumable quota-aware tasks; real-Postgres state; truthful partial/complete outcomes.
3. **Location indicator slice:** intensity/trend/comparison/rank modules and versioned immutable publication. Publish usable individual indicators before a composite is accepted.
4. **Location-index slice:** approved frozen specification, completeness/anti-inflation gates, component diagnostics, shadow evaluation and explicit activation decision.
5. **#21 API + #282 profile UI slices:** hierarchy, profile/history/ranking contracts and views, generated clients and sample/browser evidence.
6. **Audit context slice:** injectable bounded repository, immutable evidence linkage, report section and fact-pack consumption by question rules/authorized agents.

Split further to one module/route group, at most one migration and approximately 400 changed lines per agent-ready ticket. Serialize migration ownership. Update blueprint schema/routes through the repository's approved architecture-change workflow before altering those boundaries. This document records a proposal rather than silently changing the blueprint.

## 9. Acceptance additions for #48 and consumers

- Catalog accounts for all 24 reference candidates as selected/deferred/unavailable; each selected metric has reviewed source signature/unit/grain and tests. Two unresolved land fields remain explicitly unavailable.
- Gmina/powiat/województwo/country ancestry and reference versions round-trip; leading-zero, same-name, urban-rural, city-with-powiat-rights and unresolved listing-location cases pass.
- Powiat-native price/earnings/unemployment/permit data cannot serialize as a measured gmina statistic. Published parent rates/medians are never reconstructed by averaging children.
- Genuine zero, suppression, missing observation, invalid source attribute, stale observation and withheld comparison are distinct. Per-metric vintages and matched trend windows remain visible end to end.
- Territorial-break windows are excluded/flagged with reasons; raw facts remain available. No artificial demographic collapse becomes an investment signal.
- Ties, one-unit cohorts, signed/near-zero changes, ranking direction, duplicate observations and mixed versions have deterministic tests.
- Masking any required unfavorable level/trend/family cannot make an incomplete profile eligible or inflate a published comparable score. Partial reference sets with many rows still cannot claim national standing.
- Frozen catalog/reference/input/scoring hashes reproduce output; mixed/unknown versions and missing saved specs fail rather than using installed constants. Individual metric rank and composite algorithm versions are independent.
- Audit context is bounded and pinned to an identified publication; unavailable optional context is explicit. Audit financial outputs and the property grade remain unchanged by informational enrichment.
- Cross-tenant context access is 404; fact pack, report and Rynek show the same units/years/proxy and missingness semantics. Five distinct UI cases cover ordinary gmina, city-powiat, ambiguous location, boundary break and partial/stale context.
- Actual data collection, offline tests, live source verification and deployed UI evidence are recorded separately. Historical POC test/data counts are not current product acceptance evidence.

## 10. Issue amendments and missing issue proposals

### Amend #48 — BDL metric contract, provenance and completeness gates

**Add to scope:** use `gus-stats-poc` as requirements reference for multi-level location profiles, metric history/comparisons/rankings and a separate explainable fundamentals index. Implement the contract in this document; this is more than sale-price ingestion. Record the 16 October owner direction and use §9 as acceptance. Keep exact metric selection, scoring/coverage thresholds, fiscal comparability and source review explicit. Link current source and the superseding review, not only the first September verification.

**Proposed files:** `packages/rm_contracts/location_context.py`, `packages/rm_core/location_contracts.py`, reviewed metric/territory definitions, `tests/unit/test_location_contracts.py`; later migrations/importer files in separate children. Names are proposed, not existing modules.

### Amend #21 and #282 — location profile APIs and Rynek hierarchy

**Add to scope:** typed location identity, ancestry and profiles at gmina/powiat/województwo; native versus proxy data, metric history/comparisons/ranking cohorts, and experimental composite diagnostics with server-side entitlement/publication gates. #282 consumes those contracts with source/year/coverage and drill-down. A city-only price table does not close this requirement.

### LCTX-01 — `feat: publish BDL location indicators and peer rankings across administrative levels`

**Problem:** current app has rent sidecars but no typed demographic/economic/housing/fiscal location publication. #48 covers contract approval; it does not implement the analytics.

**Scope:** approved fresh ingestion, territorial references, metrics/trends/comparisons/rankings and atomic versioned publication under §§3–5/7–9. Native-level proxies remain explicit. **Depends on:** #48 contract and approved metrics/cohort policy; source/attribution decisions. **Files:** new Python analytical module, core observation/publication repositories, batch importers, migrations and offline/real-Postgres tests. Split ingestion and analytics into separate PR children.

### LCTX-02 — `feat: add an explainable, versioned location fundamentals index`

**Problem:** the reference REIS ranking provides useful locality context, but this app has no equivalent contract or safe calibration/publication path.

**Scope:** accepted scoring specification, per-family/temporal/proxy contributions, raw points versus percentile/rank, diagnostics, completeness/reference gates, shadow evaluation and approved activation. **Depends on:** LCTX-01 and explicit methodology approval; no change to IRR/Max Bid/property grades. **Done when:** §9 masking/version/reference tests pass and fiscal/type/region sensitivity is recorded. Five-pillar POC weights are a review baseline, not implicit approval.

### LCTX-03 — `feat: attach versioned location context to audits and expose it to the report and agent`

**Problem:** the worker currently loads rental comparables and a risk-free rate only; an agent/report cannot inspect the wider locality fundamentals.

**Scope:** resolve property ancestry, load a bounded fact pack through an injectable repository, pin publication/evidence references, expose tenant-safe result/enrichment contract and “Kontekst lokalizacji” report section; make facts available to question rules and authorized agent consumers. **Depends on:** LCTX-01; LCTX-02 is optional until an accepted score exists. **Done when:** ambiguous/proxy/missing/boundary/stale cases, version replay, tenant isolation and unchanged finance are verified. Split repository/worker/API/frontend deliveries and update #274's successor report scope.

These are proposals only; no external issues were posted. The recommended first action is extending #48's contract and linking LCTX-01–03, not waiting for an unspecified generic “GUS decision” or treating the POC's existing ranking as production-ready.

## 11. Verification for this document

Read the live #48/#49 bodies and #48 comments; inspect current target context/sidecar code and GUS source/catalog/crosswalk/review files; count catalog and derived definitions by JSON/AST inspection without importing POC modules. Confirmed 24 requested/22 resolved raw metrics, ten derived definitions and snapshot counts of 2,479/380/16. Did not run the POC tests, regenerate its reports, audit all saved raw observations, verify external BDL metadata or exercise a product implementation. Documentation changes require no new behavior tests; paths, links and diff whitespace are checked before delivery.
