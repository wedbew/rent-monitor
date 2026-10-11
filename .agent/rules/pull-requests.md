# Rule: every PR uses the template and its checklist

The template is `.github/pull_request_template.md`; GitHub fills it in automatically, and agents opening a PR with
`gh pr create` must pass `--body-file` built from it (never an empty or free-form body). Git flow itself
(branch names, title format, no direct pushes) is `agents.md` §6.

## Sections — all required

| Section | What goes in it |
|---|---|
| `Closes #<issue>` | The GitHub issue; `RM-n` in the title maps to issue `#n` |
| What changed | One paragraph, and the blueprint section(s) implemented |
| How it was tested | Named tests added or changed, plus the pytest summary line actually run (`uv run pytest -m "not e2e" -q`) |
| Definition of done | Every box ticked or struck through with a reason; never delete a line |
| Deviations from the blueprint | `None`, or what and why; a real deviation also needs the maintainer's approval and an ADR (`rules/architecture.md`) |

The two last checklist items map to rules: **Legal / GDPR** (`rules/legal-tags.md`) and **Context** (`rules/context.md`).

## Checklist semantics

- Title: `type(RM-<issue>): subject`, ≤ 72 chars; the `pr-title` workflow enforces it.
- Invariants: no `invariant` test deleted, skipped, `xfail`ed or weakened. If you believe one is wrong, stop and ask.
- Money: `Decimal` / `NUMERIC`; all financial math stays in `apps/deal-analyzer`.
- Tenancy: tenant-owned queries go through a `Principal`-scoped repository; foreign resources return 404.
- Migrations: expand-only; the contract step is a later PR. `pytest tests/migrations` and `squawk` pass.
- Golden `DealAnalysis` snapshots unchanged, or every diff explained under the section it affects.
- New dependency: name it and say why in the PR body (`agents.md` §4).

## Authoring

1. Target `staging`, never `main`. Open as draft until the local checks (`make lint types test`) pass.
2. Keep one concern per PR. Tick only what you verified; unverified boxes stay unticked with a note.
3. End agent-authored PR bodies with the attribution line the tool requires.
4. Merge only as described under *Merge and close*.

## After opening: watch CI and fix it (agents do this, not the human)

Opening the PR is not the end of the task. Do not report "done" until the checks are green or you have stopped for a reason below.

1. Run a monitor on the PR in the background: `gh pr checks <n> --watch --fail-fast` (Claude Code: a background Bash or the Monitor tool;
   other agents: any equivalent poll, 60 s interval). Also read review comments from the Claude/Gemini review workflows.
2. A check fails → read its log (`gh run view <run-id> --log-failed`), reproduce locally with the same command
   (`make lint types test`, `uv run pytest -m invariant`, `pytest tests/migrations`), fix the **cause**, and push a new commit
   `fix(RM-<n>): ...` to the same branch. Then watch again.
3. Report to the user: final check status, what failed, what you changed. Paste the check names, not a paraphrase.

## Merge and close (autonomous, into `staging` only)

When **every required check is green** (`lint types test invariants migrations security pr-title`), there are no unresolved review
threads, and the PR body is complete, the agent that opened the PR merges it:

```bash
gh pr view <n> --json statusCheckRollup,reviewDecision,mergeable   # confirm all green first
gh pr merge <n> --squash --auto                                    # GitHub merges when required checks pass; branch auto-deleted
gh issue close <issue> --reason completed --comment "Merged in #<n> (<short-sha>) into staging."
git switch staging && git pull --ff-only && git branch -D <branch> # tidy local; history keeps everything
```

- **Issues are closed, never deleted.** `Closes #n` only auto-closes on merge into `main`; the `close-issues` workflow closes linked
  issues after a merge into `staging`. Verify with `gh issue view <n> --json state`; if still open, close it with the command above. Reopen on regression.
- Agents authenticate as the limited bot user (`docs/AGENT-BOT.md`), not the owner's admin token, when one is configured.
- Branches are deleted on merge; they stay restorable from the PR ("Restore branch") and from history.
- Squash title = PR title (`type(RM-n): subject`). Never `--admin`, never `--auto` to bypass checks, never merge with a red or pending required check.
- **Ask a human first (comment on the PR, wait for approval)** if the PR touches: money/ledger/quota/billing/webhooks, auth/sessions/tenant
  isolation, a migration's contract step, `.github/` workflows or rulesets, `.claude/settings.json`, an `invariant` test, or owner items in `docs/PRE-DEPLOYMENT.md`.
- **Promotion `staging` → `main`** is a human decision: the agent may open the promotion PR but never merges it (the ruleset requires one approval).
- After merging, **pull**: `git switch staging && git pull --ff-only`, delete the local branch, report the commit.
- After merging, update `CONTEXT.md` §8 if state changed and tick `docs/PRE-DEPLOYMENT.md` items the PR gave evidence for.

**Stop and ask instead of fixing when:**
- the fix would delete, skip, `xfail` or weaken an `invariant` test, loosen a lint/type/semgrep rule, lower `fail_under`, or edit a workflow or ruleset to make CI pass;
- the failure is a known gap, not a bug (record it in `docs/LIMITATIONS.md` and tell the user);
- the failure needs a secret, a token scope, a repo setting or a paid plan;
- the same check still fails after 3 fix attempts, or a failure looks flaky (re-run once, then report it).

Never: `--no-verify`, force-push, merge before checks are green, push to `staging`/`main` directly, or mark a check "expected to fail" in the PR body to avoid fixing it.
Known intentional red: the `invariants` job fails until the four named invariant tests exist (blueprint 4.6); report it, do not stub them.

## Do not

- Remove or reword template sections to make a PR look complete.
- Paste secrets, real emails or customer data into a PR body.
- Claim a test passed without the summary line from a run you did.
