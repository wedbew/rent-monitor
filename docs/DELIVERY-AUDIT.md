# Autonomous delivery audit

**Date:** 13 October 2026 (Europe/Warsaw) · **Tracking:** [RM-177](https://github.com/wedbew/rent-monitor/issues/177)
**Baseline:** GitHub `staging` at [`e9cdea7`](https://github.com/wedbew/rent-monitor/commit/e9cdea76b2e3723dfb35841bdac35362d6f57eb7), through PR #175; repository created 11 October, 18:27:58 Warsaw time. Metadata sampled around midnight on 12–13 October. Recommendations only: no application, scope, gate or agent-rule changes made.

## Verdict

**The project is producing code quickly, but sequencing work around components and governance rather than a usable product.** It is also undertaking a greenfield analytical-engine rebuild, not simply adding auth, payments and logging to the POC. After about 29.5 elapsed hours, 70 PRs have merged, but the central authenticated listing → queued analysis → persisted result journey is still absent. More commits or more agents will not resolve that sequencing problem by themselves.

“Testing has not started” needs qualification: substantial automated testing exists and runs in CI. What remains missing is validation of the complete product journey, real provider integrations, valuation accuracy and launch gates. Keep the money, tenancy and security safeguards; change the unit of delivery and how progress is measured.

## Evidence and timing

| Measurement | Observed | Interpretation |
|---|---:|---|
| Repository creation → latest baseline commit | 29 h 32 min | Calendar time, **not** agent working time |
| Commits reachable on GitHub `staging` | 71, including root | 70 squash merges; local `--all` contained 169 commits, including branch history, so it overstates shipped work |
| PRs | 75: 70 merged, 4 closed, 1 open | Open #120 is a dependency update; closed PRs include replaced stacks |
| Merged PR titles | 24 feat, 31 docs, 5 ci, 3 test, 3 chore, 2 fix, 2 refactor | Documentation is 44% of merges; title categories measure count, not time or value |
| Small documentation PRs | 15 added ≤10 lines | Each still traverses the issue/branch/PR/check/merge cycle |
| PR creation → merge | Median 1.88 min; nearest-rank p90 14.68 min; maximum 4.11 h | Most merge waits are short; a few gated items are long |
| Issues, refreshed sample | 101: 74 closed, 27 open | Excludes this audit issue. Issue numbers share GitHub's sequence with PRs; #176 does **not** mean 176 issues |
| Actions history | 737 runs: 477 success, 227 skipped, 27 failure, 4 cancelled, 2 unfinished | Includes all workflows; success does not necessarily mean code was implemented |
| CI / security workflows | 166 / 167; median completed elapsed 78 s / 38.5 s | Both run on PR updates **and** pushes after merge |
| Summed completed workflow elapsed | 5.71 h | Overlaps across workflows/jobs; neither billed runner-hours nor 5.71 h of serial delay |
| Headless `claude` workflow | 231 runs: 224 skipped, 2 success, 2 failure, 3 cancelled | Only seven non-skipped runs; continuous headless implementation is not demonstrated |
| Local audit verification | 879 tests collected; **617 engine/unit tests passed in 12.36 s** | Integration/migration suites were not rerun for this audit |

Sources: GitHub [PR history](https://github.com/wedbew/rent-monitor/pulls?q=is%3Apr), [issues](https://github.com/wedbew/rent-monitor/issues?q=is%3Aissue), [Actions](https://github.com/wedbew/rent-monitor/actions) and [staging history](https://github.com/wedbew/rent-monitor/commits/staging/); local `tests/`, `pyproject.toml` and workflow files. Snapshots were fetched sequentially: the initial issue sample still showed #167 open; the refresh showed it closed and newly created #176 open. Statistics are a dated baseline, not a live dashboard.

## Core issues, ranked

### 1. The scope changed from hardening a POC to rebuilding a product — highest impact

[ADR 0001](adr/0001-greenfield-rewrite.md) explicitly supersedes “wrap, don't rewrite” and forbids copying POC code, tests, fixtures or corpus. `CONTEXT.md` estimates ~23.8k lines in the POC deal engine, plus other analytical packages. Fresh market-data acquisition, new formulas/tests, billing/tax, ops, GDPR and a new frontend substantially expand the task. The [roadmap](ROADMAP.md) estimates 98–175 agent-days and a multi-week beta; these are uncalibrated planning estimates, not measured agent throughput, but clearly describe a different scope from a one-day SaaS wrapper.

**Recommendation:** retain the accepted rewrite decision unless the owner explicitly revisits it. Define the smallest validated launch scope and a separate expansion backlog. If reuse is reconsidered, assess individual pure modules against money, dependency and correctness constraints; do not silently copy the POC or assume it is production-safe.

### 2. Components are complete before the user journey — highest immediate impact

`rm_api.app._include_routers` registers health, auth, me, saved and admin; no audits or billing router. `rm_worker.app` registers retention, AI-budget, maintenance and email tasks; no audit task. The engine's `analyse_listing` consumes supplied `RentInput` and risk-free rate; production context acquisition is not wired into that journey. [#13](https://github.com/wedbew/rent-monitor/issues/13), [#14](https://github.com/wedbew/rent-monitor/issues/14) and comparable-store [#106](https://github.com/wedbew/rent-monitor/issues/106) remain open. The Docker smoke script checks health, readiness, worker presence and seeded plans, not a completed analysis.

Meanwhile, admin routes, privacy infrastructure, monitoring and multiple provider specifications have landed. These have value, but they do not demonstrate the primary product. Strict sequential steps in `.agent/agents.md` also coexist with parallel lanes in the roadmap; agents must interpret which prerequisite is actually required.

**Recommendation:** deliver one authenticated analysis through the real API, queue, Postgres and engine using explicit offline provider fakes first. Add one failure/credit-release path immediately. Then substitute real providers individually and add the smallest UI. Resolve phase/order ambiguity in a maintainer-approved rule update before parallel implementation.

### 3. Work fragmentation and shared-file churn — high impact

Fifteen tiny docs PRs illustrate the transaction overhead: [#66](https://github.com/wedbew/rent-monitor/pull/66) changes one line; [#162](https://github.com/wedbew/rent-monitor/pull/162), [#166](https://github.com/wedbew/rent-monitor/pull/166) and [#170](https://github.com/wedbew/rent-monitor/pull/170) separately record approval status. Layout was refactored twice (#62, #64). Draft stacks #163/#164/#168 were closed and replaced by #173/#174/#175 after auth merged. Shared `CONTEXT.md`/changelog edits also accompany branch synchronization, e.g. #108's merge comment. This proves churn, not its exact share of agent time.

**Recommendation:** update related status/docs in the implementation PR; combine routine status housekeeping into one coherent update. Split work by independently verifiable behavior rather than arbitrary line limits. Prefer prerequisites merged before dependent work; when stacking is useful, target the parent branch so review sees the incremental diff and retain the same PR through retargeting. Serialize migrations and shared contract edits.

### 4. Autonomy is configured, but sustained dispatch is unproven — high impact

The headless workflow is event-triggered, limited to 40 turns/30 minutes, and has per-issue concurrency control. It does not implement a dependency-aware “take the next ready ticket” loop or checkpoint/resume scheduler. Of 231 recorded runs, 224 skipped; the two failures include [38182957497](https://github.com/wedbew/rent-monitor/actions/runs/38182957497), whose log reports `is_error:true` and a subsequent commit-compare 404. The root cause is not established by that log. Even completed workflow status is not evidence of implementation output. Local/interactive agent activity is not captured by these counts.

**Recommendation:** prove one headless canary from ready issue to code diff, passing checks, merged PR and next-task handoff. Then use a single dispatcher with explicit dependencies, ownership and saved checkpoints. Record `ready → started → PR → checks green → approval → merged` timestamps. Do not scale agent count before this works.

### 5. Review waits matter, but are not the whole day's explanation — medium/high impact

Ledger [#108](https://github.com/wedbew/rent-monitor/pull/108) and AI budget #109 took 4.11/4.07 h from opening to merge; auth [#147](https://github.com/wedbew/rent-monitor/pull/147) took 3.49 h. Worker ops #158 and specification PRs #159/#160 took 2.45–2.76 h. These intervals include edits, checks and approval; they are **not measured pure owner idle time**. Auth has no submitted GitHub review, but its body records approval in chat. The rules require human approval for sensitive areas while the staging ruleset requires zero approving reviews: enforcement is partly procedural.

**Recommendation:** schedule two predictable review windows per working day. Present exact diffs, decisions, tests and risk evidence together; record the approved revision. Delegate routine execution after decisions are settled, while keeping auth, financial semantics, invariant changes and promotion gates. Any approval-policy change requires owner agreement.

### 6. Documentation volume has not produced reliable state — medium/high impact

At the baseline, README says “steps done: none” and points to engine foundation as next; `CONTEXT.md` lists implemented engine modules but later says `apps/` and invariant tests are missing and CI stays off. It still calls merged ledger/auth work pending. `BLOCKERS.md` lists merged approval items; new #176 is correcting that table. Its deferred vendor rows also contain earlier implementation descriptions. Stale instructions can trigger redundant work or false blockers in every subsequent session.

**Recommendation:** maintain one short authoritative delivery-state table with links to merged evidence, remaining integration and owner action. Keep architecture/specification separate from volatile status. Derive issue/PR state from GitHub; update only affected docs and remove contradictory historical status prose. Do not equate “issue closed” with “provider verified.”

### 7. Tests are strong at component level; realistic feedback is late — high product risk

Auth PR #147 reports 777 tests passing and explicitly says real Google/Resend were untested. Latest #175's required checks are green, including invariants and migrations. Local engine/unit verification passed here. Nevertheless, L-005/L-006 retain live listing/image assumptions; L-007 has placeholder CAPEX prices; #94 accuracy evaluation remains open. Green synthetic tests cannot establish realistic valuations or working vendor delivery.

**Recommendation:** develop with the product acceptance harness from the first slice. Keep PR tests offline and hermetic; run separately authorized sandbox/live contract checks outside PR CI. Start sourced CAPEX inputs, owner-labelled valuation samples and per-audit cost measurements early. Treat production-environment testing as a separate approved activity under current rules.

## Faster delivery flow

**Optimize for a completed, demonstrated journey per session; keep the existing safety gates.** The following changes are proposals, not permission to bypass current Phase 1, review, deployment or launch rules.

| Order | Deliverable / owner | Exit evidence |
|---|---|---|
| 0: one planning session | Owner + agent agree private-beta scope, representative city/listings, required vendor decisions, and phase/order changes | Short acceptance checklist; ready issues name dependencies, contracts, files and owner-only decisions |
| 1: next implementation priority | Authenticated audit API + queue + context adapter + engine + persistence | Offline Docker/API test: one signup grant, one reservation, completed canonical result; duplicate submission and failed job cannot double-charge or lose credits |
| 2: realistic validation | Replace each fake with its injectable provider; establish comparable coverage and sourced CAPEX | Authorized provider evidence, labelled accuracy cases, actual latency/cost; failures degrade/refund as designed |
| 3: usable private beta | Minimal UI: sign in, paste URL, progress/result, required account/privacy flows | Browser acceptance test against Docker; no frontend finance; obtain Phase 2 authorization before implementation |
| 4: paid behavior | Sandbox Checkout → signed webhook → entitlement → paid audit, including refund/invoice paths | Real Postgres duplicate/adverse-order tests plus authorized sandbox evidence; never present a sandbox pass as live verification |
| 5: release | Harden ops and complete the existing launch checklist | Measured backup/load/connection/auth gates, provider setup, accepted limitations, owner-approved promotion |

Start owner decisions and external setup alongside coding so they do not arrive at the end. Defer radar/screener, redesign, expanded admin and optional analytics from the **critical path** only with an explicit scope decision. Card-only or one-time-pass launch is an option to evaluate, not an authorized removal of BLIK/KSeF gates. A private local beta is a different milestone from a production paid launch.

For implementation, use one integration owner. If concurrent agents are approved, add at most two disjoint lanes with fixed contracts; serialize migration/shared-file changes. End every run with a durable checkpoint: completed behavior, exact checks, branch/PR, blocker and next command. A timed-out run resumes the existing issue/branch rather than spawning replacement work.

Use targeted lint/types/tests during edits. Run the required full checks on the final candidate; reuse results only for the identical revision. Propose CI path filters for docs-only changes and keep full checks on code changes and staging, with workflow approval first. Measure savings before redesigning CI: its 78-second median makes it a secondary bottleneck. Avoid running the full pipeline, pre-push suite, PR suite and post-merge suite repeatedly on unchanged code merely to demonstrate activity.

## Success measures and limits

Track **time to first completed analysis**, time to first sandbox purchase, acceptance journeys passing, blocked time by reason, rework and defects after merge. Proposed operating targets: one demonstrated journey improvement per implementation session; ≥70% of implementation effort on the current journey; review response within four working hours; no replacement PR without a technical reason; no owner blocker without a next action. These are targets to calibrate, not performance already achieved.

Do not promise production completion within a day. A thin offline journey should be the next milestone; estimate the remaining build only after that slice exposes integration costs. Existing beta measurement, accuracy, legal/accounting, provider activation and release-gate requirements impose separate elapsed time. The audit cannot allocate the 29.5 hours precisely: no comprehensive local-agent session/token/cost logs were inspected, workflow elapsed overlaps, PR wait includes rework, and issue age includes time before work starts.

**Method:** `gh issue/pr list --state all --limit 500`; paginated GitHub staging commits and Actions runs; representative PR bodies/comments/checks and one failed-agent log; current staging ruleset; tracked source/tests/docs and local collection/engine/unit runs. No secrets, production systems or external integration calls were accessed. GitHub metadata access and local offline tests provide the evidence; this is a delivery-process audit, not a full security or code-correctness review.
