# Rule: parallel feature work uses isolated writers and same-PR integration

Applies when the owner requests parallel agents/sessions or a coordinator explicitly assigns independent
workers. It governs **edit timing and ownership** for shared files; it does not waive documentation,
acceptance, security, approval or testing requirements. All six feature-gap deliverables remain in scope.
Operating guide and conflict inventory: `docs/PARALLEL-FEATURE-DELIVERY.md`.

## 1. Isolation and assignment

- One active writer per checkout and per feature branch. Never run independent Git writers in one working
  directory, even when their code paths differ: index, branch, generated files and test output are shared.
- Use assigned isolated checkouts/runners. Work only in your assigned checkout. A coordinator may provision
  worktrees under the repository's ignored `.claude/worktrees/` within existing filesystem permissions;
  external checkout locations need existing owner authorization. Never alter another worker's checkout,
  index, environment, branch, running server or uncommitted work. This is the narrow parallel-work exception
  to the single-checkout wording in `blockers.md`; no worktree is automatically created by this rule.
- Before dispatch, record issue, branch, base SHA, lane, exact owned implementation/test paths, merged
  prerequisite interfaces, shared-file reservations, test database/ports/output directories and next task.
  Real GitHub issue numbers are required; G/OTO/LCTX labels are planning references, not issues.
- Start with three feature workers and one coordinator/integrator; increase only with measured capacity.
  Do not nest uncontrolled teams. A prompt or ownership table is coordination, not an enforced file lock.

## 2. Shared-file ownership

Workers own disjoint implementation files. The **integrator owns central documentation reconciliation**:
`CONTEXT.md`, `docs/STATUS.md`, `docs/BLOCKERS.md`, `docs/LIMITATIONS.md`, root `README.md`,
`CHANGELOG.md`, `docs/BACKLOG.md`, `docs/ROADMAP.md` and the shared feature plans.

Workers record required doc changes and new blockers/limits immediately in
`docs/parallel-handoffs/RM-<issue>.md` using `TEMPLATE.md`; they may continue their owned work. The unique
handoff is provisional input, not a replacement for canonical docs. For each required central edit name the
section and exact factual delta, evidence, desired status and decisions still unknown. Do not write
“not affected” just because the integrator owns the file. No secrets/real personal data in handoffs.

Number collisions are routine integration: use issue-scoped temporary keys such as `RM-123-L01`/`B01` in
the handoff. The integrator assigns the next unused canonical L/B ID from the updated target branch and
updates references before readiness. Existing canonical IDs are never renumbered or reused.

Shared **code/contracts**, unlike prose, need explicit reservations: `db/models.py`, migrations,
settings/problem/job/legal registries, API/worker registration, engine result/schema version, report
adapter, translations, route/nav/interaction registries, dependency manifests/locks and deploy files.
Only the assigned slice owner edits a reserved file. Do not build against an assumed new contract.
Unmerged producers may be explored read-only; production consumers wait for merged interfaces.

## 3. Same-PR integration and regeneration

1. Worker tests its slice, writes the handoff and marks the draft PR `integration pending`. Central doc
   edits may be deferred during authoring, **never beyond PR readiness/merge**. One PR per issue remains.
2. Transfer exclusive branch ownership to the integrator at a named pushed SHA; the worker stops writing
   that branch. It may start another assigned issue in a different isolated checkout, subject to capacity.
3. Integrator merges latest verified `staging` into that same branch (no force-push), preserves unrelated
   changes and folds the handoff into canonical docs **in the same PR as the feature**. Keep the handoff as
   provenance, labelled reconciled with sections/IDs; do not leave unresolved handoffs on a ready PR.
4. Regenerate schemas, OpenAPI, frontend types/fixtures and lockfiles from final merged sources with the
   project's generators/package manager. Never hand-merge generated JSON, copy lockfile hunks or update
   frozen historical schemas to hide a breaking change. New mandatory fields still need version handling.
5. Run relevant checks again on the integrated SHA, then all required repository checks. A prior worker
   run is not evidence for a later integrated head. CI green alone is not proof a handoff was reconciled.
6. Merge only one PR at a time into `staging`, with existing checks/reviews/approvals. Verify the resulting
   staging CI before integrating the next merge. Worker branch updates happen only after ownership is
   handed back explicitly; nobody switches or cleans up another agent's checkout.

Do not create a later docs-only PR to excuse missing feature docs. Do not use `ours`/`theirs`, reset/clean,
force-push, skip checks or delete another worker's changes as a generic conflict remedy.

## 4. Continue versus stop

**Routine; continue owned work and queue integration:** two docs add rows in the same section; README
table order; CONTEXT date/header churn; provisional L/B number collisions; a reserved central-doc file;
a newer target commit; regenerable output drift. Re-read current sources and preserve both valid deltas.
Missing live credentials block live verification, not already-authorized offline implementation with fakes.

**Stop the affected slice, record exact reason, work elsewhere if assigned:** unresolved money/auth/tenant/
retention/product policy; genuine blueprint contradiction; incompatible contract meanings; pending
required producer interface; actual code-path ownership collision; unsafe schema/data operation; failed
invariants or checks requiring weakened protections. Red/unverified staging retains the existing stop-line
rule; this protocol does not override it. Do not invent owner policy to avoid a stop.

A blocker on one feature is not a new dependency of unrelated lanes. Record affected issues precisely;
do not mark the whole batch blocked. An open PR awaiting review does not, by policy, prohibit independent
work, although the **current dispatcher remains globally serial** until separately changed and tested.

## 5. Rule and automation changes

Canonical rules, `CLAUDE.md`, skill instructions, settings, workflows and PR templates have one coordinator
owner during a batch. Changes to `.github/`, rulesets or `.claude/settings.json` keep existing approval
requirements. Never loosen permissions, tests, limits or branch protections to enable concurrency.
This protocol is an agent instruction, not a scheduler, durable lease service or proof Claude auth works.

## 6. Clean up the worktree when the task completes

A worktree exists for one task. The moment that task ends, the agent that created it (or the coordinator who
dispatched it) removes it; leftovers clutter the editor's source control and hold stale locks.

1. **When:** the PR is merged, or the task is abandoned or handed off. A handoff removes the worker's checkout
   only after the integrator owns the branch at a named pushed SHA (`§3`).
2. **Before removing, check:** `git -C <path> status --porcelain` is empty, and the branch tip is on `origin`
   (`git rev-list --count origin/<branch>..<branch>` is 0). Anything else is reported, never discarded.
3. **Remove:** `git worktree remove <path>`, then `git worktree prune` and delete the local branch
   (`git branch -D <branch>`; a squash merge makes `-d` refuse). No `--force` on a dirty tree.
4. **Locks:** unlock only when the process named in the lock reason is no longer running
   (`ps -p <pid>`). A live lock belongs to someone else's active session; leave it and say so.
5. **Never** remove a worktree you did not create or were not assigned, or the main checkout.
6. The final message of the task states that the worktree was removed (or why not).
