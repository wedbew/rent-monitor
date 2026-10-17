# Parallel Claude delivery for the complete feature-gap batch

**Reviewed:** 2026-10-17 (Europe/Warsaw). **Status:** source-backed operating plan and local rule changes;
no agents, worktrees, paid sessions, remote issue writes or workflow dispatches were started.
All six product deliverables in the [feature-gap guide](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md)
remain required. Parallelism changes scheduling and integration, not scope or acceptance.

## 1. Findings: what currently prevents parallel delivery

| Confirmed source | Consequence |
|---|---|
| `scripts/dispatch_next.py:decide` returns idle when **any** Claude run is active, a PR is pending or a passing PR awaits merge | The automated dispatcher is globally serial. Giving it more ready issues does not create parallel lanes. |
| `.github/workflows/claude.yml` concurrency group is per issue/PR/run | Distinct issue jobs can be independently isolated on runners; this is different from dispatcher selection. A concurrency group is not a global worker-cap or file ownership check. |
| `docs/AUTONOMY.md` describes one issue at a time | Existing automation cannot be advertised as a parallel scheduler. Manual distinct issue triggers need coordinated ownership and capacity too. |
| `.agent/rules/delivery.md` requires disjoint `Files:` plus same-PR docs | Every feature otherwise collides on CONTEXT/STATUS/README/changelog even with independent code. Shared-doc integration must be assigned explicitly. |
| `blockers.md` single-checkout wording and automatic checkout cleanup after merge | Multiple local writers in the same directory would switch branches and stage each other's files. Separate branch names alone are not isolation. |
| `CONTEXT.md` has one long updated-history line; LIMITATIONS/BLOCKERS allocate sequential IDs | Independent additions create predictable text/ID conflicts, not necessarily product disagreements. |
| All contracts feed common report/OpenAPI/type generators, and all models feed one Alembic graph | These need short serialized integration windows even when feature modules run concurrently. |
| `.claude/skills/ticket-flow/SKILL.md` requires same-PR docs, merged dependencies and resume checkpoints | Worker completion must include an integration handoff; do not replace required docs with a later status PR or start consumers on imagined interfaces. |

Local CLI inspection: `/opt/homebrew/bin/claude`, **2.1.284**, supports `--worktree`, `--agents`,
`--background` and `--print` in its help. No model was invoked or auth verified. The five latest queried
Claude workflow runs were **skipped**, not successful executions. Existing B-021 records an older OAuth
failure; skipped runs do not resolve it. Check the read-only canary before relying on headless execution,
but lack of headless auth does not block this local planning work.

## 2. Recommended execution model

Use **three isolated feature workers plus one coordinator/integrator**. Each worker owns one small real
issue/branch at a time. Coordinator schedules prerequisites, reserves shared implementation files and
serializes integration/merges; it does not become the author of every feature's code. Keep total actual
processes within machine/account/CI capacity. Three is an initial operating recommendation, not measured
optimal throughput or a promise of 3× speedup.

For local coding, explicit isolated checkouts and independent Claude sessions are the easiest to audit.
Claude's [parallel-session guidance](https://academy.claude.com/courses/ai-native-sdlc-playbook/parallel-sessions-and-subagents)
distinguishes full isolated sessions from scoped subagents. Its
[subagent documentation](https://code.claude.com/docs/en/sub-agents) describes worktree isolation for
subagents. Use that only when a session is deliberately coordinating scoped helpers.

[Agent teams](https://code.claude.com/docs/en/agent-teams) are optional: currently experimental, disabled
by default, with independent teammate context and additional coordination/token overhead. They require
interactive spawning; the documented non-interactive `-p` behavior does not spawn teammates. Teams are
not an automatic substitute for assigned file ownership or checkout isolation. This plan does not edit
`.claude/settings.json` or enable the team flag.

**Existing Actions alternative:** independently assigned issue jobs already get isolated runner
checkouts. The dispatcher still serializes automatic selection; use a coordinated manual pilot or
implement the dispatcher upgrade in §8 before expecting unattended multi-lane delivery. Do not assume
the action's restricted tool allow-list enables nested agents just because the local CLI supports them.

## 3. Feature lanes and dependency waves

Keep a companion [readiness workstream](FEATURE-GAP-READINESS-COVERAGE-2026-10-17.md#6-required-companion-work--preserve-the-feature-batch)
for existing billing/settings/legal/quality/ops issues. Rotate tasks within the same capacity cap;
feature completion is not proof the release gates passed. This adds launch work, not a scope reduction
of any feature lane below.

The G/OTO/LCTX names below are proposal labels, not real GitHub issue numbers. Create/attach ready child
issues before running implementation. A feature proposal is much larger than one 30-minute/40-turn job.

| Lane | Independently owned feature work | Waits on | Shared edits to reserve |
|---|---|---|---|
| Media (G-01) | Pure validation/media manifest, media repository/API, report gallery | Approved storage/retention for persistence, merged media contract for consumers | DB models/migration; API registration; privacy export/erasure; CSP; gallery insertion in ReportView |
| Otodom (OTO-01–04) | Corpus/repos, verified search options, bootstrap, nightly/recovery and daily publications | Actual full catalogue, verified provider/window policy where used; merged corpus contracts | DB models/migration; job names; worker registration; settings/env; batch Compose; comparable cache/context |
| BDL (LCTX-01) | Territory/metric validation, ingestion seams, pure comparisons/ranks and publication | Selected metric/reference contracts, B-023 policy for activation | DB models/migration; market publication/schema; source client/settings; API registration |
| Evidence (G-02) | Item reconciliation and OCR persistence, then equipment UI | Stable media IDs; merged evidence contract; explicit financial boundary | Listing/VisionRecord/DealAnalysis; schema version/goldens; prompt; report insertion |
| Questions (G-03) | Deterministic missing-fact rules using existing approved report inputs; later evidence questions | Current result sufficient for basic questions; G-02 only for item/photo-specific questions | Pure question output contract; optional persistence/migration; report insertion; translations |
| Manual (G-04/#283) | Manual source identity, drafts/uploads, then UI journey | Media/input contracts and required-field/charge policy | Audit/listing identity, migrations, submission/credit paths, list/report adapters |
| Interior (G-05/#284) | Project/concept job model, provider seam, history/retry UI | Owned media and project/operation/cost policy; room evidence only where consumed | Migrations, job/budget/credit registries, provider/settings, API/routes |
| Market consumers (#21/#282, LCTX-03) | Native-level profiles, history/coverage UI, bounded audit context | Published Otodom/BDL contracts independently; index methodology for score activation | Market routes/OpenAPI, context seam, report insertion, translations/nav |

**Wave 0 — coordinator/contracts:** split issues, assign lanes and concrete files, confirm current verified
staging SHA and existing PR ownership. Merge small interface/version decisions and foundations needed by
the first consumers. Independent pure validation and requirements work can proceed meanwhile; record
which policy-blocked pieces are not ready. Do not merge all product policy into a giant prerequisite PR.

**Wave 1 — three workers:** media foundation; Otodom catalogue/corpus/search slice; BDL territory/metric
slice. These can overlap in time after interface ownership is explicit. Their DB migrations do **not**
overlap: one migration PR reservation at a time. Others continue pure modules, tests and injectable
adapters until their migration slot. Do not generate speculative competing Alembic heads.

**Wave 2 — rotate slots on completion:** media consumer/equipment; Otodom bootstrap → periodic capture;
BDL ingestion → metric publication. A free slot can implement deterministic seller questions from the
current report without waiting for richer equipment facts. Manual drafts consume the merged media seam.

**Wave 3 — rotate to consumers and operations:** gallery/equipment/report integration, manual journey,
interior projects/jobs, rental trends/Rynek, BDL profiles/audit context and approved location score. These
are all required deliverables; wave grouping does not remove interior/manual work. Stagger shared report,
route, schema and migration edits instead of making one developer wait for the whole previous feature.

No universal “BDL before Otodom,” “questions after all equipment,” or “all backend before any frontend”
gate: only the exact interface consumed must be merged. A contract-test-backed UI can use synthetic
fixtures after its contract lands; mock UI success must not be reported as integrated provider evidence.

## 4. Shared-file conflict inventory

This is the verified risk inventory, including files beyond the three named in the request. Ownership is
by concrete file/slice; logical feature independence alone does not prevent collisions.

| File or group | Why problematic | Rule / handling |
|---|---|---|
| `CONTEXT.md` | Same updated line, §4/5/8/9/10 touched by every lane; duplicate or contradictory status | Worker supplies exact section delta in unique handoff. Integrator updates once against latest state; concise newest date/issue summary, no re-append of whole history. Delivery claims link STATUS. |
| `docs/BLOCKERS.md` | Shared table, sequential B IDs, standing approvals mixed with dated incidents | Immediate issue-local blocker note and exact affected slices. Integrator assigns next B ID/preserves approval evidence. Do not re-open a resolved scope decision or block other lanes. Ambiguous policy is not merged as fact. |
| Root `README.md` | Every command/doc/stack addition hits same sections; status prose can drift | Queue factual command/link delta; fold into same feature PR. Combine disjoint rows. Verify command names in code; never copy another branch's not-yet-merged commands or old Phase-1 restriction. |
| `docs/STATUS.md` | Shared rows; worker may mark entire feature complete after a submodule test | Integrator records only actually proved level, revision and check/provider scope; partial slices remain explicit. No last-writer-wins status. |
| `docs/LIMITATIONS.md` | L IDs collide, resolved versus active states race | Temporary `RM-<issue>-L01` in handoff, canonical ID allocated on updated target; reconcile evidence/status and keep history. Update all references in that PR. |
| `CHANGELOG.md` | Same Unreleased categories; concurrent insertions | Preserve independent issue-tagged bullets; one category heading, never regenerate/rewrite the entire file. No invented ticket IDs. |
| `docs/BACKLOG.md`, `ROADMAP.md`, feature/BDL/Otodom plans | Duplicate issues, competing dependencies, accidental scope removal | Integrator retains all six deliverables and both data additions, links real child issues, preserves source-specific specs. Local ordering change is not a new global product priority. |
| `docs/BLUEPRINT.md`, `ENGINE-SPEC.md`, ADRs | Policy/architecture conflicts look like prose conflicts | Coordinator owns changes; true policy/deviation requires existing approval process. Resolve ordinary disjoint sections; do not decide finance, retention or scoring by choosing a hunk. |
| `.env.example`, `rm_core/settings.py` | Same settings model/names; docs/config inconsistency | Settings slice reserves both; use safe names/defaults and source comments, update mandatory run instructions. No real env reads, no duplicate names with different meanings. |
| `packages/rm_core/db/models.py`, `migrations/versions/` | Shared declarative models and Alembic head | Single schema owner per migration slice. Merge expand migration before the next migration PR. Defer model registration to that slice; never fix by weakening checks or silently merging heads. |
| `packages/rm_contracts/*`, problems/jobs/legal registries | New fields, error codes, task/tag names overlap | Small interface PR first; explicit registries reservation. Worker implementation consumes merged definitions, not an arbitrary broad `Any` contract. |
| `apps/deal_analyzer/{analysis,listing,vision}.py` | Equipment, manual identity and media evidence change same canonical types | One output-model owner per slice. Coordinate schema evolution and old-audit readers; other workers write pure helpers in owned new modules. |
| `docs/deal-analysis.schema.json`, schema baselines and engine goldens | Generated result schema; version/required-field compatibility | Generate from final models, bump when necessary, explain golden diffs. Never modify old frozen baselines to absorb conflicts. |
| `docs/openapi.json`, `frontend/api/*.generated.*` | Each endpoint changes global generated output | Regenerate on current integrated sources; run drift/runtime validation. Do not manually choose one branch's generated artifact. |
| `services/rm_api/app.py`, `rm_worker/app.py`, task/job exports | Independent features share registration points | Reserve a short registration integration slice; preserve both routes/tasks and test discoverability. |
| `services/rm_worker/context.py`, comparables/cache | Otodom freshness and BDL context alter the audit seam | Contract-first small slices, explicit per-input provenance; neither context silently overwrites another or changes finance. |
| `ReportView.tsx`, `AnalysisPage.tsx`, report parser/adapters | Gallery, equipment, questions and location section insert in same files | Owned new section components can proceed; one report integration writer mounts each and updates schema adapters. Test all sections together. |
| `frontend/routes.tsx`, `shell/navigation.ts`, typed i18n catalogs, `e2e/interactions.ts` | New pages/keys/controls use shared registries | Allocate exact namespace/registration writer. Keep all interactions exercised, no deleting entries to satisfy coverage. |
| `pyproject.toml`, `uv.lock`, `package.json`, `pnpm-lock.yaml` | Concurrent dependency edits and resolver output | Serialize dependency mutations; rerun package manager after source manifest merge, frozen-install/drift checks. No manual lockfile hunk merges. |
| `deploy/compose*.yml`, `Caddyfile`, worker budgets | Gallery CSP, batch workers and provider settings affect same runtime/resources | One runtime slice owner; preserve documented connection/memory/admission budgets and provider priority. No deployment from feature branches. |
| Privacy retention/export/erasure modules | Media/manual/interior add references with shared lifecycle | Agree lifetime/reference contract, reserve lifecycle edits and test late worker/erasure races. No guessed TTLs. |
| `.agent/*`, `CLAUDE.md`, skills, `.cursor` pointers, PR template, workflows/settings | Workers can change their own constraints or disagree on new instructions | Coordinator only; canonical pointers stay pointers. Current workflow/settings approvals remain. New rule prose does not auto-configure permissions or jobs. |
| Tests, Compose projects, ports, coverage/screenshots/artifacts, `data/api-samples` | Separate Git checkouts can still share external resources | Unique per-lane database/ports/project/output, capped containers and runners. Do not stop shared Docker or overwrite another lane's generated evidence. Visuals still use the pinned renderer. |

## 5. Shared docs must not stall feature implementation

The [parallel-work rule](../.agent/rules/parallel-work.md) makes this concrete:

1. Each worker edits its code/tests and **one unique** `docs/parallel-handoffs/RM-<issue>.md`, recording
   central-doc deltas and new blockers/limits immediately. A fresh limitation ID can wait; its factual
   evidence and affected scope cannot.
2. When the slice is tested, the draft PR is `integration pending`. Worker hands exclusive branch
   ownership to the integrator at a known SHA. The integrator commits actual CONTEXT/README/BLOCKERS/etc.
   changes to **that feature's branch**, merges updated staging and regenerates/checks it.
3. Before readiness, handoff state is reconciled, canonical docs are present in the same PR, real
   references/IDs are assigned, and checks rerun on the integrated revision. No later catch-all docs PR.
4. While a handoff waits, the worker can take another ready independent slice within the capacity cap.
   It cannot keep writing a branch the integrator owns. Code review/integration can lag implementation,
   but the ready/merge gate cannot silently skip required docs.

This replaces “every worker edits every shared document immediately” with “each feature's required
documentation is integrated into its own PR before readiness.” Single-worker behavior is unchanged.
The handoff template is durable input, not the authoritative delivery ledger. The protocol is manual
unless separately implemented checks enforce it.

Routine text overlaps, table ordering, new L/B IDs and generated-output drift are integration tasks.
Real semantic contradictions, unresolved owner policy, unmerged prerequisite interfaces and shared
implementation ownership collisions stop only the affected slice. Red staging still follows the existing
stop-line rule. Never use a documentation conflict as permission to reset another author's work or weaken
a gate; never use a global “ignore all conflicts” instruction.

## 6. Practical local launch procedure

Do **not** start workers from this dirty checkout yet. First commit/review the common rule/contract
foundation and merge it normally to verified staging; otherwise isolated sessions will not have these
instructions or untracked feature-gap docs. This is an integration prerequisite, not a request to discard
current edits. No changes here were committed, pushed or merged by this investigation.

Coordinator preparation:

- Pick three real ready child issues; record exact Files, merged dependency SHAs and resource names.
  Inspect existing PRs before allocation; feature code must not race an already assigned branch.
- Provision an ignored in-repo worktree per issue at the **same verified `origin/staging` SHA**, explicitly
  creating branch `rm-<issue>-<slug>`. Native `claude --worktree` is supported locally, but explicit Git
  provisioning makes branch naming and base reviewable. Never assume it starts from staging by default.
- Open `claude` in each assigned directory. Use normal inherited model/permissions; do not pass permission
  bypass flags. Worktrees share Git objects, not a working index; environment and service isolation still
  need separate provisioning. Do not copy `.env`/credentials into worktrees.
- Give all workers the prompt below with their own concrete issue/base/paths. Record running/handed-off/
  integration states on the coordinator's board; a task claim alone is not an enforced lease.
- Integrator handles one handed-off branch at a time and one staging merge/check cycle at a time. Clean
  up a worker checkout only after its worker has stopped and needed artifacts are preserved.

### Worker prompt template

```text
Implement issue #<real issue> in the assigned checkout and rm-<issue>-<slug> branch only.
Read CLAUDE.md, .agent/agents.md and .agent/rules/parallel-work.md first.
Lane: <media / otodom / bdl / questions / manual / interior / consumer>.
Base: <verified staging SHA>. Merged prerequisites: <issues + interface SHAs>.
Own only: <exact implementation/test paths>. Reserved shared files: <owner/slice>.
Runtime isolation: <database, ports, Compose project, artifacts>.
Integrator: <session/person>. Create docs/parallel-handoffs/RM-<issue>.md for every
required shared-doc change and any blocker/limitation. Do not edit another lane's files.
Implement/tests with injectable fakes inside settled policy; record blocked live evidence.
Ordinary shared-doc conflicts do not stop owned coding. Actual semantic/policy/contract
conflicts stop only the affected part; record the exact action and safe independent work.
Use the existing issue/PR/checkpoint workflow. Before PR readiness transfer exclusive
branch ownership at a pushed SHA; integrator must reconcile canonical docs in this PR,
regenerate shared outputs and rerun checks. Do not merge without the normal gates.
All six product deliverables and the Otodom/BDL expansions remain required.
```

### Integrator prompt template

```text
Read the parallel rule and all pending RM handoffs. Integrate only the branch explicitly
handed over to you; confirm worker stopped writing and record transfer SHA.
Merge latest verified staging into that branch, preserve all valid changes, reconcile
canonical docs in the same PR, assign fresh L/B IDs, and regenerate shared outputs.
Do not invent policy or modify frozen historical schemas. Return semantic questions to
the affected issue; keep independent lanes available. Run checks on the final integrated
head, confirm required CI/reviews/approvals, then merge to staging only. Verify staging CI
before the next integration. Hand branch ownership back explicitly if further edits are needed.
```

## 7. Near-term pilot and success criteria

First pilot: three small independent offline slices in media, Otodom and BDL, each using already approved
interfaces or narrowly specified pure modules. Do not start all broad proposals at once. Record wall time
for coding, integration, owner wait and rework. Verify no duplicate branch writer, shared-resource reset,
missing canonical docs, model/contract mismatch or changed financial invariant. Then rotate to the other
required features. No credible total-hour estimate follows from the existing audit alone.

Source/current-state checks performed on 17 October: reviewed rules, skills, workflow and dispatcher
source, generators and conflict paths; inspected local Claude version/help; queried current open PRs and
five recent Claude run outcomes. Open PRs observed include billing #366, session lifetime #363, workflow
#356, API contract tests #350 and settings #346, so they must be considered during path assignment.
Those PR states can change; recheck at launch. No credentials read and no paid/session canary started.

## 8. Optional automated multi-lane dispatcher: a separate implementation

Proposed issue: **`feat: dispatch independent Claude lanes with durable ownership and serialized integration`**.
This is not implemented by changing Markdown. Keep the existing serial dispatcher working until the
replacement is tested. `.github` changes require the existing human approval before merge.

Required behavior:

- Opt-in bounded `max_workers`, stable per-issue/lane ownership, concrete path/resource reservations,
  prerequisite checks against merged interfaces and verified staging; exclusions/actual owner blockers.
- A unique claim/lease store with atomic compare-and-set/expiry (explicit approved persistence), including
  recovery after dispatcher failure. GitHub labels or a Markdown file alone are not cross-process locks.
- Decisions distinguish running, coding complete, docs/integration pending, checks running, awaiting review,
  failed and owner-blocked per lane. A passing PR must not be auto-blocked/resumed, but also must not
  prevent dispatch of unrelated ready lanes. One PR per issue and resume checkpoints remain.
- Serial integration/merge ownership, revalidate current branch/head/dependencies before start and
  publication, no duplicate label/comment dispatch on concurrent triggers, no new code on stale reservations.
- No automatic force-push, permission bypass, retry storms or relaxation of staging/auth/money gates.
  Begin with dry-run logs, then explicit canary/pilot authorization and recorded results.

Tests belong with `tests/tooling/test_dispatch_next.py` or a separately reviewed dispatcher module:
two disjoint tasks fill free slots; overlapping paths/schema reservations exclude; approval-waiting lane
does not stall unrelated work; pending producer waits; red staging starts no new work; concurrent claim,
expired lease/restart, per-issue max retries, duplicate event and stale head are safe. Preserve current
serial-mode tests. Update AUTONOMY and workflow docs only with actual behavior evidence.

## 9. Changes prepared in this investigation

Added the canonical parallel-work rule and handoff template; wired it into agent discovery and the rules
that previously demanded immediate shared-doc edits or global checkout cleanup. Added this source audit,
lane/ownership matrix and launch prompts. These are reviewable local changes; no scheduler, CI settings,
approval gates, invariant checks or model configuration were changed. Actual parallel execution remains
unverified until the pilot. Documentation links/whitespace and relevant existing dispatcher tests are
checked separately; passing serial tests does not prove parallel dispatch works.
