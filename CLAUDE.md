# CLAUDE.md

@.agent/agents.md
@.agent/rules/architecture.md
@.agent/rules/limitations.md
@.agent/rules/changelog.md
@.agent/rules/readme.md
@.agent/rules/legal-tags.md
@.agent/rules/context.md
@.agent/rules/poc-reference.md
@.agent/rules/pull-requests.md
@.agent/rules/blockers.md
@.agent/rules/delivery.md
@.agent/rules/frontend.md
@docs/STATUS.md
@.agent/rules/repo-layout.md
@.agent/rules/env-example.md
@docs/BLOCKERS.md
@CONTEXT.md

## Claude-specific notes
- Before writing code that touches Procrastinate, Stripe, SQLAlchemy async or sse-starlette, look the API up with
  the `context7` MCP server; the blueprint pins versions newer than most training data.
- Run `uv run pytest -m "not e2e" -q` and `uv run pyright` before declaring a task done; paste the summary line.
- Before editing or moving any file, `grep -nE "(LEGAL|GDPR)\["` it; carry tags through refactors and add the PR-body **Legal / GDPR** line.
- In GitHub Actions (`@claude`): open a PR against `staging`, never `main`; title per agents.md §6.
- Before every push run `make ci` (or at least `make ci-fast`) and paste any SKIPPED stage into the PR; never push to let CI find it.
- After `gh pr create`, start a background `gh pr checks <n> --watch --fail-fast` (Monitor), fix failures per `pull-requests.md`, and report the final check status.
