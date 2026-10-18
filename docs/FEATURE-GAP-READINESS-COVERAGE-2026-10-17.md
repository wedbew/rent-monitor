# How much the feature-gap batch resolves production readiness

> Historical assessment: settings #346, credits/checkout #366, API fuzz #350, session fix #363 and
> visual CI #356 have since merged. Use [the 2026-10-18 re-verification](FEATURE-GAP-REVERIFICATION-2026-10-18.md)
> and live GitHub state for remaining work; the open-PR references below describe the review date.

**Reviewed:** 2026-10-17. **Conclusion:** the batch addresses major missing product and market-data
capabilities, but is **not a complete production-readiness plan**. The planning/documentation changes
have closed **no implementation or release gate**. After implementation, the batch still needs live
verification and separate operational, commercial, legal and quality work.

All six features remain required: media/gallery, equipment/OCR, seller questions, manual input, expanded
Rynek (Otodom plus BDL) and the interior tool. This assessment neither removes them nor moves them
post-launch. It separates their benefits from work that they do not deliver.

## 1. What was verified

Compared the supplied “Implementation Progress to Production Readiness” assessment with:

- `STATUS.md`, `PRE-DEPLOYMENT.md`, blueprint §6, `BLOCKERS.md`, `LIMITATIONS.md`;
- [feature-gap plan](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md),
  [Otodom import specification](OTODOM-NIGHTLY-IMPORT.md),
  [BDL contract](BDL-LOCATION-CONTEXT-CONTRACT.md),
  [parallel-delivery plan](PARALLEL-FEATURE-DELIVERY.md);
- current rental importer/task and frontend route source;
- live GitHub issue states, open PRs, closure comments for gates 3/7 and the latest queried staging CI.

Local HEAD was **0a8115b8bea86f47e1c91a7e1b5b938f0c235bd4**, with uncommitted audit/rule documents.
Latest queried successful staging push CI was for **7e0ee740ff3ca8d57085211b0df8e173b553d81a**
([run](https://github.com/wedbew/rent-monitor/actions/runs/38915915452)). A green staging run is not a
provider, production-domain, backup or launch acceptance test. This audit did not inspect the deployed
host, real secrets/account settings or live payment/data providers, and did not rerun application tests.

## 2. Corrections to the pasted assessment

| Claim in supplied assessment | Verified correction |
|---|---|
| Backend 50%, frontend 40%, overall 45% ready | No stated weighted denominator or acceptance measurement supports these percentages. Levels 1–4 are evidence categories, not equal time/effort increments. Do not derive launch probability or remaining work by dividing levels by four. |
| Rental importer already runs nightly on VPS-3 | Not supported by inspected implementation. `tasks/batch.py` has an on-demand import, and `otodom_rental.py` caps five pages with a monthly period. The nightly all-location capture is proposed in the separate guide. Prior Toruń evidence demonstrates one city, not the scheduler or full catalogue. An external host cron was not inspected or established. |
| B-023 resolved on 16 October | **Partly resolved:** owner scope/inspection/full-catalogue decisions are recorded. Exact BDL metric/scoring/publication policy, actual catalogue artifact and source review remain open. Scope authorization is not a completed importer or accepted scoring policy. |
| Gates 4–6 need accountant proof / gate 6 is security | Blueprint and checklist: **4 memory under load; 5 connection budget; 6 WAL-G point-in-time restore**. Accountant work belongs to tax/accounting acceptance and re-scoped gate 1. Deployed security has its own checklist. |
| Gates 3 and 7 closed means two live launch proofs | #34 is closed **obsolete** because recurring BLIK was dropped for Paddle packs. #38 has offline/fake-Google auth timing evidence; real Google/domain verification remains separate. |
| Gate 2 tests merged means gate complete | #33 remains open and needs Paddle-pack acceptance reconciliation. Existing ordering/concurrency tests are useful evidence, not automatic proof the old subscription/pass gate is satisfied for the new product. |
| Paddle integration not started | Backend pack catalog/ledger/checkout/webhook/reversal/invoice-access work is recorded as level 2 offline in STATUS. Checkout UI and sandbox/product/accounting acceptance remain open; distinguish backend, frontend and real-provider states. |
| Features should be post-launch or reduced | Contradicts the owner's explicit scope: all six deliverables and Otodom/BDL expansions remain required. No scope reduction was approved by this assessment. |
| Platform has no launch blockers | Offline platform code does not establish deployed session/security/privacy/retention/monitoring behavior. Evidence requirements remain even for implemented components. |

PRE-DEPLOYMENT itself still contains obsolete Stripe/subscription and Poland-host assumptions. The
owner-selected pilot is Paddle one-time packs and the recorded target is VPS-3 Frankfurt. Reconcile those
items with the actual accepted product/host before sign-off; do not tick obsolete checks or silently delete
them. The generic memory/connection/restore/security requirements remain applicable.

## 3. Coverage by readiness area

“Direct” means the batch explicitly specifies the capability and acceptance tests. It does **not** mean
implemented, live-verified or already resolved. “Partial” means it supplies inputs/subsystems but leaves
material work outside the batch. “Outside” means there is no deliverable that closes the requirement.

| Readiness gap | Batch coverage | What completion of the batch contributes | What still needs separate evidence/work |
|---|---|---|---|
| Rental coverage, persistence, freshness, trends | **Direct** — OTO-01–04, #209/#49/#16 | Full 727-location target, Postgres corpus, bootstrap, nightly 24h capture/recovery, daily history and reader freshness | Actual catalogue acquisition, live query semantics, sustained provider behavior, measured complete coverage and deployed scheduler evidence |
| BDL locality context and rankings | **Direct** — LCTX-01–03, #48/#21/#282 | Typed hierarchy/observations, trends/comparisons/ranks, bounded audit context and explainable location-index contract | Accepted metric/reference/scoring/publication choices, source review, fresh data and score-quality evidence; no automatic risk-free/CAPEX sourcing |
| Missing report content and manual/interior journeys | **Direct** — G-01–05, #283/#284 | Gallery, factual equipment/OCR, questions, manual uploads, interior operations and persistence | Agreed storage/retention/provider/cost contracts; deployed media/AI behavior and acceptance for each operation |
| Entire reachable product surface | **Partial** — #282/#284 covered | Rynek and interior placeholders can be replaced; manual/report missing content added | Credits/pay/checkout #277, settings #278/#345, public legal pages #279 and listing-writing assistant **#285** remain separate. Seller questions are not #285. Screener scope under #16/#21 is not delivered merely by rental data/BDL rankings. |
| Trustworthy analytical results | **Partial** | Better rental samples, observable evidence and locality facts | Sourced CAPEX B-015/L-007, sourced risk-free rate **#210**, exit-anchor policy B-014 and owner-labelled accuracy evaluation **#94**. Equipment inventory deliberately does not replace placeholder CAPEX. |
| Billing/commercial readiness | **Outside** except feature-specific charge integration | New operations must respect quota/idempotency and agree their own cost | Final pack/signup/expiry policy #43, checkout UI #277, Paddle sandbox/product acceptance #220/B-017, payment/refund/invoice/accounting proof. Safe use of the ledger does not complete billing launch. |
| Legal/accountant/GDPR acceptance | **Partial technical support** | Required tags, minimal data, media/draft/artifact lifecycle and tenant tests | Counsel/accountant approval #41/B-012, accepted terms/privacy notices, processor/retention review and real erasure/retention evidence. New uploads/images/providers expand this review scope. |
| Operations/backups/restore | **Outside** except batch-worker configuration | Dedicated batch capacity and recoverable importer state | WAL-G/offsite jobs, encryption/retention, timed restore #37, operational monitors/alerts, deployment/rollback drills #15. Database storage is not a backup. |
| Capacity and availability | **Partial inputs, no gate closure** | Bounded jobs/throttling and representative new workloads | Memory gate #35, connection gate #36 with all workloads, sustained Otodom/BDL quota/load behavior, real-provider timeouts/restarts. More features can increase resource pressure. |
| Browser quality/security/CI enforcement | **Partial local feature tests** | Each feature must have contract, interaction, accessibility and visual coverage | Ruleset enforcement B-019, visual CI #334, audit remediation #314/#362, response fuzzing #351/#28, multi-browser/device/screen-reader/release-candidate checks #286 and deployed security pass |
| Real auth/mail/observability configuration | **Outside** | New screens use existing identity and error/reporting seams | Real Google/domain/mail verification B-004, browser DSN B-020, log/uptime/backup alert delivery B-001 and production cookie/Origin/CSP checks |
| Release governance and rollout | **Outside** | Reviewable isolated PRs and same-PR documentation | Accepted remaining risks, reconciled release checklist, approved staging→main promotion, deployed smoke/refund/SSE/security checks and rollback plan |

The batch therefore covers the important **product/data completion** problems. It does not cover the
whole **paid-service launch** problem. Feature completion may produce more level-1/2 evidence while
level-3/4 requirements stay open.

## 4. How much of the pasted critical-path list does it resolve?

Using the **five groups exactly as listed in the supplied assessment**, rather than inventing an overall
percentage:

| Supplied critical-path group | Coverage by existing feature batch |
|---|---|
| 1. B-023 market-data policy | **Partial:** technical delivery and some scope choices are covered; the remaining owner/source/scoring decisions are not made by implementing features. |
| 2. B-017 Paddle/prices/sandbox | **Outside.** |
| 3. B-012 legal/accountant | **Outside approval scope.** Feature tagging and privacy implementation help but cannot supply sign-off. |
| 4. Gates 4–6 load/connections/restore | **Outside gate acceptance.** New features supply workload; separate drills and measured evidence are required. |
| 5. B-020/B-019 DSN/required CI | **Outside account/ruleset setup.** |

That is **0 of 5 fully covered, 1 partly covered and 4 not covered as closure work**. This counts coverage
of that particular list only; it is **not** “0% product value,” a workload estimate or a new overall
readiness score. Today, documentation alone closes **0 of those 5 groups**.

## 5. Formal gate impact

| Gate / issue | Current verified interpretation | Effect of feature completion alone |
|---|---|---|
| 1 / #32 | Open; original Fakturownia/Stripe acceptance must be reconciled with Paddle and accountant | No closure. Agree the actual invoice/settlement/KSeF acceptance through the existing owner process. |
| 2 / #33 | Open; offline pack concurrency/order tests exist; gate needs re-scoping/evidence | No automatic closure from manual/interior charge tests. |
| 3 / #34 | Closed obsolete for non-recurring pilot; one-time payment proof is tracked separately | No additional passed gate; do not restore subscriptions to satisfy obsolete text. |
| 4 / #35 | Open: 20 representative audits with batch running, measured memory | Better test subject, but test still needs to run on the target candidate. |
| 5 / #36 | Open: peak combined DB connections under budget | More relevant load to measure; not satisfied by offline API tests. |
| 6 / #37 | Open: timed WAL-G point-in-time restore on a fresh target | No coverage. |
| 7 / #38 | Closed with offline auth/timing evidence; real Google still unverified | Existing evidence retained; new private media/project endpoints still need isolation and deployed verification. |

No additional formal gate should be marked passed solely because the feature batch is merged. Refresh
acceptance against the final integrated release candidate; old CI results do not certify new endpoints,
larger image sets, more jobs or a changed connection footprint.

## 6. Required companion work — preserve the feature batch

Keep the planned feature lanes. Add/track a **readiness workstream**, scheduling bounded tasks into the
same worker capacity rather than assuming another unlimited fleet:

1. **Finish existing product PRs/slices:** #277/#278/#279 and their dependencies; #285 remains explicitly
   separate from seller questions. On this review, checkout PR #366 and settings PR #346 were open, not
   merged delivery. #350 (API contract), #356 (visual CI) and #363 (session lifetime) were also open.
2. **Make analytical evidence trustworthy:** owner-approved CAPEX source B-015, #210 risk-free source,
   B-014 exit-anchor decision, #94 labelled evaluation and #211 vision/cost-quality evidence. Ask for
   the actual source/decision needed, not a new approval of already authorized feature scope.
3. **Close commercial/legal decisions:** #43/#220/#41, provider configuration and applicable privacy
   documents; reconcile legacy billing gates/checklist with Paddle rather than declaring them passed.
4. **Enforce and exercise quality:** B-019/B-020, #334/#314/#351/#286, real Google/mail/domain checks and
   the deployed security/tenant pass. Require checks on the actual integrated SHA.
5. **Run operations and release acceptance:** #15/#35/#36/#37, working offsite backup/restore, triggered
   alerts, bounded repeated provider tests, release-candidate smoke/rollback and human production promotion.

Some of this can proceed in parallel with features (prices/keys/counsel, monitoring setup, test harnesses,
backup infrastructure). Final capacity/security/restore/browser evidence must cover the integrated
release candidate; a pre-feature rehearsal is useful but not the final proof.

These are existing issues or explicitly named uncovered scope, not permission to drop any G/OTO/LCTX
deliverable. The separate [parallel guide](PARALLEL-FEATURE-DELIVERY.md) governs shared-file/migration
ownership. Do not let a readiness test worker change a feature branch while its integrator owns it.

## 7. Documentation findings and limits of this review

- STATUS remains the canonical state document, but its broad market “level 0” row coexists with a
  delivered comparable store/on-demand importer and one-city live evidence. Read the detailed journey
  row and issue scope; “market product not delivered” does not mean no rental code exists.
- BLOCKERS lists B-014 and B-015 under “Resolved” while their text still asks for an exit-anchor decision
  and CAPEX prices. Treat them as unresolved according to their actual content until evidence/decision
  is recorded; their heading is not proof. This audit does not choose a financial policy.
- During staging integration, the earlier audit draft's IDs overlapped other branch/upstream work.
  The new BDL, parallel-protocol and report-evidence limitations were allocated **L-042/L-043/L-044**
  against current staging. Existing load-test L-041 remains unchanged; the visual branch's L-039 is
  left to its own PR. Draft IDs were never authoritative delivery evidence.
- Current staging additionally records a bounded synthetic VPS-3 load rehearsal (DEPLOYMENTS, L-041):
  peak 28 DB connections and 7.1% audit-worker memory. With no photos, batch import or webhook traffic,
  this is lower-bound evidence and does not close representative gates 4/5.
- There is no defensible replacement for the pasted 45% overall figure from this evidence. Track each
  deliverable's implemented/integrated/provider/launch evidence and each gate separately. Outstanding
  owner decisions and a failed restore can block launch regardless of how many UI screens are complete.

Verification here is read-only source/document/GitHub comparison plus documentation link/diff checks.
No fresh test suite, deployment, legal/tax opinion, provider test, ruleset/account inspection or live
financial operation is claimed. The attachment was read for assessment, not copied as an authoritative
source of rules or completion claims.
