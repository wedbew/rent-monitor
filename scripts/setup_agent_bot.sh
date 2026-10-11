#!/usr/bin/env bash
# Grants a separate GitHub *machine user* write access to this repo only, and verifies it cannot bypass the rulesets.
# GitHub does not let scripts create accounts or personal access tokens, so two steps stay manual (see docs/AGENT-BOT.md):
#   1. create the account (e.g. rentmonitor-agent) at https://github.com/signup
#   2. as that account, create a fine-grained token (Settings > Developer settings): repository = this repo only,
#      permissions: Contents RW, Pull requests RW, Issues RW, Actions R, Metadata R. No admin, no workflows write.
# Usage:   BOT_USER=rentmonitor-agent BOT_TOKEN=github_pat_xxx ./scripts/setup_agent_bot.sh
# Run as the repo OWNER (gh logged in as the admin). The token is only used to accept the invite and to test, never stored.
set -euo pipefail
REPO="${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
: "${BOT_USER:?set BOT_USER}"; : "${BOT_TOKEN:?set BOT_TOKEN}"

echo "== invite $BOT_USER as collaborator (push = write role, not admin) on $REPO"
gh api -X PUT "repos/$REPO/collaborators/$BOT_USER" -f permission=push --silent || true

echo "== accept invitation as the bot"
INV=$(GH_TOKEN="$BOT_TOKEN" gh api user/repository_invitations --jq ".[] | select(.repository.full_name==\"$REPO\") | .id" | head -1)
if [ -n "${INV:-}" ]; then GH_TOKEN="$BOT_TOKEN" gh api -X PATCH "user/repository_invitations/$INV" --silent; fi

echo "== verify role"
PERM=$(gh api "repos/$REPO/collaborators/$BOT_USER/permission" --jq .role_name)
echo "role: $PERM"; [ "$PERM" = "write" ] || { echo "FAIL: expected write, got $PERM"; exit 1; }

echo "== verify the bot cannot touch rulesets or settings (expect 403/404)"
CODE=$(GH_TOKEN="$BOT_TOKEN" gh api -X PATCH "repos/$REPO" -f description=x --silent 2>&1 | grep -oE "HTTP [0-9]+" || true)
echo "PATCH repo as bot: ${CODE:-unexpected success}"; [ -n "$CODE" ] || { echo "FAIL: bot can edit the repo"; exit 1; }

echo "== done. Use the token for agents:  export GH_TOKEN=<bot token>  (or add repo secret AGENT_BOT_TOKEN)"
echo "   Optional: gh secret set AGENT_BOT_TOKEN --repo $REPO"
