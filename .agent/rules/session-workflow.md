# Rule: session hygiene and delegated briefs

From `docs/SESSION-REPORT-2026-10-11-to-18.md` (31 sessions, 4,618 tool calls). Keep this file short: it is loaded in every session.

1. **One issue, one session.** Start each issue with `/clear` and split work that would exceed about 300 tool calls.
   Re-run an interrupted request in the same session; do not reopen a new session with the same text.
2. **Brief first, stop conditions second.** A brief states what is authorised, what is not, what "done" means (merged,
   or PR open with checks watched) and when to ask. Do not ask for approval the brief or `OWNER-DECISIONS` already gives.
3. **Edit with `Edit`, create with `Write`.** Do not rewrite existing files with heredocs or inline Python string
   replacement, so diffs stay reviewable and Read-before-edit holds.
4. **One checkout, one writer.** Parallel work runs in its own worktree under `.claude/worktrees/` (`parallel-work.md`).
   Never switch branches in a shared checkout.
5. **Test auth with `claude -p`.** Use one scripted one-shot call, not an interactive session, to check a token.
6. **Check before claiming a value is missing.** Check names and presence only (for example `grep -o '^NAME=' .env`,
   the value is never printed). Say which check ran. This is the only permitted read of `.env`; see `agents.md` §4.
7. **Verify a number before using it.** When challenged, read its source first and quote it.
8. **Turn a repeated correction into a rule or memory the same day.** Add it to the rule file for its area, not to chat.
9. **Keep instruction files small.** Stay well under the 120k-character instruction limit; check size before adding a rule.
10. **Classify tool errors.** Count error types per session so the most common cause is fixed first (follow-up, no
    tooling yet).
