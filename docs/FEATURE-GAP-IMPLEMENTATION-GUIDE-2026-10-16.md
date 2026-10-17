# Missing product features: implementation audit and delivery guide

**Reviewed:** 2026-10-16 (Europe/Warsaw). **Status:** assessment and proposed implementation plan, not delivered functionality.

**Readiness cross-check, 2026-10-17:** [what this batch resolves and what still blocks launch](FEATURE-GAP-READINESS-COVERAGE-2026-10-17.md).
The six product/data deliverables remain required. Billing, settings/legal pages, sourced CAPEX/risk-free
inputs, accuracy, enforced CI, operational drills and provider/accountant acceptance are not completed
merely by delivering this batch. Do not use the pasted 45% readiness estimate or mark release gates passed
from feature completion alone.

The reported gaps are present in this checkout: Rynek and Architekt wnętrz are unavailable routes; manual analysis with uploads is absent; the analysis report has no photo gallery, equipment inventory or generated seller-question artifact. The URL analysis journey, deterministic financial engine, listing-photo extraction and vision integration do exist. These are different levels of completion and must not be described as a complete product.

## 0. Next implementation batch: Rynek data and location context

**Owner-confirmed scope, 2026-10-16:** implement **all six original deliverables in §4**, including gallery, equipment/OCR, seller questions, manual input, Rynek and interior tools. Complete Otodom apartment-rental collection and GUS BDL location context are **additions to that batch**, expanding Rynek and report/agent context. They do not replace, defer or remove G-01–G-05. The batch is incomplete until every required deliverable meets its own acceptance criteria; dependency order determines sequencing, not scope reduction.

| Workstream | Required result | Canonical implementation detail / ownership |
|---|---|---|
| Media and report gallery | Durable media identity/storage and private gallery for existing URL analyses, including photos/plans and partial failures. | G-01, §7/§11 |
| Equipment and OCR | Factual inventory, source/image evidence and retained floor-plan text; unknown/conflicting facts visible. | G-02, §8/§11 |
| Seller questions | Grounded report-specific questions and saved results; optional paid AI enhancement follows its cost decision. | G-03, §10/§11 |
| Manual source and uploads | Tenant-owned manual facts/photos enter the common audit pipeline and canonical report. | #283/G-04, §6/§11 |
| Interior tool | Persistent projects, owned media and concept/image operations with explicit progress, retry and settlement. | #284/G-05, §9/§11 |
| Otodom coverage and corpus | Cover **all locations in the owner-verified 727-location catalogue**, fetch all rental-result pages/partitions once, and persist offer-level analytical data in Postgres. An initial rollout subset does not satisfy full coverage. | [Otodom bootstrap/nightly guide](OTODOM-NIGHTLY-IMPORT.md), #209/#49; proposed OTO-01/02 below |
| Otodom daily collection | An application cron/Procrastinate periodic dispatcher queues last-24-hours new-rental searches for every bootstrapped location each night; durable windows, retries and catch-up prevent silent gaps. | Same guide §§6–7, #16/#209; proposed OTO-03 |
| Otodom trends and Rynek | Persist daily new-offer and rolling 90-day cohort summaries, counts and coverage/freshness. Expose history through #21 and replace the #282 placeholder with real data. | Same guide §8, #16/#21/#282; proposed OTO-04 |
| GUS BDL profiles and rankings | Gmina/powiat/województwo facts, trends, comparisons and peer rankings; separately versioned fundamentals index; audit/report/agent context. | [BDL context contract](BDL-LOCATION-CONTEXT-CONTRACT.md), #48/#21/#282; proposed LCTX-01–03 |

**Confirmed current gap:** `otodom_rental.py` limits each on-demand city/month import to five pages, rejects fewer than ten priced rows and replaces monthly comparables. `tasks/batch.py` has an on-demand task, with no rental periodic dispatcher. That is not the durable all-location corpus, nightly new-offer capture or daily trend history required here. Existing single-city live evidence does not establish nationwide coverage. See L-022.

**Batch acceptance:** every catalogue location has explicit bootstrap and refresh state; completion requires coverage evidence for every location, not just successful jobs for a subset. Zero-offer locations must have successful-empty evidence. Failed/capped/unsupported locations stay visible as incomplete; national completeness claims remain withheld. Offer IDs, run/checkpoint state and historical summaries survive worker restarts. A browser can read actual rental trends and separately sourced BDL context through typed APIs.

The user has authorized the full-catalogue target and nightly collection scope; do not ask again whether these features belong in the app. Still verify the actual catalogue artifact, live provider query/window semantics, source review and remaining BDL scoring/publication decisions. This documentation update does not install a cron, run scraping or claim implementation is complete.

## 1. Roadmap and issues checked first

Reviewed `ROADMAP.md`, `BACKLOG.md`, `STATUS.md`, `FRONTEND-PLAN.md`, `BLOCKERS.md`, the report and engine specifications, and the reference project's `docs/APP_AUDIT_AND_ROADMAP.md`, `apps/deal-analyzer/ROADMAP.md` and `ROADMAP_UPDATE.md` before tracing the implementations. GitHub returned **200 issues across all states** (`gh issue list --state all --limit 1000`); titles were searched across the complete snapshot and relevant bodies and comments inspected. Issue state below is the state observed on 16 October, not a permanent promise.

### Existing coverage and whether it is sufficient

| Issue | Observed state and scope | Assessment and required amendment |
|---|---|---|
| [#282 — Rynek market view](https://github.com/wedbew/rent-monitor/issues/282) | Open; depends on #21, #16, #48, #49 and #270 | Good UI acceptance: source/date, asking/deed separation, gaps, server-enforced top 20 and five cities. Not sufficient alone: add the exact dataset inventory, endpoint fields, filters, freshness states and ranking suppression contract from §5. Keep this issue; do not duplicate it. |
| [#21 — market/screener API](https://github.com/wedbew/rent-monitor/issues/21) | Open; route-map description | Too broad to implement in one slice. Split market read contracts, market routes and screener routes; name files, pagination/filter vocabulary, sample-count/coverage metadata, entitlements, error states and tests. Screener should not block a first approved market view. |
| [#16 — market batch tasks](https://github.com/wedbew/rent-monitor/issues/16) | Open; refresh, ranking and screener umbrella | Needs executable acceptance, separate importer/ranking/screener children, publication atomicity, deadline/retry/recovery policy and file ownership. Link the newer nightly-import guide rather than inventing a competing refresh policy. |
| [#48 — BDL contract](https://github.com/wedbew/rent-monitor/issues/48) | Open; approved metrics, provenance, completeness | Correct requirements, but not ready: approved metric list, units/grains, cohort and suppression thresholds are undecided. Comments on 16 October explicitly link **B-023**. Add typed-contract files and tests for each decision once recorded. |
| [#49 — coverage/partition/deduplication](https://github.com/wedbew/rent-monitor/issues/49) | Open; ceilings, deduplication, checkpoints | Correct themes; missing quantified acceptance and a files list. B-023 also applies. Specify complete pagination/partition termination, duplicate policy, coverage denominator and interrupted-run publication rules. |
| [#209 — rental-comparables importer](https://github.com/wedbew/rent-monitor/issues/209) | Open; offline implementation exists | Description is stale: it still says the comparable store is empty. RM-240/RM-242 and STATUS document an on-demand importer and one-city live evidence. Amend to separate delivered sampling from pending all-page bootstrap, nightly new offers, 90-day cohort and measured coverage. |
| [#283 — manual-input analysis](https://github.com/wedbew/rent-monitor/issues/283) | Open; explicitly requires backend specification first | Captures the intended feature and upload/UI failure cases. Insufficient implementation detail: no source identity, draft/media contract, required-field list, idempotency/credit rules, storage/retention or manual-to-engine mapping. Add the §6 contract and proposed child G-04. |
| [#284 — Architekt wnętrz](https://github.com/wedbew/rent-monitor/issues/284) | Open; product/cost/backend contract pending | Correctly requires persistence, media, progress/retry/cost and preserved originals. Missing operation types, room identity, task/artifact schemas, pricing/settlement, partial-success policy and provider isolation. Add §9 and proposed child G-05. |
| [#274 — canonical report](https://github.com/wedbew/rent-monitor/issues/274) | Closed; six report sections delivered | Closure comment lists summary, rent, costs, price, checks and sources, with historical test evidence. Legal text mentions photos, but acceptance does not define a gallery or equipment/questions. Do not treat closure as proof of those features. Add G-01/G-02/G-03, rather than reopen the entire report slice. |
| [#211 — audit vision/OCR](https://github.com/wedbew/rent-monitor/issues/211) | Open; integration description predates delivered work | Amend: integration shipped in [#244](https://github.com/wedbew/rent-monitor/issues/244), pricing hold in [#246](https://github.com/wedbew/rent-monitor/issues/246), and STATUS records one real OpenRouter call. Remaining work is quality/live coverage and richer durable evidence, not “pipeline never calls vision.” It does not currently specify equipment or a gallery. |
| [#23 — vision client/helpers](https://github.com/wedbew/rent-monitor/issues/23), [#91 — typed output/clamp](https://github.com/wedbew/rent-monitor/issues/91) | Closed | Useful foundations; neither promises persisted images, item detection or seller questions. Preserve their security and financial invariant tests. |
| [#285 — listing assistant](https://github.com/wedbew/rent-monitor/issues/285) | Open | Adjacent feature: creates listing drafts/tips. It does not cover buyer questions to the seller. Keep the scopes distinct. |
| [#43 — owner decisions](https://github.com/wedbew/rent-monitor/issues/43) | Open; several old decisions resolved | Roadmap D-07 still covers seller questions/analyst/redesign scope. Current user request authorizes this investigation and guide; it does not settle feature prices, processing consent/retention or automatic paid generation. Record those choices in the implementation issues. |

#282, #283 and #284 had no comments with additional decisions at review time. No dedicated issue title for gallery, equipment/fit-out inventory or seller questions was found in the full snapshot. This is a coverage finding based on issue titles and relevant bodies, not a claim that no unrelated discussion ever mentions them.

### Planning inconsistencies to correct alongside implementation

- `ROADMAP.md` revision 2 is the historical launch baseline. Its frontend restriction, sequential-gate wording and Stripe-first critical path have been superseded by Phase 2 authorization, ADR 0012 and the Paddle pilot. Use current rules, STATUS and FRONTEND-PLAN for readiness.
- `BACKLOG.md` says no interior/seller-question tickets until scheduled; #284 now exists. Update the mapping; seller questions still lack a dedicated ticket.
- `STATUS.md` lists #48/#49 as ready to specify, while B-023 and their latest comments identify owner decisions. Mark the affected scope blocked on those named decisions without blocking independent gallery work.
- L-024/L-025 describe design prototypes. They are not enough to explain production gaps; L-044 records the missing report evidence and links this guide.
- `OTODOM-NIGHTLY-IMPORT.md` has owner-selected collection policy but also historical “Phase 1 backend only” wording. That restriction is superseded for the authorized SPA; the data collection policy is still relevant.

## 2. Evidence boundary and implementation baseline

Target repository: `rent-monitor`, HEAD **51e45fa**, branch `rm-334-work`. The checkout already had unrelated modified/untracked CI, visual-test and development-stack files; they were left alone. This report concerns the inspected source, not an assumed deployed revision.

Reference repository: `/Users/marcin/Projects/otodom-rent-report`, HEAD **00ab3f9d89ea19b976ce0a4749449b7d1da655e5**. It was inspected read-only for requirements. Nothing was copied, imported, executed or installed from it. The reference HEAD is recorded here independently of CONTEXT's older source pin.

No UI session, live listing, database, deployment or paid provider was exercised for this audit. Existing STATUS records one live Toruń analysis; that is prior evidence, not a fresh accuracy or completeness measurement. Every interface and table proposed below is **new design**, not a callable existing endpoint.

### What is actually implemented

| Capability | Confirmed source evidence | Completion boundary |
|---|---|---|
| Rynek | `frontend/routes.tsx:116`; `frontend/shell/navigation.ts:49`; no market router in `services/rm_api/app.py` or `docs/openapi.json` | Unavailable placeholder; not an empty chart caused by a failed market request. |
| Architekt wnętrz | `frontend/routes.tsx:117`; navigation marks it unavailable | No production workflow, persistence contract or generation API. |
| Manual listing + photos | `frontend/features/analyses/new/NewAnalysisPage.tsx`; `packages/rm_contracts/audits.py:41` | Production submission accepts only `listing_ref`, `lang`, `analyst`; no manual body or upload field. V2 manual tab is a local prototype. |
| Listing photos | `apps/deal_analyzer/listing.py:38`; `extract.py:156`, `:273`; `services/rm_worker/vision_stage.py:118` | URLs are extracted, selected, safely downloaded and sent to vision. `DealAnalysis.listing` retains URL fields. `ReportView.tsx` never renders them. |
| Vision | `services/rm_worker/audit_wiring.py`; `audit_pipeline.py:174`; `apps/deal_analyzer/vision.py` | Injectable provider, budget/deadline, image guards, condition and clamped adjustments exist. Failure degrades the analysis. |
| Durable image evidence | `VisionOutput`, `VisionRecord`, `apply_vision` in `apps/deal_analyzer/vision.py` | Persisted record has counts/condition/adjustments/model/prompt. Individual classifications, OCR text and notes are not carried into `VisionRecord`; downloaded prepared bytes are not exposed through a media API. |
| Equipment | `Listing`, `VisionOutput`, `PhotoAssessment`, `VisionRecord` | No structured inventory. Photo assessments only classify image kind; equipment is neither extracted into typed facts nor returned for rendering. |
| Seller questions | `ReportView.tsx:546` (`CheckSection`); `services/rm_api/audits.py:142` | Existing checks map warnings and two unknown fields to fixed copy. No question-generation operation/result. `analyst=true` is refused with 403; enabling it will not create this feature. |
| Canonical report | `apps/deal_analyzer/analysis.py:59`; `frontend/api/report.ts`; `ReportView.tsx` | Versioned, runtime-validated financial report exists. New evidence must respect version compatibility and durable old audits. |

An additional delivery constraint: `deploy/Caddyfile:19` allows `img-src 'self' data:`. Adding `<img src={listing.photo_urls[0]}>` alone would still fail against the production CSP. Approved same-origin media delivery avoids both that problem and a browser request to an uncontrolled third-party URL.

## 3. Requirements learned from the reference project

| Reference files | Useful behavior to rebuild | Defect or constraint to avoid |
|---|---|---|
| `frontend/src/pages/report-page.tsx:155`, `components/listing-gallery.tsx`, `components/image-intel.tsx` | Gallery linked to image-specific observations, floor plan and redesign entry. | Do not assume array position identifies an image after filtering/deduplication. Persist stable media IDs and evidence links. |
| `apps/deal-analyzer/src/deal_analyzer/images/schema.py:69`; `fitout/models.py:363`, `:450`; `fitout/reconcile.py` | Furniture/appliances, item condition, evidence references, uncertainty, separate deterministic reconciliation. | Not visible is not absent; built-in appliances can be concealed. Repeated views must not double-count an appliance. Reference math uses floats: rebuild with Decimal and approved rules. |
| `seller_questions.py:32`, `:39`, `:99`, `:129`; `frontend/src/components/seller-questions-panel.tsx:29` | Four question groups; question/reason/priority; report + visual context; saved versions; explicit generate/regenerate. | Reference is a local file-backed operation, not tenant-safe SaaS. Do not transplant subprocess endpoints, filesystem history or float cost fields. Generation is an explicit operation there, not automatic on every report load. |
| `redesign.py:29`, `:43`, `:82`; `frontend/src/pages/redesign-page.tsx`; `frontend/server/redesign.ts` | Select a room image, style/constraints, before/after concept, history and partial image failure. | The local server waits for a child process and uses a process-local busy flag. Replace with persistent jobs and idempotent settlement. AI price bands are unverified, and must not become analytical CAPEX or verified shop prices. |
| `frontend/src/pages/rent-report-page.tsx`; `frontend/server/plugin.ts:105`, `:819` | City index/detail, filters, sorting, pagination, sample sizes and freshness. | Reference reads report files and derives summaries in its Node plugin. New server is Python, reads validated Postgres data and computes financial outputs only in `apps/deal_analyzer`. |

The reference audit is a source of requirements and failure modes, not an implementation specification. Its queue suggestions and historical roadmap completion claims do not override this repository's Postgres/Procrastinate architecture or approved ENGINE-SPEC.

## 4. Delivery order (updated for the owner's next batch)

**Parallel execution, 2026-10-17:** [lane/dependency plan and complete shared-file conflict inventory](PARALLEL-FEATURE-DELIVERY.md).
Use three isolated workers plus an integrator; media, Otodom and BDL start as independent ready slices,
then rotate to evidence/questions/manual/interior/market consumers. Canonical doc conflicts are handled
through issue-local handoffs and integration in the same feature PR before readiness. All deliverables
below remain required; no worker may remove one to simplify parallel scheduling.

All six original deliverables remain required, with the Rynek data lane expanded by the Otodom and BDL requirements. These are dependency slices, not calendar promises:

1. **G-01: durable media and report gallery.** Start with existing URL analyses; immediately restores visual context and creates the shared media seam.
2. **G-02: factual equipment evidence and OCR persistence.** Read-only inventory first; do not expand financial assumptions as part of evidence display.
3. **G-03: seller questions.** Deterministic questions can use known gaps; optional narrative generation follows an approved cost/entitlement decision.
4. **#283 / G-04: manual source and uploads.** Reuse the same media and analysis path, with durable identity and credit behavior.
5. **#48/#49 → #209/#16 → #21 → #282: Rynek.** Independent data lane, with remaining B-023 decisions applied to the affected scope. Includes all-location Otodom storage/bootstrap/nightly capture/trends (OTO-01–04) and GUS BDL location context/rankings (LCTX-01–03). Publish only datasets meeting their contracts; unrelated BDL work need not block a clearly labelled rental-only first slice, but that slice does not complete the full batch.
6. **#284 / G-05: interior tool.** Build on owned media, room/equipment evidence and persistent jobs; release one operation at a time.

### Expanded Rynek data-lane sequence (deliverable 5)

1. **Contracts and identities:** locate/validate the complete Otodom catalogue, approve #49 coverage/window rules and #48 BDL metric/territorial contracts. Scope is all catalogue locations; chunking controls workload, not final coverage.
2. **Otodom persistence and bootstrap (OTO-01/02):** immutable offer corpus, run/checkpoint staging, all-page/partition fetches, completion manifests and recovery. Keep interactive audits prioritized through the shared provider throttle.
3. **Nightly capture and trends (OTO-03/04):** application periodic jobs, source-window catch-up, age eligibility, append-only daily summaries and daily reader/cache semantics.
4. **BDL indicators and rankings (LCTX-01/02):** fresh approved observations, hierarchy, comparable periods and immutable publications; composite activation follows explicit methodology approval. Otodom collection does not wait for composite acceptance.
5. **Rynek and audit/agent consumers (#21/#282, LCTX-03):** API index/detail/history, complete coverage/freshness states, BDL locality profiles and bounded report context. Useful accepted datasets may ship independently while remaining gaps stay visible.

The gallery/evidence/manual/interior lane and the market-data lane may progress independently where their interfaces permit. Completion of one lane never closes or defers the other. Features with unresolved pricing/provider choices remain required scope with explicit blockers, rather than disappearing from the implementation list.

Every implementation PR starts from a real issue, follows repository branch/PR rules, and updates STATUS with evidence. G-01…G-05 are proposed issue labels in this document, **not GitHub ticket numbers**. No issues or comments were posted by this audit.

## 5. Rynek: from existing data to a usable market view

**16 October follow-up — broader location context is required.** The owner explicitly requested the datasets/ranking capabilities of `gus-stats-poc` as part of this app for gmina, powiat and województwo and for the analyzing agent. #48 references that project but does not yet explicitly cover these consumers. The [BDL location-context contract proposal](BDL-LOCATION-CONTEXT-CONTRACT.md) records the source audit, 22 resolved raw/ten derived metric candidates, administrative hierarchy, per-indicator ranks/trends/comparisons, separate REIS-style fundamentals index, bounded agent fact pack, report section and missing issue proposals LCTX-01–03. Read it alongside this section. The reference's location fundamentals index must remain separate from property grades and yield rankings; no financial assumptions change through informational enrichment.

### Contract and data work

1. Resolve the remaining B-023 decisions in #48/#49: selected BDL variables/units/grain, attribution review, per-metric publication thresholds and actual complete Otodom catalogue artifact (all 727 locations are now the owner-confirmed target). GUS-reference inspection and inclusion of hierarchical location context were authorized by the owner's 16 October follow-up; do not ask again for that scope. Exact scoring policy remains undecided. Do not invent a national coverage denominator.
2. Inventory each intended dataset separately: rental asking, sale asking, deed transactions, demographics/supply and risk-free rate. For each record source, period, territorial ID/grain, size/room bucket, unit, sample count, expected cohort, coverage fraction, freshness, input digest and methodology version. A database table existing is not evidence of populated complete coverage.
3. Implement the owner-selected rental policy in `OTODOM-NIGHTLY-IMPORT.md`: all-page bootstrap, nightly newly-created offers, insert once, no individual-listing refresh, 90 elapsed-day eligibility and resumable checkpoints. Label the rolling cohort as collected original asking rents, not verified live inventory. Missing runs and page ceilings must be visible. This is a change from the present first-five-pages/monthly sample.
4. Add sale asking/deed data only through separate approved importers. Distinguish legitimate zero, absent observation, withheld aggregate and failed import. Coverage failures must not overwrite the last valid publication with an apparently complete result.
5. Build versioned read models/publications. An incomplete city must not silently alter a national ranking. If a yield/ranking uses financial calculations, expose a deterministic engine function in `apps/deal_analyzer`; importers/API serialize the output. Never calculate it in React or route handlers.

### API and frontend work

Under #21, specify market index and city-detail operations (candidate shapes: `GET /api/market/cities`, `GET /api/market/cities/{location_id}`) before implementing. Define supported filters, page/cursor ordering, source/basis discriminators, historical series availability, units and suppression reasons. Enforce plan limits in the server, including detail access policy; do not implement a client-only “top 20.” Return only typed, bounded public aggregates.

Under #282, replace PendingPage after captured contract fixtures exist. First view: searchable city list, rental/asking/deed basis selector where supported, source/date/sample count/coverage, city details and comparable historical periods. Include loading, no dataset, stale last valid data, incomplete/withheld cohort, 403/429 and provider failure. Maps and additional charts can follow; they should not delay useful validated tables. Do not plot different grains as a single comparable series.

**Acceptance:** five genuinely distinct synthetic/captured-shape cities; missing/stale/partial cases; deterministic paging and filtering; asking/deed invariant; entitlement tests on index and detail; interrupted bootstrap and duplicate-job tests; no suppressed national ranking leaks through a detail route. Add sample scenarios, accessibility, light/dark and mobile/desktop browser checks.

**Likely files:** new contract modules under `packages/rm_contracts/`; market repository/contracts under `packages/rm_core/`; importer and `tasks/batch.py` slices; `services/rm_api/market.py` plus registration; `frontend/features/market/`; generated OpenAPI/types. These are proposed ownership areas, not existing modules.

### Otodom completion details for the next batch

Use the existing [nightly-import guide](OTODOM-NIGHTLY-IMPORT.md) as the detailed design, including its database schema, page/window verification, scheduler, recovery and tests. Amend #209's stale empty-store description, #49's coverage acceptance, #16's periodic-job/history deliverables and #21/#282's history/coverage contracts. Do not create a competing fetch specification.

- **Full catalogue:** seed verified source IDs/paths, retain catalogue version and explicit expected/covered/failed counts. Do not invent the 727 paths from names or treat them as all Polish gminas. Account for overlapping search locations and deduplicate source offer IDs with a reviewed location-assignment rule. A location with no priced offers can still have complete ingestion.
- **Offer-level Postgres storage:** retain source ID, location/reference, original asking rent, area/rooms when valid, original publication/first-seen timestamps, age basis and provenance. Use minimal whitelisted fields; no seller names, phones, photos or descriptions in this corpus. Persist staging/runs/checkpoints before publication; source IDs must survive retries and process restarts.
- **Every-page collection:** remove five-page sampling from the new full-corpus path and prove a strategy for portal result ceilings. Fixed bounded chunks must resume until all partitions complete. Keep incomplete counts honest; never declare a capped city complete.
- **Nightly application schedule:** adopt the existing proposed fixed UTC cron after scheduler verification; dispatcher on `ops`, bounded fetch work on dedicated `batch`, one shared host throttle with interactive priority. Last-24-hours means newly created rental offers, not fetching every existing listing nightly. Durable due-work reconciliation and verified wider/bounded queries handle late starts/missed nights; unsupported catch-up leaves a visible coverage gap.
- **History and trends:** persist daily new-offer summaries and separate rolling 90-day eligible cohorts, including zero-new-offer days. Recovery counts use source publication dates rather than inflating today's supply. Preserve daily snapshots/input digests/methodology versions, actual source coverage, observed/priced counts and bucket definitions so comparable historical trends can be reproduced.
- **Reader migration:** current month-based freshness, queue locks and monthly replacement are incompatible with daily coverage. Migrate comparable loading/cache invalidation and API data-status fields together; expiry without new inserts must invalidate the cohort digest. Failed runs retain the last valid publication.

“Up to date” here means recent new-offer capture and correctly aged stored observations. Under the existing insert-once policy, older offers are not checked for withdrawal, new asking prices or successful rental. Trend charts must say **original asking rents**; they cannot claim price-change history for one advert, achieved rents or verified active inventory. Changing that policy would need a separately specified feature.

### Proposed Otodom issue children (not filed)

| Proposed title | Description / done criteria | Existing parent |
|---|---|---|
| **OTO-01 — `feat: persist the complete Otodom location catalogue and immutable rental corpus`** | Versioned verified catalogue, offer/run/staging/checkpoint repositories and expand migration; durable source-ID uniqueness, explicit location assignment for overlapping searches, retention and coverage records. Test retries, conflicting sightings, concurrency, empty results and no seller data. Exact files: core market models/repositories, migration, integration fixtures/tests; split migration and repository work as needed. | #209/#49 |
| **OTO-02 — `feat: bootstrap all Otodom rental locations with resumable complete pagination`** | Full flat-rental bootstrap for every catalogue location using verified search/partition semantics; bounded checkpointed chunks, no individual advert fetches, complete/partial/empty manifests and safe bootstrap-to-incremental handoff. Test more than five pages, portal ceilings, overlap, schema drift, interruption and restart. Depends on OTO-01 and validated provider contract. Files: worker search client/source, importer, batch tasks and integration tests. | #209/#49 |
| **OTO-03 — `feat: schedule nightly last-24-hour rental imports with gap recovery`** | Persistent application periodic dispatcher, per-location jobs/locks, due-work reconciler, verified wider-window catch-up, dedicated batch capacity and atomic window publication. Test duplicate dispatch, zero offers, delayed/missed nights, DST, provider errors and crash recovery. Depends on OTO-02 handoff; do not install a separate host cron that bypasses the worker state. Files: worker tasks/job contracts, queue/deploy config and scheduling tests. | #16/#209 |
| **OTO-04 — `feat: publish daily rental trends and coverage for Rynek and audit context`** | Daily new-offer and 90-day cohort summaries/history, age expiry, daily comparable/cache migration, typed API history and freshness/coverage consumed by Rynek. Test immutable history, late recovery dates, expiry without inserts, thin samples, stale/partial data and ask/admin-fee invariants. Depends on OTO-01/03 publication contracts; expose test fixtures before live evidence. Files: pure engine statistics, core publication/read repositories, API contracts/routes and #282 UI slices. | #16/#21/#282 |

These are deliverable proposals, not four oversized agent-ready changes: split by module/route group and migration before labelling implementation children. The matching BDL proposals are LCTX-01–03 in the linked contract. No external issues were posted by this update.

## 6. Manual analysis with photographs

### Source identity must come before the form

Today `Audit.otodom_id` is a non-null listing foreign key (`packages/rm_core/db/models.py:609`), `AuditOut` returns that ID, and active-audit deduplication uses it. The engine `Listing` also requires `otodom_id`. A form alone cannot create a valid manual journey. Do not fabricate an Otodom ID or put private manual payloads into the shared listing snapshot cache.

Design a typed source discriminator (`otodom` / `manual`) with a durable internal property/draft UUID, optional external reference, immutable submitted-input revision and tenant ownership. Plan an expand migration, old-reader compatibility and a later contract cleanup. Audit summaries, list filters, report headings, saved-item behavior and links must handle manual identity. Existing Otodom saved-listing endpoints cannot be reused unchanged: initially hide saving for manual reports or add a separately specified property-saving contract.

### Input and operation contract

Agree mandatory facts and billing in #283. Suggested minimum for review: sale intent, whole/share/unknown ownership declaration, asking price, area, rooms and resolvable city/location; optional administrative fee, floor/year/building attributes, description, declared equipment and media. Unknown fee is null, not zero; unknown ownership follows an explicitly approved conservative policy. Manual input cannot bypass RENT/fractional guards or claim coordinates more precise than supplied evidence.

Candidate workflow: create/edit tenant draft → upload media → validate/preview → submit immutable draft revision with idempotency key → reserve the agreed report credit and enqueue once → existing context/vision/engine/result/progress journey. Exact endpoint names belong in the backend spec; the SPA must consume generated types, not invent requests.

Specify credit outcomes for validation failure, incomplete upload, missing context, duplicate submission, crash, cancellation and degraded vision before implementation. Uploading a draft should not silently spend a report. The lost-response/reload path must reconcile the same request key; repeated delivery cannot create another charge. Cleanup a draft without deleting media referenced by a submitted audit.

### Upload handling

Reuse §7 media preparation after implementing a separate bounded upload boundary. Initial proposal for owner review: JPEG/PNG/WebP, existing 10 MiB per-file/40 MP decode safeguards, bounded file count and total per-draft/user quota. Current worker selection uses up to 25 photos and two plans; a draft may have a different storage cap only if explicit. Match declared MIME to decoded content, reject SVG/HTML and corrupt/bomb inputs, orient/re-encode and strip metadata. Treat floor plans as a declared type subject to validation, not proof of dimensions.

The UI needs drag/drop plus file picker, upload progress, reorder/remove, thumbnails, role marking, per-file decode failure, resumable draft and server field errors. Retry must retain facts and successful files. Display missing city/context separately from invalid input. On success navigate to the same report renderer.

**Acceptance:** manual and URL sources produce the same canonical analytical schema; persisted/manual identity survives reload; tenant A cannot reference B's media/draft; exactly one credit/job under parallel submit/retry; RENT/share rejection; no photos/failed vision; unknown vs zero; rejected/oversized/forged uploads; draft expiry, export and erasure; five distinct UI scenarios plus a real-Postgres worker journey with fakes.

## 7. Photos in analysis reports and shared media foundation

### Stage A: stable evidence identity

Create a bounded manifest identifying every source image/plan and its ordinal, source type, stable media ID and content digest. Record prepared dimensions/MIME, download/rejection state, classification and analysis state separately. Keep original-to-selected-to-deduplicated-to-model-input mapping: the current selector and downloader change array membership. Model output must cite media IDs; validate missing, duplicate and foreign evidence IDs. Test the request/output cardinality contract, including 25 photographs plus two plans, because current `VisionOutput.photos` is capped at 25 while requests can contain 27 images.

Do not let a model classify an image that was never submitted, and do not infer room identity from “bedroom” alone. A floor-plan image and its OCR observations need a shared reference. Show renders/staging explicitly and exclude them from factual equipment/condition evidence.

### Stage B: storage and retrieval

Persist approved media metadata and operation state in Postgres. Current rules say all state lives in Postgres; `R2-SPEC.md` covers **backups**, not an approved public media store. Specify a bounded Postgres binary-storage beta option with storage/backup limits, or obtain an explicit architecture decision for private object storage before adding it. Do not silently reuse the backup bucket for product media.

Provide an authenticated same-origin media route that resolves an opaque ID through the caller's audit/draft/project ownership. Foreign IDs return 404; never proxy a caller-supplied arbitrary URL. URL imports reuse allow-list, redirect, deadline, byte/pixel and content safeguards. Uploads use decoded content validation instead of URL allow-list checks. Media access must not trigger paid vision or an unbounded fetch on every page view.

Set private/no-store behavior as required by the privacy design, correct Content-Type and nosniff. Do not use publicly enumerable blob paths or cache tenant media in a service worker. Decide source-original preservation versus normalized derivative retention: original bytes may contain EXIF/PII and need restricted access, while normal viewing and processors receive stripped derivatives. If originals are not retained, promise preserved source/normalized input, not byte-for-byte originals.

Define actual retention values, references and deletion semantics with the owner. Shared Otodom snapshot reuse is not authorization to share private uploads. Audit deletion/account erasure and the retention sweep must remove/revoke media, question and redesign derivatives as specified; prevent a late worker completion from recreating erased artifacts. Backups follow their documented expiry policy. Retention is not equivalent to the market's 90-day analytical cohort.

### Stage C: gallery

Add `frontend/features/analyses/report/` gallery components and media query contracts. Render thumbnails and full-size dialog, keyboard navigation/focus return, captions, image type and per-image failure/retry. Separate photos from plans; a vision failure must still allow successfully stored photos to be viewed. Preserve the financial report when an image fails or has expired. Keep existing old reports readable with “media unavailable”; never manufacture missing evidence or silently recompute an old report.

**Acceptance:** seeded report displays photos and plans under the actual Caddy CSP; foreign media ID is 404; no arbitrary fetch/redirect; no EXIF leak; partial image failures and unavailable media have explicit states; renders are labelled; lazy loading works; dialog works with keyboard/zoom/mobile; session end clears sensitive UI; account erasure and worker races are exercised.

## 8. Equipment, furniture and floor-plan evidence

### Ship facts before extending valuation

Extend extraction for an approved equipment vocabulary and listing claims. Add bounded observations for fridge, hob/oven, washing machine, dishwasher, kitchen units, bed, sofa, wardrobe and heating/cooling equipment only where evidence supports them. Each observation should carry item ID, room ID if known, evidence source (structured listing, text claim, photo, manual declaration), status (`observed`, `claimed`, `explicitly_excluded`, `unknown`), condition if supportable, evidence reference and confidence. Contradictions stay visible.

Presence in a photo does not establish that the item is included in the sale. Track inclusion separately as confirmed-by-user/seller claim/unknown. An invisible dishwasher behind cabinetry stays unknown; a cropped room does not prove missing equipment. Ignore renders and virtual staging as factual evidence. Multiple photos of one room should not count as multiple fridges; uncertain room matches remain unresolved.

Add item observations and stable media IDs to a versioned vision prompt and typed result. Persist observations through the worker into canonical evidence, not just model response logs. Also retain bounded floor-plan transcription with media reference/confidence; do not turn uncertain OCR into measured dimensions. The current path parses `floor_plan_text` and `notes` but drops them in `apply_vision`; correct that durability gap deliberately. Check PII redaction for both image text and model notes.

Render “Wyposażenie” with item, claim/observation, included-in-price status, condition and a link to the evidence image. Use explicit “brak informacji” for unknown; reserve “brak” for supported exclusion. Contrast listing claims and photo evidence only when they conflict. Missing or contradictory facts become seller-question inputs.

**Financial boundary:** initial inventory is informational. Existing approved CAPEX uses area/condition and a ±15% vision clamp. Item-priced fit-out, catalog prices, replacement actions, quantity rules, contingency and readiness/void changes require a separately approved engine-spec extension, sourced/versioned assumptions and money/property tests. Never add item totals on top of the current area allowance without a double-counting policy. Interior-design shopping estimates must not change this report.

**Acceptance:** concealed appliance, cropped photo, render, repeated room, claim-vs-photo contradiction, sale inclusion unknown, explicit exclusion, no vision and no equipment fields. Round-trip evidence/OCR through stored `AuditOut.result`; reject invalid references. Same financial inputs yield byte-equivalent financial sections before/after informational enrichment. If later costing is approved, test monotonicity, Decimal serialization and no double counting.

**Likely files:** `apps/deal_analyzer/listing.py`, `extract.py`, `vision.py`, `analysis.py`, new pure evidence/reconciliation module; worker prompt/media mapping; schema/goldens; report section, catalog copy and tests.

## 9. Architekt wnętrz as a persistent operation

First release recommendation for #284: one selected real room photo, style, functional constraints and optional known dimensions → saved concept → optional generated concept image. Keep the choice of this scope, provider/model and price explicit. A whole-apartment planner and verified marketplace shopping are further slices.

1. Persist tenant project, source audit/media references, immutable input revision and operation. Link room observations and floor plan only through verified room identity. Estimated dimensions remain labelled and cannot become purchase-fit guarantees.
2. Candidate operation contract: create project; submit concept/generation job with request key; read job/progress; list versioned artifacts; retrieve private before/after media. Reuse API/Procrastinate/progress patterns, with reviewed resource limits and queue capacity, rather than creating a Node service or process-local lock.
3. Separate concept generation and image generation into durable steps. If the concept succeeds and the image fails, retain the concept and allow an image-only retry. Do not charge successful text twice or overwrite prior concepts on failure. Define timeout, retry, cancellation, restart, provider-cost and user-credit outcomes per step.
4. Reserve AI budget atomically before calls; record provider request/result IDs when supported, model, prompt/input versions, usage and Decimal cost. A provider may charge before a lost response: avoid blind retries and document ambiguous settlement policy. No unbounded per-project history or user-selected arbitrary model/URL.
5. Preserve source images under the agreed media policy. Label generated images “koncepcja AI,” never actual condition. No generated image flows back into condition scoring/equipment evidence. Keep generated output private and within export/erasure rules.
6. Show input selection, preferences, declared cost, task progress, explicit retry and history. Before/after needs keyboard-accessible controls; no compulsory drag interaction. Unknown layouts and failed operations must have useful visible states.
7. If a shopping list ships, label availability, dimensions and price provenance honestly. Unverified model prices are suggestions, not offers. Keep deterministic monetary aggregation in `apps/deal_analyzer` with Decimal and a versioned policy; never copy the POC's float `PriceBand` into the new engine.

**Acceptance:** foreign report/media/project 404; duplicate request one operation/charge; two workers cannot overspend; text-success/image-failure persists; retry targets only failed step; restart and erasure races; no overwrite of originals; generated image cannot be used as factual evidence; unsupported model and provider timeout; source report's financial JSON unchanged. Provider calls stay behind injectable clients and the appropriate default-on legal/privacy switches.

## 10. Seller questions: structured, grounded and durable

The existing “Co sprawdzić” checklist is useful input, but it is not a generated question set. Do not gate basic questions on the unavailable `analyst` mode.

Recommended first slice: deterministic, report-specific questions from missing/contradictory facts, followed by an optional separately priced narrative enhancement if approved. Example: an unknown fee yields “Jaki jest aktualny czynsz administracyjny i co obejmuje?” with reason “Brak tej kwoty w analizie”; a visible appliance with unknown sale inclusion yields a question about inclusion, not a claim that it is missing. Always keep admin fee and rental income distinct.

Use four groups learned from the reference: legal/financial, property condition/equipment, location/context, negotiation/handover. Every item needs stable ID, question, reason, priority and supporting report/media field references. Bound question count/text; deduplicate; validate references; omit empty groups rather than fabricate a local development or defect. No claim of verified land-register status without evidence, and no legal advice generated as a factual conclusion.

For optional AI, pass a minimized fact/evidence projection with instructions to treat listing/image text as untrusted data. Do not send the full raw seller payload. A typed, bounded result must be validated before saving. Store audit/input digest, language, rules/prompt/model versions, timestamp, provenance and cost. Define unsupported/stale report behavior and question validity after input changes.

Candidate API: an authenticated create/read operation under an audit (for example `POST /api/audits/{id}/seller-questions` plus versioned reads). Use persistent task state, a unique input/language/version/request key, deadline and budget. Reads and page reloads never trigger paid calls. Regeneration is explicit and must preserve the previous successful version if the provider fails. Define entitlement and reserve/capture/release behavior before enabling paid generation.

Render questions/reasons grouped by priority, with links back to evidence and copy/export controls if approved. Keep the current financial report available when questions fail. Questions are prepared for the user: **do not send them to a seller** or expose seller contact information.

**Acceptance:** missing admin fee, unknown ownership/title details, thin rent sample, equipment inclusion unknown and contradictory evidence produce grounded questions; a complete input does not produce invented gaps; bad AI output/budget exhaustion/timeout preserves prior results; repeated click/reload creates one operation and charge; foreign audit 404; question generation leaves every financial field unchanged; pl/en and export/erasure supported as contracted.

## 11. Proposed issue titles and descriptions

These are copy-ready proposals. Amend existing owners in §1; create only the missing deliverable or an explicitly linked child. Each new issue should also include the repository's normal DoD, Legal/GDPR and Context lines.

G-01…G-05 describe deliverables, not single agent-ready PRs. Before applying an `agent` label, split each into contract/model, persistence/migration, worker/API and frontend slices as needed: one module or route group, at most one migration and approximately 400 changed lines per slice (`ROADMAP.md` §5). Give every child an exact files list and dependencies; serialize migration/schema edits. G-01's stages A/B/C are its first split, and G-04/G-05 backend children must be split again rather than combining a source migration, provider operation and UI in one run.

### G-01 — `feat: persist audit media evidence and render a private report gallery`

**Problem:** URL analyses extract photo/plan URLs and run vision, but the report has no gallery, no authenticated media route and no durable mapping from displayed images to analyzed evidence. Direct CDN images conflict with the deployed CSP.

**Scope:** §7; design media storage within the current architecture; stable media manifest; tenant-authorized same-origin retrieval; durable normalized derivatives; private retention/export/erasure; gallery/photos/plans with partial failure. Preserve financial results and readable old audits.

**Depends on:** existing #23/#244/#274; storage/retention decision for the new media lifecycle. No dependency on #21 or interior generation.

**Files:** new `rm_core` media repository/contracts/migration, API media route, worker media persistence/mapping, report gallery, privacy sweep/export and synthetic fixtures.

**Done when:** §7 acceptance passes through a real-Postgres API/worker journey and a browser under Caddy CSP; cross-tenant 404, image guards, erasure race, keyboard and missing-media states tested. Tags: `LEGAL[images|republication]`, `GDPR[personal-data|retention|erasure]` (use individual repository tag syntax in code).

### G-02 — `feat: retain equipment and floor-plan evidence in canonical analysis reports`

**Problem:** current Listing/VisionRecord have no equipment inventory; per-image kinds/OCR are not retained as report evidence, so neither the equipment section nor grounded equipment questions can be built.

**Scope:** §8; approved vocabulary, listing/manual claims, per-media observations, separate inclusion status, unknown/occluded/conflict handling, OCR persistence and report display. Initial change must leave finance unchanged; item-cost modeling is a later approved engine slice.

**Depends on:** G-01 stable IDs; evidence schema and prompt approval. **Files:** engine listing/extract/vision/analysis/evidence models, worker prompt/mapping, report schema/adapters/goldens, equipment section and tests.

**Done when:** all §8 evidence cases round-trip through saved JSON with valid image references, non-photographic evidence excluded, and old version handling tested. Tags: `LEGAL[images]`, `GDPR[processor|personal-data]`.

### G-03 — `feat: generate and save evidence-backed questions for the seller`

**Problem:** report checks are fixed warning copy; no seller-question contract, stored result, operation or UI exists. #285 is a listing-writing assistant and does not own this behavior.

**Scope:** §10; deterministic gap questions first; optional AI only with approved pricing/entitlement; bounded question/reason/priority/evidence model, versioned storage, idempotent jobs if applicable, regeneration failure handling and report section. No seller messaging and no financial recalculation.

**Depends on:** approved scope/cost decision; canonical result already exists. Equipment-specific and image-linked questions depend on G-02; basic gap questions can land earlier.

**Files:** new pure engine question rules/models, `rm_contracts` operation schemas, `rm_core` repository/migration, API/worker task and report question section. **Done when:** §10 tests, schema/sample capture, tenant isolation, finance unchanged, lifecycle cleanup and UI states pass. Tags: `GDPR[processor|retention|erasure]` when applicable; preserve related image tags.

### G-04 — `feat: add tenant-owned manual drafts and submit them through the audit pipeline` (child of #283)

**Problem:** Audit and Listing require an Otodom identity; adding fields to the existing form cannot support a private manually entered property with uploads.

**Scope:** §6; approved mandatory fields/cost; source identity and migration; draft CRUD/media revision; idempotent submission and credit settlement; source adapter into common engine/progress/report; list/save/link compatibility. #283 retains UI ownership and adds the form after the contract.

**Depends on:** G-01 media and recorded source/cost/retention choices. **Files:** contracts, `rm_core` models/repositories/ledger seams, migration, manual source adapter, API submission, worker, list/report adapters; frontend form under #283.

**Done when:** §6 real-Postgres journey, parallel submission/credit tests, URL regression, rejection cases, privacy cleanup, OpenAPI/samples and five frontend scenarios pass. Tags: `LEGAL[images]`, `GDPR[personal-data|retention|erasure]`.

### G-05 — `feat: persist interior projects and run concept/image jobs with per-step settlement` (child of #284)

**Problem:** interior route is unavailable and the reference implementation is a synchronous local workflow. No tenant-safe persistent operation, pricing or partial-failure model exists here.

**Scope:** §9; one-room first operation; project/source/media revisions; persistent concept and image steps; approved model/cost/entitlement; budget/credit idempotency, private output/history, partial success and erasure. #284 owns the consuming UI and browser acceptance.

**Depends on:** G-01, approved scope/provider/cost/storage, G-02 for evidence-based room context when used. **Files:** new contracts/repository/migration, worker task/provider client, API/project/progress/media routes, engine monetary aggregation only if approved; frontend under #284.

**Done when:** §9 failure/concurrency/tenant/erasure acceptance and UI scenarios pass; original evidence/report finances are unchanged and generated output is clearly labelled. Tags: `LEGAL[images]`, `GDPR[processor|retention|erasure]`.

## 12. Schema, validation and delivery checklist

All new inbound models must be bounded and forbid extra fields; public errors use registered RFC 9457 problem codes. Keep API stateless, persistence in Postgres, external work in injectable worker clients, financial calculations in Python engine modules and money as Decimal/string/NUMERIC. Do not introduce a Node server, Redis or POC dependency.

`docs/REPORT-SCHEMA.md` has an important compatibility consequence: the generated serialized schema currently marks **all** fields required, including nullable/defaulted fields. Adding `equipment=None` or `evidence=()` to a model can therefore introduce a new required serialized field. Run the compatibility check and bump the version when required; do not call it compatible merely because Python has a default. New-version readers need an explicit old-version adapter, retained versioned schemas or a separately versioned enrichment contract. Keep stored old reports immutable; absence of historical evidence stays explicit.

For each changed contract: regenerate report schema/OpenAPI and generated frontend types, refresh synthetic fixtures/sample capture, update smoke scenarios, test unsupported versions and malformed success responses. Never bypass `parseReport` or the runtime response validator with casts. Update engine Markdown/export views where the contract promises parity; do not leave new JSON evidence invisible in exports without an explicit scope decision.

Useful existing commands (run the subset relevant to each implementation, then required repository gates):

```sh
uv run python scripts/gen_report_schema.py
uv run pytest tests/unit/test_report_schema.py
uv run pytest -m invariant
uv run pytest -m 'not e2e'
make api-samples
cd frontend
pnpm generate:api
pnpm check
pnpm test:e2e
pnpm test:e2e:journey
pnpm visual
```

Migrations additionally need migration tests and squawk; money/concurrency work needs property or parallel-request tests. Browser coverage must register every new control, include axe and five distinct data scenarios, and review light/dark at mobile/desktop sizes. Do not mark “delivered” from fixture-only visuals; distinguish offline contract/journey, real-provider verification and deployed browser evidence in STATUS.

### Verification performed for this audit

- `.venv/bin/python -m pytest tests/engine/test_extract.py tests/engine/test_vision.py tests/unit/test_vision_stage.py tests/unit/test_images.py tests/unit/test_audit_contracts.py tests/unit/test_report_schema.py -q` — **219 passed**. `uv run` initially hit a sandbox cache permission error; the existing virtualenv ran the same selected suite successfully without changing dependencies.
- `pnpm exec vitest run features/analyses/report/ReportView.test.tsx features/analyses/AnalysisPage.test.tsx api/report.test.ts` — **35 passed**, three files.
- These checks confirm existing extraction, vision, schema and report behavior remains supported. They do **not** prove the missing features work. No new application behavior, full suite, browser run, deployment or paid call is claimed.

### Decisions that remain genuinely open

Record B-023 data policy in #48/#49; manual required fields/source identity and cost in #283; media retention/storage and privacy handling in G-01; informational equipment versus separately approved fit-out costing in G-02; deterministic/AI question scope and generation cost in G-03; first interior operation, provider/cost and partial-success settlement in #284/G-05. Counsel/processor review follows existing B-012 and feature tags; it is not a reason to erase the feature from planning.

The owner's next batch includes **all six deliverables in §4**: gallery, equipment/OCR, seller questions, manual analysis, expanded Rynek and the interior tool. Otodom all-location collection/nightly trends and GUS BDL locality context/rankings extend the same batch. Follow dependencies within each lane; neither dataset delivery nor a rental-only Rynek slice completes the report/manual/interior requirements.
