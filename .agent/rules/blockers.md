# Rule: stop and record blockers instead of guessing or faking

`docs/BLOCKERS.md` is the list of things only the owner can unblock. Agents read it before starting a ticket and update it
the moment they hit one.

## When to stop
Stop work on the affected part, write the blocker, tell the owner, and move to an unblocked ticket (or end the run) when:
- a tool, service or account is not set up: Better Stack, Umami, Stripe (keys, BLIK activation, webhook), Google OAuth, Resend,
  Cloudflare R2/DNS, Fakturownia, OpenRouter, the VPS, a domain;
- a required env value is missing or an `.env.example` name cannot be verified (agents may not read `.env*`);
- a step needs a repo setting, ruleset, secret, token scope, paid plan or `.claude/settings.json` change;
- a decision is the owner's (engine formulas, pins, VAT, legal review, retention periods);
- local tooling is broken in a way only the owner can fix (Docker, credentials).

Never fake it: no placeholder keys that look real, no stubbed integrations presented as done, no weakened tests or rules.
A safe offline fake behind an injectable client is fine if the PR says the live integration is blocked.

## How
1. Add a row to `docs/BLOCKERS.md` under *Open*: id `B-nnn`, what is blocked, what the owner must do (exact, copy-pasteable),
   which tickets wait on it, date. Link it from the issue and the PR body.
2. Tell the user in the final message of the run; do not continue past the blocker.
3. When the owner resolves it, move the row to *Resolved* with the date; do not delete rows.

## Always, in the same spirit
- Work only inside this checkout; never create worktrees or directories outside it.
- After a PR merges: `git switch staging && git pull --ff-only`, delete the local branch, and say which commit you are on.
- Commit only files you changed (never `git add -A` over someone else's uncommitted work).
