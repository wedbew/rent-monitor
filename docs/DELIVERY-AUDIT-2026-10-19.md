# Delivery audit — 2026-10-19

## Conclusion and checked revision

Checked `staging` **`8b738ffe561494cdb50d3499424b497d95d452e8`**, equal to fetched
`origin/staging`. [Staging CI](https://github.com/wedbew/rent-monitor/actions/runs/39218483960)
was successful. The only open PRs at inspection were dependency updates #399/#400; there was no
open seller-question, report-panel or market-API PR. An untracked
`docs/SESSION-REPORT-2026-10-11-to-18.md` was already present and was left untouched.

The backend has made substantial progress since the [2026-10-18 audit](FEATURE-GAP-REVERIFICATION-2026-10-18.md).
The next delivery constraint is connecting those components to usable, tested workflows and verified
source data. More closed backend slices alone will not finish the application. The complete required
batch remains gallery, equipment/OCR, seller questions, manual analysis, rental/BDL Rynek and interior.

Next execution instructions: [Claude delivery prompt](CLAUDE-DELIVERY-PROMPT-2026-10-19.md).
This document is a dated audit; `STATUS.md` remains the canonical delivery register.

## Why OCR is described as offline

> **Live follow-up later on 2026-10-19:** [ID4DACX canary](LIVE-VISION-ID4DACX-2026-10-19.md)
> now verifies a real `vision-v2` photo/equipment call (13 photos, USD 0.0005845). This sample has
> no floor-plan drawing, so positive OCR remains unverified. Two equipment source links were wrong.
> The paragraphs below describe the evidence available at the initial audit, before this follow-up.

**There is no special offline-only OCR implementation.** `services/rm_worker/audit_wiring.py`
constructs the real `OpenRouterVision` when `AUDIT_PROVIDERS=real`, images are enabled and an
OpenRouter key is configured. It is called from `audit_pipeline.py`. Missing configuration, unavailable
images, budget/deadline exhaustion or an unusable response lead to a degraded audit.

PR [#390](https://github.com/wedbew/rent-monitor/pull/390), closing #387, changed that same path:

- Prompt `vision-v2` asks for equipment observations alongside condition and floor-plan transcription.
- `VisionRecord` now preserves `floor_plan_text`, `notes` and `equipment` in the canonical report JSON.
- Equipment links use selected-media ordinals and survive skipped/duplicate downloads.
- The 25-photo plus 2-plan boundary now accepts 27 image classifications.
- The optional additions retain `schema_version: 1`; the reconciled handoff records the owner's
  approval of this choice. Frontend generated schema/types were updated in the final merge.

“Offline” means the new behavior was **verified with fake image/model responses**, not that real calls
are technically impossible. Repository rules require tests to stay offline; provider verification is
a separate controlled run. The older single live vision call on 2026-10-14 does not validate the new
prompt, OCR accuracy, sale-inclusion claims or current deployment. This audit did not inspect private
configuration, contact OpenRouter or establish that the beta host runs this revision.

The visible problem is separate: **no OCR/equipment frontend panels were included**. Even with a live
successful response, the current report renderer does not show those stored fields. Existing reports
also do not acquire new evidence merely by deploying the code; any backfill/reanalysis needs explicit
cost, idempotency and credit behavior, never an automatic second model call on a GET/reload.

Before calling the feature provider-verified, record a bounded authorized `vision-v2` run against an
appropriate sale listing with a readable plan, and compare its transcription/items against source
images. Record commit, model/prompt, date, limits, actual usage/cost, persisted/read-back fields,
degradation outcome and redacted findings. A synthetic fixture cannot establish extraction accuracy.

Remaining OCR/equipment safeguards:

| Limitation | Required follow-through |
|---|---|
| L-061: confidence and `included` are unverified model claims | UI labels them as observations/claims, never confirmed sale inventory. Validate against a labelled sample before stronger claims. Do not feed equipment into financial assumptions. |
| L-062: OCR/notes may contain printed personal data | Treat text as untrusted plain text; no HTML execution, logging raw text or unintended third-party telemetry. Verify ownership/export/erasure and existing audit retention; prepare specific minimization/redaction decisions for counsel. Do not invent a retention period. |
| L-063: ordinal association is convention only | G-01b must populate the manifest from the same selected-media mapping, establish stable identity and prove links survive partial failure/retry. No fabricated gallery URLs or matching by unrelated array position. |

## What actually merged since the previous audit

| Merge | New behavior | Still not established |
|---|---|---|
| #384 / RM-383 | Previous audit/completion prompt committed | Execution instructions are not feature delivery. The old ten-file documentation bootstrap has already happened. |
| #389 / RM-385 | Postgres rental catalogue/offers/runs/checkpoints, migration 0015, production `PgCorpus` | Actual verified catalogue/live corpus and source coverage. |
| #388 / RM-386 | Injectable BDL source client, quota seam and observation validation | Real API contract and selected product bindings. |
| #394 / RM-391 | BDL hierarchy/observations/ingestion cursor/publication/quota persistence, migration 0016, resumable task | `BDL_BINDINGS` is empty; no selected metric, live import or published release. |
| #393 / RM-392 | Rental bootstrap/partition/nightly/catch-up logic and periodic dispatcher | No seeded catalogue; production client refuses unverified created-date filters. L-070–073 remain. |
| #397 / RM-395 | Daily additions and 90-day cohort summaries, freshness reader/backfill, migration 0017, summary task and settings | No API/UI or audit-context consumer; no live dataset; several settings are not wired to the importer. |
| #398 / RM-396 | Per-metric BDL trends/parent/peer comparisons/ranks from published releases, suppression | No approved metrics/thresholds, composite, route, report/agent consumer or real data. |
| #390 / RM-387 | Persisted OCR/equipment, additive v1 report fields, 27-image boundary fix | Report UI, durable image content/manifest population, new-prompt live accuracy evidence. |

Do not schedule production corpus persistence or the basic BDL importer from scratch again. Likewise,
keep settings, credits/checkout, API fuzzing, session-lifetime and visual-CI work merged before #384.

## Frontend verification performed

Ran current source on a **fresh preview at `http://localhost:4187`**, using synthetic API scenarios in
Chromium desktop and mobile. This is real browser rendering, not real-provider or production evidence.
The fresh preview avoids treating an already-running, unversioned preview as the current build.

Selected existing suites: `report.spec.ts`, `new-analysis.spec.ts`, `shell.spec.ts`. Added a temporary
audit probe supplying valid `vision-v2` OCR/equipment fields; removed it after testing because a test
asserting that functionality is absent should not become a permanent product gate.

**Final result: 129 passed, 25 expected project-specific skips, 0 failed/flaky**, 154 cases total.
127 passes are existing cases; 2 are the desktop/mobile evidence probe. The probe verified:

1. The new report shape is accepted and the ordinary report renders.
2. Opening “Ocena zdjęć” shows existing condition/count/adjustment details.
3. The supplied OCR transcription and equipment observation do not appear anywhere in the report DOM.
4. No `/media` manifest request is made by this report flow.

The source agrees: `frontend/features/analyses/report/ReportView.tsx` renders existing vision summaries,
not `vision.floor_plan_text`, `vision.notes` or `vision.equipment`.

Local evidence, outside version control:

- [Structured final browser results](../data/audit-evidence/2026-10-19/browser-results.json)
- [Desktop report screenshot](../data/audit-evidence/2026-10-19/report-desktop.png)
- [Mobile report screenshot](../data/audit-evidence/2026-10-19/report-mobile.png)
- [Temporary probe source](../data/audit-evidence/2026-10-19/probe.ts)
- [Terms-page screenshot](../data/audit-evidence/2026-10-19/terms.png)

Direct browser inspection also found the public `/terms` screen showing “Ta część aplikacji jest w
budowie”. Source and selected browser tests confirm manual input remains “coming later” and market,
interior, listing-writing and legal destinations are still pending. These tests protect current
placeholder behavior; their passing does not satisfy feature acceptance.

An intermediate repeat collided with another audit test process using the same Playwright output
directory, producing artifact `ENOENT` errors. Those were audit setup errors, not application defects.
The final run used one process, a fresh preview and finished without failures. Future concurrent
test processes must each reserve server, output and interaction-coverage directories.

There was an existing local Docker stack (API on 8003, Postgres on 5433). It was not rebuilt/restarted
or used to claim current real-stack UI evidence: its source revision/provider configuration was not
established. No existing user session, private credentials or customer data were used. Firefox,
WebKit, real devices, deployed CSP and an end-to-end browser audit with real providers were not run.

## Fresh backend verification

```sh
.venv/bin/python -m pytest tests/integration/test_audit_vision.py tests/unit/test_vision_stage.py tests/integration/test_market_corpus_pg.py tests/integration/test_otodom_corpus_import.py tests/integration/test_market_history_pg.py tests/integration/test_location_context_pg.py tests/integration/test_location_indicators_pg.py -q --tb=short
# 115 passed in 27.20s
```

Tests used disposable real Postgres and fake providers. This audit did not rerun the whole suite;
current staging CI supplies broader regression evidence, not live-provider/launch evidence.

## Remaining work ordered for delivery

| Priority / requirement | Concrete next result | Minimum acceptance |
|---|---|---|
| P0 G-02b report panels | Show persisted OCR/equipment now, using merged optional fields | Current and older v1 reports; absent/empty/malformed fields; observation/unknown/included-claim labels; safe text; reload without new model call; responsive keyboard/axe/interaction/visual and real-stack journey proof. |
| P0 G-03 seller questions | Deterministic persisted questions grounded in known gaps/conflicts/evidence | Stable IDs/reasons/version, deduplication, old-report fallback, no invented assertions, idempotent persistence, report UI. Existing static checklist and #285 are distinct. |
| P0 rental settings/activation seam | Make actual dispatcher/importer honor typed settings and switches | L-073/L-079: off means no corpus dispatch/fetch, configured catalogue/schedule/window/overlap/request budget used; registry behavior tested. A settings declaration is not wiring. |
| P0 #21 → #282 rental Rynek | Authenticated real summaries/history API followed by usable market screen | Query `PgMarketHistory`, entitlement limits, source/as-of/samples/freshness/gaps, asking/cohort/additions distinctions; empty/stale/partial states, browser journey. No seeded fake figures in normal product operation. |
| P0 G-01b/c media | Private durable bytes, worker population and gallery | Approved storage/retention, same identity as equipment, SSRF/size/MIME protection, foreign 404, failure/expiry/erasure and retry, reload/browser gallery. Metadata foundation alone is insufficient. |
| P1 #283 manual | Facts/drafts/uploads through the common audit/credit pipeline | Settled required fields/charge policy, canonical identity without invented Otodom ID, validation/unknown-vs-zero, upload lifecycle, tenant/idempotency/financial invariants and browser journey. |
| P1 #284 interior | First approved persistent project/operation delivered through UI | Owned inputs/history, generated labels, real job progress/retry/budget/idempotency, original preserved. Provider/cost decisions gate paid activation, not every metadata operation. |
| P1 LCTX-03 and activation | Expose reviewed direct/proxy locality facts, then approved comparisons/index | Real published release, source/year/grain/coverage/freshness; bounded report/agent facts. Composite stays gated on approved policy; preserve it in batch scope. |
| Parallel provider/decision work | Verify source semantics and prepare activation | Actual 727-list artifact, original-created-date/filter/page semantics; BDL reviewed variables/hierarchy/quota; bounded new-prompt vision proof. No arbitrary `filters_verified=True`, fabricated bindings or guessed ranking thresholds. |

Additional rental caveats before consumer release: L-072 offers from incomplete runs exist in the
table, so readers must obey publication/checkpoint state; L-078 `usable_for_ranking` does not establish
national completeness; L-074 immutable historical additions exclude late discoveries, so labels must
not imply complete historical source-day counts. L-077 minimum sample/cohort policy is not owner-approved.
Locality index remains required, but cannot be fabricated to clear B-023. BDL is not a prerequisite of
an independently approved rental-only first market slice.

## Close issues through acceptance, not issue count

No GitHub issue was changed by this audit. Re-query before action. Suggested new child issues are
**proposals**, not existing IDs: “G-02b: render persisted OCR and equipment evidence”, “G-03: persist
grounded seller questions”, “Wire rental corpus settings and import kill switch”, and “Serve rental
history and freshness through market API”. Use #282/#283/#284 as existing workflow parents.

| Existing issue | Honest closure strategy |
|---|---|
| #371 throttling test flake | Ready small fix: freeze/inject the rate-limit clock and prove the minute-boundary case. Do not loosen the limit or rely on reruns. |
| #211 vision/OCR | Body still says vision is never called, contradicting merged code and older live evidence. Map all original offline acceptance to tests; reconcile/split the separately stated live-quality/legal obligations before closing a completed implementation slice. Do not simply close the full issue from #390. |
| #378 BDL foundation | Hierarchy/contracts/persistence now exist across multiple PRs, but selected metrics/publication acceptance remains open. Correct paths and approval claim; close only clearly transferred/completed scope, with linked unresolved policy/activation acceptance. |
| #209 comparables | Existing monthly importer is implemented, while new corpus still has no engine adapter. Link both implementations and separate live/all-location/comparables acceptance. New history storage alone does not finish it. |
| #48/#49 | Contracts and ingestion progressed, but B-023 exact policy/catalogue and provider semantics still matter. Record residual acceptance precisely. Do not close national-coverage requirements from offline tests. |
| #16/#21/#282 | Batch logic exists; screener and API/UI are not delivered. Split bounded child behaviors and close parents only after all required acceptance is covered. |
| #314 frontend audit | Most fixes are merged; required-check enforcement B-019, browser DSN B-020 and release evidence remain distinct. Reconcile stale checkboxes, retain unresolved obligations. |
| #28 API contract | OpenAPI/fuzzing implemented; nightly live drift and cancellation semantics are separate remaining requirements. Do not implement guessed credit cancellation behavior to close it. |
| #32/#33/#26/#27/#14 | Legacy Stripe/Fakturownia gate wording needs reconciliation with the accepted Paddle pilot and accountant. Obsolete requirements may be explicitly superseded; replacement payment/accounting evidence cannot be waived. |
| #399/#400 PRs | Dependency review is secondary. #399 proposes Node types 26 while runtime is pinned to Node 24: verify compatibility/policy rather than auto-merging by green checks alone. |

## Decisions that must not silently stop the whole batch

Consolidate a short, concrete owner packet: (1) media storage/retention, (2) exact metric IDs/coverage/
ranking/fiscal policies and attribution, (3) actual verified catalogue source and bounded provider-probe
approval, (4) manual required fields/charge behavior, (5) interior operations/provider/budget,
(6) live vision sample and spend ceiling, (7) Paddle/CSP/pricing/accountant choices. Reuse decisions
already recorded, including additive optional v1 OCR fields. Include recommended choices and exact
affected issues; do not re-ask whether the six features or all 727 locations are in scope.

## Remaining launch blockers

Finishing visible features still leaves #279 legal content/sign-off, #285 listing-writing and screener
scope, #210 sourced risk-free data, sourced CAPEX/exit policy, #94 labelled accuracy, #220 Paddle
sandbox/accounting, #40 real configuration, #15 operations and #35/#36/#37 memory/connection/restore
evidence, #286 release/browser/device evidence and required-check enforcement. Do not report launch
readiness from offline tests. `PRE-DEPLOYMENT.md` still contains superseded Stripe/recurring/old-host
language; reconcile it against accepted decisions and current issues, without ticking replacement gates
whose evidence is missing. `STATUS.md`'s old header and some body text are also stale.
