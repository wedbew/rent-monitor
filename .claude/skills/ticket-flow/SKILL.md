---
name: ticket-flow
description: Take a GitHub issue to a merged PR on staging (branch, commits, PR body, CI watch, auto-merge, close). Use at the start of any ticket.
---

0. Resume first: `git branch -a | grep rm-<n>-`, `gh pr list --search "head:rm-<n>-"`, and the latest `<!-- rm-checkpoint -->` issue comment. If any exists, continue on that branch and PR; never open a replacement without a stated technical reason (`rules/delivery.md`). Check `Depends on:` is closed; if not, stop and comment.
1. Read the issue and the blueprint section it names. Read `.agent/rules/poc-reference.md` (greenfield, production bar) before engine work.
   Ambiguous money/auth/tenant/irreversible point → comment on the issue and stop.
   For owner-authorized parallel sessions, read `.agent/rules/parallel-work.md`: use your assigned isolated
   checkout, owned paths and issue-local handoff. Routine shared-doc conflicts do not stop owned coding.
2. For a new unassigned checkout: `git switch staging && git pull --ff-only && git switch -c rm-<n>-<slug>`.
   If the parallel coordinator already provisioned your issue branch, verify its assignment/base SHA and
   use it; do not switch branches or recreate it. Resume existing issue branches per step 0.
3. Tests first (invariant / failure / concurrency), then code. `make check` (lint, types, tests) before every push.
4. Commit `type(RM-<n>): subject` (≤72 chars, validated by `scripts/check_commit_msg.py`). Tag LEGAL/GDPR sites as you write them.
5. Update docs in the same PR: `docs/STATUS.md` (journey row and level), `CONTEXT.md`, `CHANGELOG.md`, `README.md`, `docs/LIMITATIONS.md` as the rules in `.agent/rules/` say. No separate status-only PR.
   In parallel work, record exact deltas immediately in `docs/parallel-handoffs/RM-<issue>.md`; hand over
   exclusive branch ownership for the integrator to reconcile canonical docs in this same PR before
   readiness and rerun checks. A handoff alone does not satisfy step 5.
6. `gh pr create --base staging` using `.github/pull_request_template.md` (Closes #n, tests with the real pytest summary line, checklist).
7. Watch: `gh pr checks <n> --watch`; fix failures per `rules/pull-requests.md`; then `gh pr merge <n> --squash --auto`.
   Ask a human first for sensitive areas listed there. The `close-issues` workflow closes the issue; verify it.
   In parallel handoff mode, the designated integrator owns branch changes, integrated checks and merge
   after exclusive ownership transfer; the worker never races it with pushes or merges.

8. Before you stop for any reason (done, blocked, out of turns), post one issue comment starting `<!-- rm-checkpoint -->`: Done · Checks run (commands and summary lines) · Branch / PR · Blocked by (exact owner action) · Next command.
