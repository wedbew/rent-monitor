# Claude delivery prompt — owner decisions consolidated

Paste the execution block into Claude Code in this repository. The
[owner decision record](OWNER-DECISIONS-2026-10-19.md) contains the confirmed instructions and key-name
inventory. Routine choices are delegated; external approvals/configuration remain evidence-based gates.
This prompt starts execution only when submitted to Claude; no workers are started by saving it.

```text
Act as RentMonitor coordinator/integrator. Deliver the missing app workflows, verify them in a browser
and through the real backend, and close issues whose actual acceptance is fulfilled. Execute without
recurring owner questions. Choose/document/test reversible implementation and versioned policy choices
under the owner's delegation. If an unavailable or unauthorized external action blocks something,
record its precise dependency and continue other ready work. Do not fabricate approval or bypass
runtime permissions. Main promotion and public paid launch are not authorized by this prompt.

READ FIRST AND CHECK CURRENT STATE
Read CLAUDE.md, .agent/agents.md, applicable canonical rules (parallel-work, delivery, blockers,
pull-requests, frontend, architecture, legal-tags, poc-reference), CONTEXT, STATUS, LIMITATIONS,
BLOCKERS, PRE-DEPLOYMENT, relevant blueprint/ENGINE-SPEC and:
- docs/OWNER-DECISIONS-2026-10-19.md (confirmed owner instructions override older open-policy text)
- docs/DELIVERY-AUDIT-2026-10-19.md
- docs/LIVE-VISION-ID4DACX-2026-10-19.md
- docs/FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md
- docs/OTODOM-NIGHTLY-IMPORT.md
- docs/BDL-LOCATION-CONTEXT-CONTRACT.md
- docs/PARALLEL-FEATURE-DELIVERY.md and relevant reconciled worker handoffs.
Older informational-only BDL wording is superseded by the separate adverse scenario approved below.

Fetch/recheck staging/GitHub, dirty-file ownership, open issues/PRs/checkpoints, active worktrees and
CI. Audit baseline was 8b738ff; use the actual latest green staging. Already merged at that audit:
#384 documentation, #389 rental Postgres corpus, #388 BDL client/validator, #394 BDL DB/importer,
#393 rental bootstrap/nightly logic, #397 daily history/freshness/settings, #398 BDL indicators,
#390 OCR/equipment persistence and generated SPA schema/types. Settings/credits/fuzz/session/visual-CI
work was also merged. Reuse it; do not repeat contract-only foundations. UI/activation work was absent.

COMMIT PENDING DOCUMENTATION FIRST
The old ten-file bootstrap is already merged in #384. Review and commit the new owned documentation
through a real issue, rm-<issue>-<slug> branch, required checks and PR to staging; no direct staging push.
Expected paths: CONTEXT.md, docs/STATUS.md, docs/LIMITATIONS.md, docs/BLOCKERS.md,
docs/CLAUDE-FEATURE-GAP-KICKOFF.md, docs/CLAUDE-FEATURE-GAP-FINISH-PROMPT.md,
docs/DELIVERY-AUDIT-2026-10-19.md, docs/LIVE-VISION-ID4DACX-2026-10-19.md,
docs/OWNER-DECISIONS-2026-10-19.md and this prompt. Stage explicitly by name; skip files already merged.
The pre-existing untracked docs/SESSION-REPORT-2026-10-11-to-18.md is not yours to rewrite/stage without
establishing ownership. Never git add -A over unrelated changes or commit ignored live photos/artifacts.
Merge under current PR rules and verify staging CI before worktrees consume these instructions.

OWNER POLICIES — IMPLEMENT WITHOUT ASKING AGAIN
1. Private EU product object storage, separate from backups; ownership/metadata in Postgres. Retain
   normalized EXIF-stripped media only: report/project media 30 days, abandoned uploads 7 days;
   account erasure and existing backup expiry apply. Verify bucket purpose/region/privacy. Implement
   and test lifecycle/adapter even if provisioning is unavailable. Record this approved narrow media
   architecture exception in ADR/blueprint/canonical architecture rules before implementing it.
2. Gross report packs: 10 PLN/1, 40 PLN/5, 70 PLN/10. Verified signup grants 3 credits once. Purchased
   unused credits expire 12 CALENDAR months after purchase; disclose actual expiry before purchase.
   Document/test anniversary, timezone/leap-day, lot/reservation/refund/dispute behavior. Choose a
   conservative compatible migration under delegated authority; preserve recorded customer rights,
   do not retroactively impose undisclosed expiry. No live customer payments/refunds authorized.
3. Manual: sale intent, whole ownership, asking price, area, rooms and resolvable location required.
   Unknown ownership cannot submit. Drafts/uploads free. Completed/degraded report uses one credit;
   existing failure-release/idempotency/RENT/fractional rules apply. Never invent an Otodom identity.
4. Queued-only cancellation releases the reservation. Running audits return 409 and finish normally.
   Prove cancel/start races yield exactly one terminal result/settlement.
5. Interior: one room photo -> saved concept -> optional generated image. Free for authorized beta
   testers under the shared test allowance; public paid generation disabled. Claude selects a
   supported provider/model. Durable ownership/jobs/progress/retry/history/erasure and generated
   labels are required; no unlimited free public generation or financial use of generated images.
6. Paid AI tests: USD 5 TOTAL for this batch across every worker/session and OCR/equipment/interior;
   max USD 0.50 per attempt. Use one durable atomic batch reservation/spend record; count retries
   and ambiguous paid outcomes and retain monthly/provider caps. Conservatively include the prior
   ID4DACX USD 0.0005845. Do not reset on restart, ask for more budget, automatically reanalyse old
   reports or charge on GET/reload. If cost cannot be bounded or allowance is exhausted, stop affected
   paid attempts and continue safe offline work. These caps are not per-worker or retail prices.
7. Otodom: collect FRESH data for all 727 locations. Validate small source/filter/pagination probes,
   then run complete bootstrap and nightly imports under existing throttle/request budgets. Build
   and validate a fresh catalogue rather than waiting for a POC artifact. No POC data/code copy.
8. BDL: select source-verified metrics, omit unresolved variables, label measured/proxy grains. Choose
   and document versioned coverage/freshness/cohort/fiscal/scoring policies. Publish an EXPERIMENTAL
   location index with sources/components/exclusions/limitations, a demographic-decline warning,
   and a SEPARATE adverse financial scenario for vacancy, rent growth and exit value. Keep BASE
   financial results separately visible and unchanged. Update ENGINE-SPEC/ADR first; all financial
   math in deal_analyzer with Decimal, reproducibility, sensitivity/monotonic tests and honest
   missing/stale-data suppression. Stress assumptions are not empirically proven causal forecasts;
   never multiply a property grade by a locality score or apply the same risk twice.
9. Under delegated source/policy authority, select a verifiable PL 10-year-yield source and research/
   version sourced CAPEX assumptions with provenance/freshness/fallbacks. Preserve the approved BASE
   exit formula and historical report assumptions; the BDL adverse scenario is separate. Do not
   fabricate prices or certify them by POC agreement. Use available public/authorized sources;
   no new paid subscriptions/purchases are authorized by source-selection delegation.
10. Paddle SANDBOX verification is authorized; the product already exists per owner. Verify sandbox
    mode and reuse matching resources before creating duplicates. Implement the approved prices/
    allowance/expiry. Grant purchased reports only from verified signed/idempotent events, not a
    success redirect. Reconcile ambiguous purchases without duplicates; failed audit reservations
    release independently of payment refunds. Test sandbox abandonment/failure/delay/replay/refund/
    expiry/concurrency and visible recovery. Use current official provider documentation for any
    integration changes; legacy Stripe/Fakturownia text must not silently dictate Paddle behavior.
11. CSP exception approved: style-src-attr 'unsafe-inline' for the existing Paddle overlay. Preserve
    scripts and unrelated directives; allow only verified required hosts, test actual Caddy behavior.
12. Deploy green staging to the CURRENT beta VPS; securely supply missing application configuration.
    Add existing frontend/browser-journey/visual jobs as required on staging/main without weakening
    other protections. Run bounded synthetic load/restore drills in isolated disposable databases,
    never overwriting existing app data/volumes. Measure results; same-host restore is not automatically
    the fresh-host gate. No main promotion, destructive infrastructure or arbitrary settings authority.

CONFIGURATION: USE EXISTING ACCESS WITHOUT EXPOSING SECRETS
The decision record contains owner-supplied variable NAMES, not verified values/scopes. Existing
credentials may be used internally by authorized application/provider/deployment helpers. For beta
transfer use a minimal app-runtime whitelist, secure transport, host-specific mapping and non-secret
presence/health results. No raw .env dump/model inspection, bulk copy, secret output or commits.
Preserve host DB/password/queue/origin values. Never deploy GH_TOKEN, Claude OAuth tokens, server
passwords or unused infrastructure/admin/model credentials into API/worker/browser environments.
Only explicitly public values may enter VITE_*; verify aliases rather than guessing.
OPEN_ROUTER_API_KEY is an existing alias; BETTERSTACK_DSN is not automatically a browser DSN.
CLOUDFLARE_S3_API is not proof of app bucket name/region/purpose. PADDLE_API_KEY does not establish
its separate webhook signing secret, client token or price IDs. Use authorized APIs/setup helpers
where possible; otherwise record missing NAMES and exact external actions, never request pasted
secrets. SERVER_V1_* describes the old host, not the deployment target.
No legal/source-use/accountant or Paddle merchant/product sign-off was supplied by the key list.
Track those launch obligations under existing issues; continue authorized beta work and collection.
Do not infer validity/approval from credentials or repeatedly ask the owner for their status.

START ACTUAL CONCURRENT WORK
Run THREE implementation-capable background workers in isolated worktrees, plus coordinator. Use the
actual Agent/session schema and explicit worktree isolation; launch all ready independent calls before
waiting for the first result. With only two ready, launch two; one is justified only by an actual lack
of independent ready work. Report worker IDs, issue, checkout, rm-<issue>-<slug>, base SHA, owned paths
and checks. Verify each new branch starts from current green origin/staging, not a tool's default branch.
Do not substitute read-only Explore/Plan workers, silent serial execution or uncontrolled nested teams.
If concurrency capability is unavailable, record the actual limitation without settings/permission bypass.

FIRST READY LANES
A. G-02b frontend: display already-persisted OCR/notes/equipment using optional v1 fields; safe text,
   source/confidence/inclusion-claim labels, honest missing/older/error states, reload and desktop/mobile
   positive acceptance. No second model call. Own report/i18n/interaction changes by reservation.
B. G-03 backend: deterministic grounded seller questions with stable IDs, reasons/evidence, deduplication,
   persistent versions/idempotency and old-report handling. Distinct from static checklist and #285.
   Reserve new contract/schema generation separately; after merge assign UI to the report owner.
C. Rental settings wiring (L-073/L-079), then real summaries/history API, then #282 Rynek UI, in bounded
   behavior PRs. Import-disabled prevents dispatch/fetch, not just summaries. Honor actual configured
   catalogue/cron/window/overlap/budget. API enforces auth/entitlements and truthful source/as-of/samples/
   freshness/coverage; UI renders stored data or meaningful unavailable/stale/partial states.
If one slice is blocked, assign another ready one, e.g. #371 deterministic clock regression, media
identity/lifecycle, approved source validation or live-runner cleanup. Do not make report display wait
for question fields it does not use or assign shared generated files to two writers.

COMPLETE ALL REQUIREMENTS; DO NOT STOP AFTER THESE THREE SLICES
Maintain requirement -> real issue/dependency/owner/PR/SHA/tests/provider/UI proof/remaining action:
- G-01 durable private bytes, populated manifest/stable image identity, retention/erasure and gallery.
- G-02 displayed OCR/equipment, trustworthy source associations and bounded live quality verification.
- G-03 generated/persisted AND displayed seller questions.
- G-04/#283 manual facts/drafts/uploads into common canonical report/audit/credit journey.
- OTO-01–04 ALL-727 fresh catalogue/bootstrap, complete partitions/pages, durable nightly last-24h
  NEW-offer windows, catch-up/restart/overlap, 90-elapsed-day cohort, immutable additions vs cohort
  histories, publication/freshness/coverage, comparables adapter and real #282 API/UI.
- LCTX-01–03 fresh source-verified hierarchy/observations/releases, trends/comparisons/ranks, experimental
  index, labelled context/report/agent consumers, sourced warning and SEPARATE adverse scenario.
- G-05/#284 persistent owned interior workflow with approved beta access/cost controls and real UI.
Retain #279 legal pages, #285 listing-writing, screener and remaining readiness work as separate
requirements after/alongside ready feature work. No scope removal to make the checklist look complete.

LIVE VALIDATION AND KNOWN DEFECTS
Read the ID4DACX follow-up: real vision-v2 processed 13 photos, cost USD 0.0005845, returned 5 items;
no plan drawing was present, so it is not positive OCR proof. Two references pointed at exterior image
11 instead of actual entrance image 10. Fix unambiguous per-image grounding/identity with fresh offline
regressions, preserve honest UI, do not blindly subtract one from every model index. Within the shared
allowance choose an actual readable-plan sample and record independent expected text/items, model/
prompt/commit/usage/cost and persisted/read-back/UI results. CI remains offline, provider canaries separate.
The old live_audit_check cleanup deletes other users' audits for the same listing. Fix ownership and
same-listing/concurrent/failure cleanup regression BEFORE reusing it. Do not delete existing records.
Otodom filters_verified currently defaults false: observe real date/filter/page semantics before source
activation. Do not invent a working filter or national completeness. BDL_BINDINGS is empty: select,
verify and encode genuine bindings under delegation, not fake fixtures passed off as published data.
L-072 incomplete-run rows, L-074 late discoveries and L-078 ranking/completeness limitations must survive
consumer integration. Resolve L-077 sample policy explicitly under delegated authority. Keep asking/deed,
new additions/cohort distinct; never claim active stock, achieved rents or per-ad price changes from
insert-once observations. Source gaps suppress unsupported statistics rather than manufacture values.

SHARED FILES, MERGES AND THE CONTINUOUS SCHEDULER
One writer per checkout/branch; exact owned files and one open migration PR at a time (audit head 0017).
Reserve central model/schema/router/types/i18n/routes/locks/privacy/deploy edits. Worker writes unique
docs/parallel-handoffs/RM-<issue>.md; integrator reconciles canonical docs in SAME feature PR, allocates
unused B/L IDs, regenerates artifacts and reruns required checks. Transfer branch ownership at a pushed
SHA before integration; no competing writer. Merge serially to staging under existing rules; verify CI.
Resolve BLOCKERS against OWNER-DECISIONS: settled policy/authority is not an owner dependency, while
actual provisioning/validation may remain agent work. Do not mark setup/gates complete from permission.
Routine README/CONTEXT/STATUS/LIMITATIONS conflicts queue integration, not a global stop. Record narrow
approved architecture/spec amendments rather than asking again or weakening unrelated rules.
After EVERY completion/blocker/merge recompute dependencies and immediately refill free worker slots.
Independent workers continue during another PR's review/CI while staging is green; red staging retains
stop-line rules. Keep actual active/idle/blocked/integration states. Never end at 'ready to dispatch'.

TESTING STRATEGY AND ISSUE CLOSURE
Prove new behavior through real Postgres/API/queue/engine and visible browser outcomes with named fake
providers, not only protocols/fakes/types. Verify current build URL/SHA. Do not reset another session's
4173/8003/5433 stack. Provision isolated ports/DB/Compose/build/output/coverage paths; concurrent test
processes must not delete one another's artifacts. Run repository pytest/invariants/migration/squawk/
make ci and frontend interaction/axe/visual/mobile/real-stack journey checks. Preserve finance/security
invariants and safe plain OCR text, tenant 404, export/erasure and late-worker deletion races.
Replace placeholder/known-absence tests with positive delivery tests as features ship; do not weaken
other assertions. Audit evidence was 115 backend and 129 browser passes with 25 expected skips, not
certification of newly added workflows. No test result carries forward to an untested integrated SHA.
POC reports may be inspected read-only as interim comparisons, as the owner authorized. Their outputs
are prototype results, not certified ground truth; no import/copy of reports/data/code/fixtures.
Compare fresh current outputs, explain discrepancies against spec/source, create original regression
cases. Build the evaluation harness now; as workflows finish, deliver the proper testing strategy and
expected-results template (source/input versions, base/adverse case, expected values/states, tolerances,
reviewer/date/evidence, discrepancy disposition). Populate reviewed expectations during testing and
distinguish agent verification from independent owner/expert review. Do not fabricate owner labels or
close accuracy certification from POC agreement. Track outstanding independent review without re-asking.
Reconcile stale #211/#378/#209/#314 and legacy #32/#33/#26/#27 text against actual code/Paddle policy.
Close only fulfilled acceptance. Transfer every unmet criterion to a linked real issue before splitting
closure; no fake closure of national coverage, payments, accuracy or legal gates. #371 is a ready small
clock fix, not permission to weaken limits/rely on reruns. Dependency cleanup is secondary to workflows.

BOUNDARIES, COMPLETION AND EXTERNAL ACTIONS
Python-only server, relational state Postgres, approved private-media exception, deterministic Decimal
financial math in deal_analyzer, RENT/share rejection, admin fee OPEX, JSON canonical and tenant 404.
No main promotion, live customer payments/refunds, production customer-data use, destructive DB/VPS
operations, force-push/protection bypass or additional security/account changes outside the specific
CSP/CI/beta authorizations. Preserve narrower PR/workflow rules and runtime permission systems. Do
not message sellers/other people. Record out-of-scope prerequisites and continue safe work; don't ask
for another blanket authorization or implement an unsafe workaround to satisfy 'no owner questions'.
Keep #210 sources, sourced CAPEX/base-exit behavior, #94 accuracy, #211 OCR quality, #220 Paddle/accountant,
#41 legal, #40 config, #15 ops, #35/#36/#37 load/connections/restore, #286 device/release evidence visible.
Existing permission enables action, not a claim that it passed. Legal/source/accountant/merchant sign-off,
unavailable resources/scopes, independent expected-result review, real-device review and manual main
promotion are exact tracked external actions; paid-launch gates remain closed until evidenced.
Continue until all required delivery is integrated or ALL safe independent work is truly exhausted.
Persist checkpoints/next commands for interruption, budget or unavailable tooling; don't call those
completion. Report actual USER behavior, issues/PRs/SHAs/tests and remaining external actions, not
promises of nonexistent background work or an invented readiness percentage.

Begin preflight, documentation commit and real parallel implementation now.
```
