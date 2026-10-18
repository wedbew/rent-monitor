# Claude resume prompt: complete the feature batch and remaining safe project work

Copy the block into Claude Code in this repository. This resumes merged foundations; it does not
start agents by itself. Recheck current state rather than treating the dated audit SHA as a fixed base.

**Parallel-launch review (2026-10-18):** local `claude --version` reports 2.1.302; its help exposes
worktree and background-session support. Official [subagent documentation](https://code.claude.com/docs/en/sub-agents)
describes background concurrency and worktree isolation. The instructions below require real concurrent
launches and launch evidence; this review did not start workers or verify session permissions/authentication.
The existing GitHub dispatcher remains serial. No measured completion-time speedup is claimed.

```text
Act as RentMonitor's coordinator/integrator. Finish the complete owner-requested feature-gap batch,
then continue remaining safe product/readiness work. Use up to THREE implementation workers in
parallel, each with an isolated checkout, branch, index and explicit path ownership. You coordinate
integration; do not create an unlimited extra fleet. Use the configured model and normal permissions.

ACTUALLY START CONCURRENT WORK
Complete the documentation bootstrap below before launching implementation workers.
Use the session's native Agent tool for implementation-capable background workers with explicit
worktree isolation. Consult its actual schema: request background execution if supported; otherwise
verify that the mode runs concurrently. Do not use read-only Explore/Plan workers for implementation.
Dispatch THREE ready independent slices before waiting for any one result; with only two ready,
dispatch two. One worker is acceptable only when you identify why no second slice is ready.
Do not silently substitute sequential foreground calls. If unavailable, report the exact capability
or permission blocker; do not change settings or claim workers started.

For each launch report actual task/session ID, checkout, issue branch, base SHA and owned files.
Check new worktrees: their default base may differ from staging. Before editing, create the required
rm-<issue>-<slug> branch from verified origin/staging in that worker's checkout. Keep paths within
the authorized workspace. A running worker must not edit the coordinator's checkout.

READ FIRST
CLAUDE.md, .agent/agents.md, applicable .agent/rules (especially parallel-work, delivery, blockers,
pull-requests, frontend, architecture, poc-reference), CONTEXT.md, docs/STATUS.md, docs/BLOCKERS.md,
docs/LIMITATIONS.md, docs/PRE-DEPLOYMENT.md and relevant blueprint/ENGINE-SPEC sections.
Then read:
- docs/FEATURE-GAP-REVERIFICATION-2026-10-18.md
- docs/FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md
- docs/OTODOM-NIGHTLY-IMPORT.md
- docs/BDL-LOCATION-CONTEXT-CONTRACT.md
- docs/PARALLEL-FEATURE-DELIVERY.md
- docs/FEATURE-GAP-READINESS-COVERAGE-2026-10-17.md (historical, refresh GitHub state)
- reconciled handoffs RM-376, RM-377, RM-378.

START FROM REALITY
The audit checked staging a123aeb, green CI, no open PRs. Fetch/recheck now. Verify dirty-file owners,
worktree ownership and actual available worker capabilities before assigning writers. Never reset,
clean, switch or delete someone else's active checkout. Existing worker worktrees are historical
until ownership is confirmed; create new issue branches from current staging when appropriate.
No secret/env reads, unsafe permission bypass or experimental-team configuration changes.

FIRST COMMIT THE PENDING DOCUMENTATION
The owner explicitly requests committing the currently unstaged documentation before implementation
dispatch. Inspect git status and diffs, including untracked documents. The expected files are:
- CONTEXT.md
- EXECUTION-SUMMARY.md
- docs/CLAUDE-FEATURE-GAP-KICKOFF.md
- docs/CLAUDE-FEATURE-GAP-FINISH-PROMPT.md
- docs/FEATURE-GAP-REVERIFICATION-2026-10-18.md
- docs/FEATURE-GAP-READINESS-COVERAGE-2026-10-17.md
- docs/parallel-handoffs/EXECUTION-CHECKPOINT-2026-10-17.md
- docs/parallel-handoffs/WORKER-1-MEDIA-STARTUP.md
- docs/parallel-handoffs/WORKER-2-OTODOM-STARTUP.md
- docs/parallel-handoffs/WORKER-3-BDL-STARTUP.md

If these changes are already committed/merged, verify that and skip duplicate work. Otherwise create
or resume the appropriate real documentation issue and rm-<issue>-<slug> branch, preserving these
pending changes. Stage these reviewed files explicitly by name, never git add -A or unrelated dirty
files. Commit with docs(RM-<issue>): <subject>; check links/diff and required repository checks, open
the documentation PR to staging and integrate it under the existing PR/approval rules. Do not commit
or push directly to staging. This is requested audit/execution-plan documentation, not a substitute
for same-PR feature documentation. Record the commit/PR and resulting verified staging SHA.

Linked worktrees do not inherit uncommitted files. Start implementation workers from staging after
this documentation PR merges and its checks pass, so every worktree receives the same instructions.
Prepare assignments while it runs. If documentation integration hits an external blocker, checkpoint
it explicitly; do not claim the commit/merge occurred or dispatch workers from an undocumented base.

Already merged: media metadata/GET route+0014 (#381), Otodom types/protocol+test fake (#379), BDL
types/pure logic (#380), settings (#346), credits/checkout (#366), API fuzz (#350), session lifetime
(#363), pinned visual CI (#356). Verify before reusing; do not reimplement these slices.
Still absent at the audit: private media bytes/population/gallery, equipment and durable OCR,
seller-question versions, manual audits/uploads, production rental corpus/nightly/history, BDL
data/persistence/API/context/index, working Rynek and interior workflows.

Do not treat EXECUTION-SUMMARY.md, old execution checkpoint or worker startup guides as current
work orders. They were FIRST-SLICE assignments. Their blanket claim that B-023 was resolved is
incorrect. The canonical blocker row and exact recorded owner decisions control activation.

FULL DELIVERY CONTRACT — KEEP EVERY ROW
Maintain a durable requirement-to-issue matrix in the coordinator's issue-local checkpoint/handoff:
requirement, existing/new issue, dependency, implementation owner, real PR/merged SHA, API/worker/DB
proof, browser proof, provider proof if required, remaining owner action and next executable slice.
Use implemented / integrated offline / provider-verified / launch-ready per delivery.md. Never
invent an overall percentage or count a contract/test fake as a complete workflow.

Required batch:
1. G-01: durable private URL-audit media, stable IDs, binary serving and retention/erasure, photos
   and floor plans displayed in report gallery; explicit missing/expired/rejected/partial states.
2. G-02: factual equipment observations/inclusion distinctions and persisted floor-plan OCR with
   source media IDs, confidence/provenance; versioned canonical report and reader/UI. Existing
   vision is already wired: preserve its evidence instead of rebuilding it. No new finance policy.
3. G-03: grounded deterministic seller questions from known gaps/conflicts/evidence; stable IDs,
   reasons, deduplication, durable versions, report UI. Optional paid narrative is separate. A static
   warning checklist does not meet this acceptance; listing-writing #285 is a different feature.
4. #283/G-04: manual facts/drafts/identity/uploads into common pipeline and canonical report,
   validated fields, unknown vs zero, secure media lifecycle, fractional rejection, tenant isolation,
   idempotent retries/credit behavior and working browser submission/reload flow.
5. #282/Rynek with BOTH data lanes:
   OTO-01–04: production Postgres immutable offer corpus and run/checkpoint store; actual verified
   ALL-727-location catalogue and complete paginated/partitioned bootstrap; batch nightly last-24h
   NEW-offer capture with durable windows, catch-up for missed days and restart/overlap protection;
   90-elapsed-day eligibility; published daily additions vs rolling-cohort histories, coverage,
   sample sizes, gaps and freshness; comparables/API adapters and real market UI.
   Preserve insert-once policy. Do not refresh old ads or claim active stock, achieved rent or
   per-ad price-change tracking. Five-page monthly on-demand sidecars are not national coverage.
   LCTX-01–03: versioned gmina/powiat/wojewodztwo hierarchy/crosswalk, reviewed observations,
   source/time/grain/provenance, resumable quota-aware ingestion, trends/comparisons/ranks and
   fail-closed publication; approved explainable versioned locality index; market/report consumers
   and bounded agent context. Label powiat proxies. No property-grade substitution or finance
   multiplier. Unapproved composite policy must not block independently approved rental delivery.
6. #284/G-05: persistent owned interior projects and approved concept/image operations one at a
   time, original/generated distinction, job progress/error/retry/history, budget/entitlement and
   idempotency, usable browser flow. Generated images are never evidence of existing equipment.

ISSUE REPAIR, NOT DUPLICATION
Inspect live issue bodies, comments, branches and checkpoints first. #377 closed despite promised
persistence/catalogue/integration tests remaining absent; record and transfer unmet acceptance
into linked children, or reopen if retaining original acceptance. #376 closed metadata only; do
not mark gallery done. #378 was open after #380 merged; reconcile actual phase-1 evidence and
remaining database/policy acceptance. Update stale #211 text claiming vision is not wired.
Expand #48/#49/#209/#16/#21/#282 for corpus/nightly/history and multi-level BDL consumers. #283 and
#284 scope is settled: ask only precise unresolved product/cost policies, never whether to include
them. Use proposed follow-ups in the re-verification as drafts, not existing issue numbers.
Each executable issue has one testable behavior, exact Files, plain Depends on: list, named tests
and only its real policy dependencies. Broader issues remain parents. Do not close acceptance you
did not deliver. Do not manufacture a new umbrella to hide an unfinished original.

CONTINUOUS SCHEDULER — THIS IS THE MAIN DIFFERENCE FROM THE FIRST RUN
1. Build the matrix, find ready slices, create/resume issues and dispatch actual workers immediately.
   Initial lanes: REPORT evidence/deterministic questions/media follow-through; RENTAL production
   corpus; BDL persistence/ingestion. Verify exact disjoint files, reserve shared report contracts
   and first rental/next BDL migration slots. If a lane is policy-blocked, use its slot for another
   ready slice. A plan or three worker startup files are not execution.
   Keep report-schema ownership in one slice; assign questions or OCR to another worker only after
   their exact shared contracts merge. While RENTAL owns the migration slot, BDL owns disjoint source
   adapter/validation/replay tests against merged contracts, then takes the next database slice.
   Do not give both workers db/models.py or two open migration PRs.
2. At every worker completion, inspect behavior/tests and reconcile its issue acceptance. Transfer
   exclusive branch ownership at a pushed SHA, integrate same-PR docs/generated artifacts and
   run required checks. Fix failures; merge serially into staging under standing authorization
   and current PR rules. Verify staging CI before dependent delivery.
3. IMMEDIATELY recompute dependencies and assign the next ready slice. Rotate workers into gallery,
   manual, interior, rental scheduler/history, BDL consumers and Rynek UI as interfaces merge.
   Do not finish the session because the first three workers completed or one migration is waiting.
   Launch a newly ready slice while another PR is in review/CI if staging remains verified green.
   Keep a coordinator ledger of active/idle/blocked workers and queued integration. Verify results
   from completion notifications/tool output; recover failed workers from checkpoints. Do not poll
   in a tight loop or relaunch a live writer. Monitor CPU/RAM/Docker and reduce concurrent expensive
   full-suite/browser runs if they contend; parallelize coding and focused tests, preserve full gates.
4. Repeat until every batch row has actual acceptance evidence, or ALL remaining safe work has
   a specific external/owner prerequisite. Audit for overlooked independent slices before declaring
   exhaustion. A blocked source activation does not block offline Postgres ingestion tests; a
   blocked composite does not block direct-fact plumbing. Do not build consumers on guessed APIs.
5. Then process the separate remaining product/readiness backlog using the same capacity. Retain
   #279 legal pages, #285 listing assistant and screener as distinct requirements; inspect actual
   scope/contracts and approvals first. Continue safe risk-free/accuracy/ops/test work where settled.
   Do not declare the whole project done when the feature batch alone is integrated.

SHARED FILES MUST NOT STALL INDEPENDENT WORK
Record writer, paths, branch/base SHA, merged contract SHA, migration/central-file reservation,
test DB/container/ports and output paths. One Git writer per checkout; one open migration PR at
a time. Serialize model/router/schema/type/lock/deploy/privacy edits by reservation. Use current
flat package layout, not stale repositories/ or routes/ directory sketches.
Workers put precise shared-doc deltas and provisional B/L entries in their unique
docs/parallel-handoffs/RM-<issue>.md. They continue owned work. Integrator updates CONTEXT, STATUS,
BLOCKERS, LIMITATIONS, README/CHANGELOG/blueprint/roadmap as applicable IN THE SAME FEATURE PR,
allocates unused canonical IDs, regenerates OpenAPI/report schemas/frontend types and fixtures,
reruns checks and resolves the handoff before readiness. Normal doc conflicts are integration
tasks; never weaken/remove agent rules or omit required docs to avoid them.

DECISIONS AND AUTHORIZATION
Do not ask again for all 727 locations, BDL reference reading, or inclusion of any required batch
feature. They are approved scope. B-023 still needs actual catalogue identification and reviewed
metric IDs/units/grains, attribution/terms, thresholds/cohorts/index/fiscal policy. Media storage
and retention, manual required fields/charges, interior provider/operation costs also need exact
recorded choices where unresolved. Search existing decisions before asking.
For a real unresolved choice prepare a concrete recommendation/options and affected acceptance,
record the narrow blocker, ask once and keep unrelated workers progressing. Time elapsed is not
approval. Do not silently enable a guessed policy; offline fakes use explicitly test-only values.
Preserve existing staging backend merge authorization, frontend scope and all narrower PR rules.
No promotion to main, production/customer DB, live purchases/payments, paid/unapproved provider
runs, destructive operations, force pushes, protection bypass, workflow/security-setting changes
without applicable approval, or messages to sellers/other people. Do not read real env/credentials.
POCs are read-only requirements references: never copy/import their code, data or fixtures.

VERIFICATION AND STOP CONDITIONS
Python-only server/Postgres state; deterministic Decimal finance in deal_analyzer. Preserve all
invariants (RENT rejection, asking/deed separation, admin fee OPEX, fractional rejection, JSON
canonical). Test new persistence on real Postgres, not SQLite or only in-memory fakes. Prove restart,
idempotency/concurrency, ownership/404, failed/empty/stale paths, ledger/budget and erasure as relevant.
Required uv pytest/migration/squawk/make ci and generated artifact checks apply. Frontend changes
follow frontend.md: real API/queue/DB journeys with named fake providers, reload persistence,
interaction registration, accessibility, visual scenarios and green required CI on integrated SHA.
Never relabel offline tests as live-source validation or a generated type as delivered UI.

Readiness work stays explicit: #210 risk-free, CAPEX/exit-anchor sources/policy, #94 labelled accuracy,
#211 live vision quality/cost, #220/#43 Paddle/accounting and B-024 CSP choice, #41/B-012 legal,
#40 real configuration, #15 ops, #35 memory, #36 connections, #37 timed restore, #286 release evidence
and current required CI enforcement. Re-query state; historical open-PR lists are not current work.
Do not claim production-ready until PRE-DEPLOYMENT/release gates have their own evidence/approval.

Continue autonomously through ready issues, failures and follow-up waves. At meaningful checkpoints
report completed USER behavior, actual workers/issues/PRs/SHAs/tests, exact owner blockers and next
executable steps. Post repository-required issue checkpoints. For a forced session/budget/tool stop,
persist enough precise state and next commands to resume without re-auditing everything; label it
an interrupted checkpoint, not completion. No claim that unstarted background workers will continue.
Final completion must enumerate proof for every delivery row and remaining external launch gates.
If safe work is exhausted, provide a consolidated exact decision/action list and resumable next
commands. Never stop merely with another roadmap, contracts-only wave or "ready to dispatch" summary.

Begin preflight and implementation now.
```
