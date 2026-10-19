# Claude kickoff: execute the complete feature-gap batch in parallel

> **Latest resume point (2026-10-19, after #390):**
> [delivery prompt](CLAUDE-DELIVERY-PROMPT-2026-10-19.md) and [tested audit](DELIVERY-AUDIT-2026-10-19.md).

> **Resume after the first three merges (2026-10-18):** use
> [the completion prompt](CLAUDE-FEATURE-GAP-FINISH-PROMPT.md) and
> [the source/GitHub re-verification](FEATURE-GAP-REVERIFICATION-2026-10-18.md).
> This original kickoff remains scope history; the merged foundations do not complete the batch.

Foundation issue: [#374](https://github.com/wedbew/rent-monitor/issues/374). Start this prompt from the
merged, updated `staging` checkout after its checks are verified. The foundation issue publishes the
plans/protocol; it is not the implementation issue for every feature. Current GitHub state and source
override historical audit snapshots when deciding what remains.

Copy the prompt below into a new interactive Claude Code session. It authorizes implementation and
issue/PR coordination for this batch; it does not start a session by being stored in the repository.

```text
Execute the full RentMonitor feature-gap batch. Act as coordinator/integrator and use up to THREE
implementation workers in parallel, each in an isolated checkout/worktree with its own branch/index.
Use the configured model and normal permissions. Do not run several Git writers in this directory.

First read:
- CLAUDE.md and .agent/agents.md
- .agent/rules/parallel-work.md, delivery.md, blockers.md and pull-requests.md
- docs/FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md
- docs/OTODOM-NIGHTLY-IMPORT.md
- docs/BDL-LOCATION-CONTEXT-CONTRACT.md
- docs/PARALLEL-FEATURE-DELIVERY.md
- docs/FEATURE-GAP-READINESS-COVERAGE-2026-10-17.md
- docs/STATUS.md, docs/BLOCKERS.md, docs/LIMITATIONS.md and applicable blueprint/ENGINE-SPEC sections

Do not stop at planning. Inspect current staging/GitHub state, create or resume real child issues,
assign ready slices and begin implementing the first independent slices. Do not duplicate existing
issues, branches, PRs or completed work. Foundation #374 is not a substitute for those child issues.

ALL SIX deliverables remain required:
1. G-01 durable private media and report gallery, starting with URL audits.
2. G-02 factual equipment/image evidence and persisted floor-plan OCR, informational before pricing.
3. G-03 grounded seller questions and durable versions, distinct from the listing-writing assistant.
4. #283 / G-04 manual property facts/uploads through the common audit pipeline and canonical report.
5. #282 Rynek, including both expansions:
   - OTO-01–04: ALL owner-verified 727 Otodom locations, complete rental bootstrap, offer-level
     Postgres corpus, nightly last-24-hours new-offer capture, gap recovery, 90-day age eligibility,
     daily histories/trends and real coverage/freshness. Existing offers remain immutable under
     the approved insert-once policy; do not claim verified active stock or per-ad price changes.
   - LCTX-01–03: GUS BDL gmina/powiat/wojewodztwo hierarchy, observations/trends/comparisons/ranks,
     separately approved explainable locality index, bounded audit/agent fact pack and report UI.
6. #284 / G-05 persistent interior projects and concept/image operations with progress/retry/history.
Do not remove/defer any deliverable merely to simplify scheduling. Dependencies determine sequence.
Listing-writing #285 and remaining readiness work stay separately tracked; they are not seller questions.

Preflight and scheduling:
- Verify the current staging head/checks, dirty-tree ownership, existing open PRs and recorded decisions.
- Create/update small real issues under the existing parents with exact Files, acceptance tests,
  Priority and a plain single-line Depends on: list. G/OTO/LCTX are proposal labels, not ticket IDs.
- Record lane, branch rm-<issue>-<slug>, base SHA, owned paths, contract SHAs, reserved shared files,
  database/ports/Compose project and output directories before dispatch.
- Start independent MEDIA, OTODOM and BDL slices where their precise inputs/policy are settled.
  Pure validators, typed contracts and offline fakes can proceed without live provider credentials.
- Rotate free slots into equipment, basic deterministic questions, manual, interior and consumers
  as their merged interfaces permit. Do not make all questions wait for all equipment, or Otodom
  wait for acceptance of the BDL composite. No production consumer builds on a guessed interface.
- Use Claude's isolated worker/subagent/session capabilities actually available in this environment.
  Do not silently enable experimental teams, bypass permissions or claim background workers exist
  unless they actually started. The current GitHub dispatcher is serial; labels alone do not enable
  a parallel scheduler. Reconcile headless auth/capacity before relying on Actions execution.

Shared files and integration:
- Feature workers own disjoint implementation/test files. Reserve shared model/registration/schema,
  translations/routes, dependency/deploy/privacy changes explicitly. One migration PR at a time.
- Workers immediately record canonical-doc deltas/blockers/limits in their own
  docs/parallel-handoffs/RM-<issue>.md using TEMPLATE.md and continue their owned work.
  CONTEXT, STATUS, BLOCKERS, LIMITATIONS, README, CHANGELOG, roadmap/backlog collisions are normal
  integration tasks, not reasons to stop independent coding or ask for repeated scope approval.
- Use issue-local provisional B/L keys; assign next unused canonical IDs against updated staging.
- Transfer exclusive branch ownership at a pushed SHA to the integrator before reconciliation.
  Integrator merges verified staging into THAT feature branch, completes canonical docs in the
  SAME PR, regenerates schemas/types/locks, reruns checks and resolves the handoff before readiness.
- Merge one PR at a time into staging after required checks/reviews/approvals, then verify staging CI.
  Never force-push, bypass protection, weaken tests or switch/clean another worker's checkout.

Boundaries and evidence:
- Keep Python-only server, Postgres state, Decimal money and deterministic finance in deal_analyzer.
  Preserve RENT/share rejection, asking/deed separation, admin-fee OPEX and JSON canonicality.
- POC repositories are read-only requirements sources; never copy/import their code/data/fixtures.
- Never read real env/credentials. No live payments, paid provider/load runs, production deployment,
  destructive DB operations, external publication or security-setting changes without applicable
  existing authorization. Do not message sellers or other people.
- Do not invent prices, retention, storage architecture, source coverage or ranking weights to
  avoid a real decision. Record the exact blocker for only the affected slice; continue other ready work.
- Preserve the recorded backend standing authorization and all remaining approval boundaries.
- Keep readiness work visible: billing/settings/legal pages, sourced CAPEX/risk-free rate, accuracy,
  CI enforcement, real-provider checks and memory/connection/restore drills are not solved by features.
- Use the repository ticket-flow/PR template, offline regression/concurrency/invariant checks,
  make ci and relevant browser/migration checks; monitor PR CI and fix failures on the same branch.
  Distinguish implementation, offline integration, provider verification and launch evidence in STATUS.

Continue issue-by-issue until the batch is delivered or all currently safe independent work is exhausted.
At checkpoints report actual worker/issue/branch states, completed behavior, exact checks, real blockers,
shared integration ownership and the next executable step. Do not declare the batch complete from
documents, mocked screenshots, a passing serial dispatcher test or one-city provider evidence.
```
