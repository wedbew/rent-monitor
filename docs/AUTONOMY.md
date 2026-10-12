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

`.github/workflows/dispatch.yml` runs `scripts/dispatch_next.py` every 30 minutes **only when the repo variable `ENABLE_DISPATCH` is
`true`** (set it with `gh variable set ENABLE_DISPATCH --body true`; unset it to stop). It looks at open issues:

- an issue labelled `agent` is in flight → nothing else starts (one at a time);
- no activity on it (issue or its `rm-<n>-*`/`claude/issue-<n>-*` PR) for 60 minutes → one `@claude resume` comment, then a second,
  then label `blocked` and a comment naming the owner action; the dispatcher never retries a `blocked` issue;
- nothing in flight → the lowest `Priority: P0..P2`, then lowest number, issue labelled `ready` whose `Depends on:` issues are all closed
  and that is not `blocked`, `umbrella`, `owner` or `in-progress` gets the `agent` label (which starts `claude.yml`).

Manual run: Actions → dispatch → *Run workflow* (dry by default; tick *apply* to act). Local dry run: `python3 scripts/dispatch_next.py`.
Idempotency: each dispatch or resume leaves a `<!-- rm-dispatch attempt=n -->` comment; attempts are capped at 2.
Everything the agent needs to continue is the checkpoint comment (`rules/delivery.md`).

## Canary log

| Date | Issue | Result | Evidence |
|---|---|---|---|
| 2026-10-11 | #100 (labelled `agent`) | failed in ~2 s, 0 turns, $0 cost; no PR | run 38182957497: `is_error:true` before any model call, then `compare` 404 from the action's own change check |
