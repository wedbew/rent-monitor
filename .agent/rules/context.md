# Rule: keep `CONTEXT.md` current

`CONTEXT.md` at the repo root is the orientation file every agent and new contributor reads first: what we are
building, glossary, invariants, the POC → this-repo porting map, gotchas, state of the repo, open decisions. It
**summarises and links**; the blueprint stays the spec of record. A stale `CONTEXT.md` misleads every later session,
so updating it is part of the change, not a follow-up.

## Update it in the same PR when you

| Change | Section of `CONTEXT.md` |
|---|---|
| Add, move, rename or remove a package, service, app or top-level directory (`apps/`, `packages/`, `services/`, `migrations/`, `deploy/`, `frontend/`) | §4 Porting map, §8 State of this repo |
| Port or finish porting a POC module; change what is copied, wrapped, replaced or dropped | §4.1–§4.3 (mark the row done, with the PR/ticket) |
| Land a blueprint §4.8 step, a TOOLCHAIN Step 0 item, or a release gate result | §8 Order of work and state |
| Resolve, add or change an open decision (VAT display, allowance, corpus handling, SQLAlchemy/Stripe pins, …) | §9 Open decisions — tick it and record the answer and ticket |
| Find or fix a porting gotcha (float money, sync engine, blocking client, naming clash) | §5 Gotchas |
| Change an invariant, its enforcing code or its named test | §3 |
| Add, remove or re-tag a legal/GDPR hot-spot, or add a tag area | §6 (and `rules/legal-tags.md`) |
| Change the stack, auth, billing, hosting or phase scope | §1 (and the blueprint, via `rules/architecture.md`) |
| Add a term that appears in code, API or UI | §2 Glossary |
| Add a doc, ADR or runbook worth finding | §10 Where to look |
| Pin or change the POC commit/source being ported from | header **Sources** |

## How

1. Edit only the affected rows/sections; do not rewrite the file.
2. Bump the line `**Last updated:** YYYY-MM-DD · by: RM-<issue>` (use `datetime`-free plain text; today's date).
3. Keep *confirmed vs inferred* honest: when you verify an *(inferred)* item, remove the marker; when you add an
   unverified claim, mark it *(inferred)*.
4. Facts that are a **limitation** go to `docs/LIMITATIONS.md` and are linked from §5, not duplicated.
5. In the PR body, add a **Context** line: "CONTEXT.md updated: §n" or "not affected: <why>".
6. If your change makes `CONTEXT.md` disagree with the blueprint, follow `rules/architecture.md` (stop and ask);
   never edit `CONTEXT.md` to hide the disagreement.

## Reviewing

A PR that adds/moves a package, completes a §4.8 step, or answers an open decision without touching `CONTEXT.md`
is incomplete. Reviewers (human, Gemini, Claude) flag it as `should-fix`.

## Do not

- Move it into `docs/` or split it into several files; the root copy is the one tools load (`CLAUDE.md` imports it).
- Paste blueprint prose, code, secrets, real emails or customer data into it.
- Turn it into a task list — actionable work is an issue; this file records decisions and state.
- Let it grow past ~300 lines; push detail into the blueprint, an ADR or `docs/LIMITATIONS.md` and link.
