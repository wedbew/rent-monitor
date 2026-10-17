# Rule: deliver the user journey; ready, done, checkpoints

Decision of record: `docs/adr/0012-dependency-driven-delivery.md`. The one authoritative view of delivery state is
`docs/STATUS.md`; GitHub (issues, PRs, checks) is the source for anything that changes hourly. No other file carries "what is
done" prose (README *Status* and `CONTEXT.md` §8 link to STATUS).

## Priority

Until `tests/integration/test_audit_journey.py` passes in CI for success, duplicate submission, tenant isolation and failure
with credit release, **P0 is the authenticated analysis journey**: sign in → submit a sale listing → reserve credit → queue →
acquire context → run the engine → persist and retrieve the canonical result (STATUS.md *Journey*). Other work may proceed
only if it is independent of that path (own files, stable contracts) or is owner-side preparation. Do not start an optional
surface (radar, screener, redesign, extra admin, analytics) while a P0 slice is ready.

## Ready (all must hold before an issue gets the `ready` label)

1. Acceptance criteria are testable and say which test proves them.
2. `Depends on: #a, #b` lists every prerequisite; each is **closed**, or its interface is merged to `staging`.
3. No unresolved owner decision. A decision the owner already made (BLOCKERS *Resolved*, ADRs, ENGINE-SPEC) is not asked again.
4. One verifiable behaviour, one PR. Size is judged by behaviour, not line count. Umbrella issues (`umbrella`) are never `ready`.
5. `Files:` names the implementation/test paths it owns. Two ready issues may not own the same implementation
   file; migrations are serialised (one open migration PR). Shared central docs are integrator-owned under
   `parallel-work.md`, with a unique RM handoff per issue and actual same-PR edits before readiness/merge.
6. Provider behaviour is either behind an injectable fake (say so) or the issue is labelled `owner`.

Not ready: label `blocked` and write the blocker (exact owner action, `docs/BLOCKERS.md`). Do not label `agent` on work that is
oversized, blocked or ambiguous.

## Sequencing

Parallel work follows `parallel-work.md` and `docs/PARALLEL-FEATURE-DELIVERY.md`: separate checkout/branch
writers, exclusive shared-code reservations, same-PR docs integration and serialized staging merges.
The current dispatcher is serial; the protocol does not silently enable multi-lane dispatch. A routine
documentation collision is not an owner blocker or a dependency of other lanes.

`agents.md` §7's step order is the *default narrative*, not a gate. The gate is `Depends on:`. Independent work proceeds when
the contracts it consumes are merged. Dependent work never builds on an assumption: if the interface you need is unmerged, stop
and record the dependency. `staging` red blocks everything (stop the line, fix first).

## Done has four levels, and a closed issue means only the first two

| Level | Evidence | Words allowed |
|---|---|---|
| 1 Implemented | merged to `staging`, offline tests, docs in the same PR | "implemented" |
| 2 Integrated | acceptance test through API, queue, Postgres and the engine, with named fakes, green in CI | "works offline end to end" |
| 3 Provider-verified | authorised sandbox/live run recorded (date, account type, result) in STATUS and `docs/LIMITATIONS.md` | "verified against <provider>" |
| 4 Launch-ready | release gates §6 and `docs/PRE-DEPLOYMENT.md` ticked with evidence | "production ready" |

An issue whose acceptance needs level 3+ stays open or is split; close the offline slice and leave the integration issue open.
Never describe an offline-fake run as live-provider validation.

## Pull requests and shared files

- `docs/STATUS.md` edited in a PR describes the state **after that PR merges**; `staging` keeps the old text until then. A PR body must not present branch results as already on `staging`.
- Label `ready` only when each prerequisite is merged, not merely open in a PR.
- Update `CHANGELOG.md`, `CONTEXT.md`, README, `docs/STATUS.md` and `docs/LIMITATIONS.md` **in the implementation PR**. No
  docs-only PR for status housekeeping; a docs PR is for a spec, an ADR, or an owner decision.
- Rebase on `staging` to resolve shared-file conflicts. Do not open a replacement PR unless the old one cannot be fixed; say
  why in the new PR.
- Stack only for a technical reason, target the parent branch, and retarget the same PR after the parent merges.
- Draft PR at first push. Ready for review only after `make ci` (or `make ci-fast` plus the stage list in the PR body).

## Checkpoints and resume

Branch `rm-<issue>-<slug>`, one per issue. At the end of every run or session (including a timeout you can foresee) post
**one** issue comment starting with `<!-- rm-checkpoint -->` containing: *Done* (behaviour, not files) · *Checks run* (exact
commands and summary lines) · *Branch / PR* · *Blocked by* (exact owner action, or none) · *Next command*. A run that starts on
an issue first looks for branch `rm-<n>-*`, an open PR and the latest checkpoint, and resumes there. Label `in-progress` while a
branch exists.

## Approvals

The owner's recorded approvals are not repeated for the same revision. Sensitive PRs (`pull-requests.md`) get one request
comment: what changed, tests, risk. Record in `docs/BLOCKERS.md` *Approved* the PR number and approved head SHA; a later
non-trivial push needs a new approval. Routine implementation inside a settled scope is not blocked on re-approval.

## Measure

`uv run python scripts/delivery_metrics.py` prints calendar time (created to merged), execution time (created to last check
green) and wait (green to merged) per PR from GitHub. Quote it, not impressions.
