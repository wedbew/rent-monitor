# Feature-gap re-verification — 2026-10-18

This is a dated source/GitHub audit, not a replacement for `STATUS.md`. Execution instructions:
[Claude completion prompt](CLAUDE-FEATURE-GAP-FINISH-PROMPT.md). The complete requirements remain in
[the implementation guide](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md), including G-01–G-05,
OTO-01–04 and LCTX-01–03. None is removed from the batch.

## Verified baseline and conclusion

Checked clean `staging` at `a123aeb02988393b241f5a475f460bf70a3c0098`, equal to fetched
`origin/staging`. GitHub returned no open PRs at inspection. Existing worker worktrees still exist;
their existence does not prove that a session is active or that they can be safely reset.

The three workers delivered useful **first slices**, not complete features. PRs
[#381](https://github.com/wedbew/rent-monitor/pull/381),
[#379](https://github.com/wedbew/rent-monitor/pull/379) and
[#380](https://github.com/wedbew/rent-monitor/pull/380) merged media metadata, Otodom contracts/test
semantics and BDL contracts/pure logic respectively. No complete G-01–G-05 user workflow was delivered
by these three PRs. Counting three merged PRs as three completed product lanes is incorrect.

Latest inspected staging workflows were successful, including
[CI for this SHA](https://github.com/wedbew/rent-monitor/actions/runs/39159629122).
Fresh local verification:

```sh
.venv/bin/python -m pytest tests/unit/test_media_contracts.py tests/unit/test_otodom_corpus.py tests/unit/test_bdl_metrics.py tests/integration/test_media_manifest.py -q --tb=short
# 72 passed in 4.92s
```

The first restricted run passed 64 unit tests and could not access Docker for eight integration tests.
The rerun with local Docker access passed all 72 using disposable Postgres. These tests certify the
foundation slices, not rental ingestion, a BDL dataset, image serving or frontend feature journeys.
This audit did not rerun the entire CI suite, exercise a browser, contact data providers or deploy.

## Implementation against the complete batch

| Deliverable | Confirmed in merged source | Still required before feature completion |
|---|---|---|
| **G-01 private media + gallery** | `rm_contracts/media.py`, `rm_core/media.py`, `MediaEvidence` and migration `0014`; authenticated `GET /api/audits/{audit_id}/media`, tenant 404, explicit failed/expired states. | Actual private image bytes and serving/access control, worker population, retention cleanup, gallery/plan viewer, reload and erasure journeys. Metadata is not a stored photograph. L-051 remains active. |
| **G-02 equipment + OCR evidence** | Existing `vision_stage.py` already downloads bounded images and calls the injectable vision client; `VisionOutput` accepts `floor_plan_text`. Existing report exposes condition/counts/clamped adjustments. | Preserve OCR as durable report evidence, media-linked item observations, confidence/provenance and included-in-sale vs merely-visible/unknown distinctions; equipment and OCR report UI. `apply_vision()` drops `floor_plan_text` when creating `VisionRecord`; no equipment inventory is defined there. Do not rebuild the already wired vision stage or introduce new CAPEX assumptions. |
| **G-03 seller questions** | `ReportView.tsx` contains a warning-driven verification checklist, including some seller-directed copy. | A dedicated grounded question generator, stable reasons/evidence references, deterministic ordering/deduplication, durable question versions and report presentation. Existing checklist copy is not that feature. Optional paid narrative must not block deterministic questions. |
| **G-04 manual source/uploads, #283** | URL audit path exists. `NewAnalysisPage.tsx` still renders `modeManualSoon`. | Validated manual facts/draft identity, secure uploads and lifecycle, canonical source identity without a fabricated Otodom ID, common audit pipeline, idempotent credit reservation/settlement, usable form and reload/retry journeys. Scope was approved; precise mandatory-field/storage/charge policies still need reconciliation. |
| **OTO-01–04 rental corpus/nightly/trends** | `rm_contracts/market.py` defines catalogue, immutable offer, run/checkpoint/coverage types and `CorpusRepository` protocol. `tests/market_corpus_fake.py` implements test semantics; 29 unit tests. Existing on-demand monthly comparable importer also exists. | A production Postgres corpus/repository and migrations; actual verified 727-location catalogue; provider filter/date/page/partition proof; full bootstrap; durable nightly last-24h windows, catch-up/recovery, overlapping-run safety; published histories/trends/freshness and API/UI consumers. The current importer has `MAX_PAGES = 5` and is queued on demand per city/month, not a complete national nightly corpus. No new Otodom nightly task was introduced. |
| **LCTX-01–03 BDL context/index** | `rm_contracts/location_context.py`, `rm_core/location_contracts.py`: typed hierarchy, observations, comparison/ranking rules, proxy labels and fail-closed publication gates; 27 unit tests. | Production hierarchy/crosswalk/observation tables and repositories, injectable source ingestion/quota/checkpoints, reviewed variable catalogue and per-metric freshness/coverage, atomic publication, approved versioned composite, market/report API/UI and bounded agent fact pack. No actual BDL observations, DB importer or public location metric shipped. L-042/L-045–047 remain relevant. |
| **Rynek market view, #282** | `/app/market` remains `PendingPage`; no `services/rm_api` market router. | Real dataset inventory and `/api/market/*`, source/grain/date/coverage labels, entitlement limits, rental trends and BDL context/ranks with independent publication gates, user-visible loading/empty/stale/failure states and browser acceptance. BDL composite approval need not block an honestly labelled approved rental-only slice. |
| **G-05 interior, #284** | `/app/interior` remains `PendingPage`. | Persistent owned projects, input media references, one approved operation at a time, progress/errors/retry/history, budget/entitlement/idempotency, original vs generated labels and UI. Provider and charging decisions remain real dependencies of affected operations. |

Primary trace points: `frontend/routes.tsx`, `frontend/features/analyses/new/NewAnalysisPage.tsx`,
`frontend/features/analyses/report/ReportView.tsx`, `services/rm_worker/audit_pipeline.py`,
`services/rm_worker/vision_stage.py`, `apps/deal_analyzer/vision.py`,
`services/rm_worker/importers/otodom_rental.py`, `services/rm_worker/tasks/batch.py`, and the three
`docs/parallel-handoffs/RM-376.md`, `RM-377.md`, `RM-378.md` reconciliation records.

Rental offers are asking observations, not achieved rents. The insert-once 90-elapsed-day cohort
cannot establish current active inventory, removed listings or repeated price changes. Keep daily
new-offer series separate from rolling eligible-cohort summaries. BDL locality scores are context,
not a property grade or an automatic financial multiplier.

An integration edge case to test while extending media/evidence: the new manifest permits **25 photos
plus 2 plans**, while `VisionOutput.photos` currently permits 25 classifications total and the vision
prompt requests one classification per submitted image. Verify the selected-input/output mapping at
the 27-item boundary. This is a source-level contract mismatch to resolve/test, not a live-provider
failure reproduced by this audit.

## GitHub acceptance gaps and required issue reconciliation

The following is a proposal, **not issues created by this audit**. Re-query GitHub before creating
anything; G/OTO/LCTX identifiers are requirement labels, not GitHub issue numbers.

| Existing issue | Verification and action |
|---|---|
| **#376 closed** | Good metadata slice, but its body also promises a versioned DealAnalysis media model and storage/retention spec. The shipped separate manifest is not integration into the canonical report. Record the precise closed slice and transfer unmet acceptance explicitly; do not reopen completed metadata coding. |
| **#377 closed** | Title says **persist** corpus/catalogue; body promises DB tables/repository, verified catalogue and integration/concurrency tests. These were not delivered. Correct the closure record and create linked persistence/source/ingestion follow-ups (or reopen if maintainers retain the original acceptance). Unit tests against a fake do not satisfy the original database acceptance. |
| **#378 open despite merged #380** | Body incorrectly says B-023 decisions were approved, expects DB tables and uses outdated paths (`market.py`, `market/bdl.py`). Update actual phase-1 paths and evidence. Keep remaining acceptance open or explicitly split children; do not close the full issue just because #380 merged. |
| **#48/#49 open** | Preserve source/provenance/coverage gates. Amend for full multi-level BDL context and the full 727-location corpus/nightly/window/recovery/history scope. Fix literal `\n` formatting if still present. National scope is settled; actual catalogue/source proof is not. |
| **#209/#16/#21 open** | Existing comparable-import path is partial progress. Expand acceptance beyond on-demand/monthly sidecars to durable corpus, scheduler, publication and consumers. Keep screener separate; rental/BDL data alone do not finish it. |
| **#282 open** | Current source/date/coverage acceptance is useful but insufficient for the expanded batch. Add explicit rental-history/freshness and BDL hierarchy/context/ranking consumers, with independently gated datasets. |
| **#283 open** | Remove obsolete question whether manual analysis is in scope. Retain unresolved fields/upload/retention/charge decisions, backend acceptance and security tests. |
| **#284 open** | Scope is required in this batch. Refine operations/provider/cost decisions and add persistence/job/media/tenant/budget acceptance; current UI-only body is insufficient. |
| **#211 open** | Body still says the pipeline never calls vision; current `audit_pipeline.py` and `vision_stage.py` contradict that. Reconcile existing offline integration vs remaining live quality/cost and new durable evidence work. Do not use this stale sentence to duplicate the stage. |

Suggested follow-up issue titles and minimum descriptions:

| Suggested title | Description / proof to include |
|---|---|
| G-01b: populate and privately serve durable audit media | Extend #376 with approved binary storage/retention, bounded allow-listed fetch, stable manifest association, tenant-safe content access, expiry/erasure, duplicate/retry tests. Real Postgres + fake image host journey; never claim production storage from an in-memory fake. |
| G-01c: render the persisted report photo and floor-plan gallery | Consume merged media API/content contract; display failure/expiry states, keyboard-accessible viewer, report reload, no cross-tenant leaks. Real-stack browser acceptance and required visual/interaction coverage. |
| G-02: persist OCR and factual equipment evidence in canonical reports | Version report contract, retain OCR and media-linked observations/provenance/unknown states, distinguish sale inclusion, migrate readers/fixtures, add report panels. Tests prove reloading needs no second model call and finances remain unchanged. |
| G-03: generate and persist grounded seller questions | Deterministic gap/evidence-driven questions with stable IDs/reasons/version and deduplication; server persistence and report UI. Prove unknown/conflicting facts generate appropriate questions without inventing claims. |
| OTO-01b: implement the Postgres rental corpus and run checkpoints | Implement protocol in production, migrations and unique source identity; real-DB retries/concurrency/overlap/location conflicts, immutable content, atomic coverage/watermark advancement. Link unmet #377 acceptance. |
| OTO-02: verify catalogue and complete all-location bootstrap | Acquire approved catalogue reference, verify all 727 unique paths, validate source filters/timestamps and partitioning beyond page limits; durable partial/empty/error coverage manifests. Offline fixtures plus separately authorised provider proof. |
| OTO-03: schedule nightly new-offer capture and gap recovery | Batch-lane scheduler, timezone/window contract, durable last-24h bounds, non-overlap, catch-up beyond missed days, idempotent restart and prior checkpoint preservation. Scheduler/restart tests against Postgres; operator command/runbook. |
| OTO-04: publish rental histories, cohort summaries and freshness | Atomic immutable daily histories, sample/coverage/source/age labels and backfill rules; comparables/API adapter; distinguish daily additions from eligible cohort. Test stale/gapped/zero/partial states. |
| LCTX-01b: persist BDL hierarchy, reviewed metrics and observations | Tables/crosswalk/versioning, production repositories, injected source importer, provenance/quotas/checkpoint/replay and publish pointer. No invented variable IDs or thresholds; offline tests can proceed with clearly test-only policies. |
| LCTX-02: publish approved explainable location comparisons/index | Approved reviewed metric list/weights/cohort/coverage/freshness/fiscal policy version; reproducible rank/components/exclusions and suppression. Build policy validation independently; activate only approved policy. |
| LCTX-03: expose bounded locality context in market and audit reports | Gmina/powiat/województwo facts, trends and comparisons with source/year/direct-or-proxy labels, deterministic bounded agent payload and report UI; no financial score substitution. |

Use #283 and #284 as parents for manual and interior backend/UI children rather than duplicate umbrellas.
Every real child needs exact owned files, a plain `Depends on: #...` line, acceptance-to-test mapping,
policy dependencies and an issue-local handoff. Split the larger rows into one-behaviour PRs when needed.

## Why the execution stopped early; problematic coordination files

The recorded worker startup guides explicitly targeted phase-1 contracts/repositories/pure tests.
Finishing those assignments naturally exhausted their local checklists. A coordinator must dispatch
the next slices, not end after three handoffs. This is a scheduling/acceptance gap, not evidence that
parallel development cannot work.

| File / area | Problem and required treatment |
|---|---|
| Root `EXECUTION-SUMMARY.md` | Historical pre-dispatch status, old SHA/worktree steps, and an incorrect blanket B-023-resolved statement. Its wave-1 success criteria are not batch completion. Treat as historical; use this audit and new resume prompt. |
| `docs/parallel-handoffs/EXECUTION-CHECKPOINT-2026-10-17.md` | Outdated ready-to-start states and unsubstantiated metric-policy approval. Current handoffs/canonical blockers supersede it; do not restart the old branches from its base SHA. |
| `WORKER-1/2/3-*-STARTUP.md` | Narrow initial slice instructions and some path/model assumptions were superseded during integration. Read as history only. New work orders must be derived from current source with a next-issue handoff. |
| `docs/CLAUDE-FEATURE-GAP-KICKOFF.md` | Already asks for the full batch, but needs an explicit post-wave scheduler loop and completion matrix. New prompt supplies them and points back to the full guide. |
| `CONTEXT.md`, `STATUS.md`, `BLOCKERS.md`, `LIMITATIONS.md` | Shared integration ownership is necessary, not permission to omit updates. Unique worker handoff → integrator updates in same feature PR. Preserve next-unused B/L IDs. `STATUS` is canonical, but date/visual-CI prose and stale approval tables still need implementation-PR reconciliation against live GitHub. |
| `README.md`, `CHANGELOG.md`, blueprint/roadmap/backlog | Reserve integrator ownership when changed; record exact deltas. Do not grant all workers concurrent edits or treat normal merge conflicts as owner blockers. Preserve same-PR documentation requirements. |
| `db/models.py`, Alembic versions, route/schema/type registries, lockfiles, privacy/deploy configuration | Explicit reservation and branch writer transfer; one open migration PR at a time. Other lanes continue pure logic, UI consumers of merged interfaces and tests while waiting. Never reuse the same Alembic revision or generate on competing branches simultaneously. |

Do **not** remove `.agent` rules to make an agent continue. The existing rules already allow independent
work, isolated writers and shared-document handoffs. The missing mechanism is continual work assignment
and proof against end-user acceptance, not a waiver of financial/security/owner boundaries.

## Immediate parallel schedule and real blockers

Start up to three ready workers plus coordinator; the coordinator is not a fourth implementation lane.

1. **Report lane:** preserve OCR/equipment evidence through versioned contracts and deterministic seller
   questions; populate media identities where settled. Binary storage/retention and affected paid work
   require recorded policy. Gallery follows the merged serving contract, not temporary upstream URLs.
2. **Rental lane:** first migration slot for the production corpus and shared contract tests on Postgres;
   then bootstrap/source verification, nightly recovery and histories. The catalogue blocker does not
   prevent production persistence/recovery code and controlled offline tests.
3. **BDL lane:** durable ingestion/repository design and independent importer logic/tests; reserve the
   next migration slot. Unapproved metrics/index policy blocks publication, not all ingestion plumbing.

Assign disjoint files before dispatch, including shared report-contract reservations. As each slice
finishes, integrate it and rotate available workers into gallery, manual, interior and Rynek consumers.
Allow a worker to pause for a merged prerequisite while another ready slice uses the slot. Do not keep
all workers idle behind one policy, migration reservation or pending CI run.

**B-023 is partly open.** All 727 locations and BDL location-context scope were approved; that did not
approve exact metrics/variable IDs/weights/publication thresholds, source attribution/terms or identify
the actual catalogue artifact. Storage/retention and manual/interior operation charges also need exact
recorded decisions. Prepare concrete decision packets from existing proposals; ask only unresolved
choices once and continue unrelated safe work. A generic `undecided` gate is not permission to publish.

## Feature completion versus finishing the project

Compared with the 2026-10-17 readiness snapshot, **settings #346, credits/checkout #366, API fuzz #350,
session-lifetime fix #363 and pinned visual CI #356 are now merged**. Do not schedule them from scratch
because the old report called them open. Checkout still has provider/CSP acceptance (B-017/B-024).

Other reachable pages remain pending: legal #279 and listing-writing #285. The listing assistant and
screener are distinct from seller questions and locality rankings. A prompt to finish the whole app
must retain them in a separate product/readiness backlog, without dropping this feature batch.

Full paid readiness still requires evidence beyond features: #210 sourced risk-free rate, sourced
CAPEX/exit-anchor decisions, #94 labelled accuracy, #211 live vision quality/cost, Paddle/accounting
#220/#43, legal #41/B-012, configuration #40, operations #15 and gates #35/#36/#37 (memory,
connections, timed restore), CI enforcement and release/browser evidence #286. Reconcile each issue's
current acceptance before claiming a gate passed. Existing offline fakes and green CI are valuable;
they cannot supply provider, owner or launch sign-off. No honest autonomous prompt can manufacture
these decisions or guarantee production readiness without them.
