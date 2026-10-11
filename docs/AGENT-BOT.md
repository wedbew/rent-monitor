# Agent bot (machine user)

Agents should not run with the owner's admin token: the `staging` ruleset lets admins bypass it, so "never merge with red checks"
would rest on instructions alone. A dedicated machine user with the **write** role cannot bypass rulesets, change repo settings
or merge into `main` (ruleset: one human approval, no bypass), so GitHub enforces the limits.

## Set up (two manual steps, then one script)
1. Create a GitHub account for the bot, e.g. `rentmonitor-agent` (https://github.com/signup; GitHub does not allow creating accounts by API/CLI).
2. As that account create a **fine-grained personal access token**: resource owner = the bot, repository = **only `wedbew/rent-monitor`**,
   permissions Contents RW, Pull requests RW, Issues RW, Actions R, Metadata R. Nothing else (no Administration, no Workflows).
   Tokens cannot be created by API either. Set a 90-day expiry and calendar the rotation.
3. As the repo owner run:
   ```bash
   BOT_USER=rentmonitor-agent BOT_TOKEN=github_pat_xxx ./scripts/setup_agent_bot.sh
   ```
   It invites the bot with `push` permission, accepts the invite, checks the role is `write`, and checks the bot cannot edit repo settings.
4. Give agents the token as `GH_TOKEN` (local shell or the Actions secret `AGENT_BOT_TOKEN`). Never commit it; revoke it from the bot's settings if leaked.

## What the bot can and cannot do
| Can | Cannot |
|---|---|
| Push `rm-*` branches, open PRs to `staging`, enable auto-merge, comment, close issues | Push or merge to `main`, bypass rulesets, change settings, delete the repo, approve its own PR |
| Merge into `staging` once all 7 required checks are green (`gh pr merge --squash --auto`) | Merge with red or pending required checks |

Human approval stays for promotion `staging` → `main` (production), and for the sensitive areas listed in `rules/pull-requests.md`.
