# CLAUDE.md

@.agent/agents.md
@.agent/rules/architecture.md
@.agent/rules/limitations.md
@.agent/rules/changelog.md
@.agent/rules/readme.md
@.agent/rules/legal-tags.md

## Claude-specific notes
- Before writing code that touches Procrastinate, Stripe, SQLAlchemy async or sse-starlette, look the API up with
  the `context7` MCP server; the blueprint pins versions newer than most training data.
- Run `uv run pytest -m "not e2e" -q` and `uv run pyright` before declaring a task done; paste the summary line.
- Before editing or moving any file, `grep -nE "(LEGAL|GDPR)\["` it; carry tags through refactors and add the PR-body **Legal / GDPR** line.
- In GitHub Actions (`@claude`): open a PR against `staging`, never `main`; title per agents.md §6.
