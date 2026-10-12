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
