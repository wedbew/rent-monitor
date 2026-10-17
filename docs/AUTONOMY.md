# Running the agent without your computer

The agent runs in GitHub Actions (`.github/workflows/claude.yml`), so work continues when your machine is off.
Trigger: label an issue `agent`, or comment/open an issue containing `@claude` as OWNER/MEMBER/COLLABORATOR
(the repo is public, so nobody else can start a run). The agent follows `.agent/agents.md`, opens a PR against `staging`
as the bot user, watches CI, fixes failures, enables auto-merge, and `close-issues` closes the ticket.

## One-time setup (secrets live in GitHub, never in the repo, never in chat)
1. `AGENT_BOT_TOKEN`: the bot's classic `repo` token (`docs/AGENT-BOT.md`). Without it PRs would not trigger CI.
   ```bash
   gh secret set AGENT_BOT_TOKEN --repo wedbew/rent-monitor --body "$(grep '^GH_TOKEN=' .env | cut -d= -f2-)"
   ```
2. `CLAUDE_CODE_OAUTH_TOKEN`: run `claude setup-token` in a terminal, then
   `gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo wedbew/rent-monitor` and paste when prompted. It draws on your Claude subscription.
3. Create the label once: `gh label create agent --color 5319e7 --description "Let the Actions agent implement this"`.
4. Repo → Settings → Actions → General: allow GitHub Actions to create and approve pull requests is **not** needed; keep it off.

## Trigger from your phone

- GitHub mobile app → open an issue → add the label `agent`, or comment `@claude <task>` (owner/member/collaborator only).
- The run appears under Actions → `claude`; it opens a PR against `staging` and comments on the issue where it stopped.
- Alternative for interactive work: Claude app → Code (claude.ai/code) with the repo connected.

## Why the agent does not read `.env`
`.env` holds secrets that would land in transcripts and logs (a token pasted into a chat has to be revoked). Agents receive credentials as
environment variables (`GH_TOKEN`, Actions secrets), which tools use without printing them. `.env` stays unreadable to agents (`agents.md` §4).

## Limits that stay
Merges go to `staging` only; `main` needs your approval (ruleset). Sensitive areas in `rules/pull-requests.md` still wait for a human comment.
A run is capped at 40 turns and 30 minutes; a ticket that does not finish leaves a comment explaining where it stopped.

## Dispatcher (opt-in, ADR 0012)

**Parallel-delivery audit, 2026-10-17:** this dispatcher is still **globally serial**. The [parallel feature
guide](PARALLEL-FEATURE-DELIVERY.md) maps independent lanes, isolated Claude sessions/runners, file
ownership and same-PR documentation integration; [the canonical rule](../.agent/rules/parallel-work.md)
applies to owner-authorized parallel work. No dispatcher or workflow behavior is changed by that rule.
Do not expect multiple automatic workers from extra `ready` labels. A future multi-lane dispatcher needs
explicit capacity/ownership/recovery tests and the normal workflow approval.

`.github/workflows/dispatch.yml` runs `scripts/dispatch_next.py` every 30 minutes **only when the repo variable `ENABLE_DISPATCH` is
`true`** (set it with `gh variable set ENABLE_DISPATCH --body true`; unset it to stop). States it distinguishes:

- **running**: a `claude` workflow run is active, or the PR's checks are pending: nothing happens;
- **awaiting approval or merge**: an open PR whose checks all finished well (no checks yet, or an unknown conclusion, is `pending`, never passing; found by branch `rm-<n>-*`, `claude/issue-<n>-*` or `RM-<n>` in the title,
  labelled `agent` or not): never resumed, never blocked, and no other issue starts;
- **failing**: PR checks failed and 60 minutes idle: one `@claude resume` comment, up to two, then `blocked`;
- **stalled**: labelled `agent`, no PR, 60 minutes idle: same resume-then-`blocked` path with the owner action in the comment;
- **free**: nothing in flight, the latest `ci` run on `staging` finished successfully on staging's current head (a missing, running, cancelled, timed-out, failed or older-commit run counts as unverified and idles) and no run is active: the lowest `Priority: P0..P2`, then lowest
  number, issue labelled `ready` whose `Depends on:` issues are all closed and that is not `blocked`, `umbrella`, `owner` or `in-progress`
  gets the `agent` label (which starts `claude.yml`).

A blocked issue is retried only when the owner comments `/retry` and removes `blocked`; attempts are counted after the latest `/retry`.
Manual run: Actions → dispatch → *Run workflow* (dry by default; tick *apply* to act). Local dry run: `python3 scripts/dispatch_next.py`.
Idempotency: each dispatch or resume leaves a `<!-- rm-dispatch attempt=n -->` comment; attempts are capped at 2 per `/retry`.
Everything the agent needs to continue is the checkpoint comment (`rules/delivery.md`).

## Diagnosing a failed run

The action hides its output. On failure `claude.yml` prints sanitised facts from the execution file (result, `error` / `errors` /
`api_error_status`, the error text; no transcript, tool data or credentials) to the job summary and as an error annotation
(`scripts/claude_failure_report.py`). Run the read-only canary any time from Actions, *claude*, *Run workflow*: Read tool only, 3 turns,
no write access, no branch or PR; on success the one-sentence answer is shown in the summary.

## Canary log

| Date | Issue | Result | Evidence |
|---|---|---|---|
| 2026-10-11 | #100 (labelled `agent`) | failed in ~2 s, 0 turns, $0 cost; no PR | run 38182957497: `is_error:true` before any model call, then `compare` 404 from the action's own change check |
| 2026-10-12 22:48Z | #190 (labelled `agent`) | failed in 40 s, no model turn; no PR | run 38318725879: `claude_code_oauth_token: ""` and `ANTHROPIC_API_KEY: ""`, i.e. the OAuth secret is empty (B-021). The `claude.yml` preflight now fails fast and comments the owner action. Retry target: #106 |
| 2026-10-13 09:47Z | read-only canary (`claude.yml` *Run workflow*, branch `rm-189-ci-dispatch`) | failed in ~2 s: `API Error: 401 OAuth access token is invalid` (`authentication_failed`, 0 turns, $0) | run 38378777564; the secret is present, the API rejects it (B-021). Earlier empty-secret runs fixed by re-setting the secret |
