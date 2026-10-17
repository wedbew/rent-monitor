# Rule: keep README.md current

`README.md` at the repo root is the human entry point (create it when the first runnable piece lands). It stays short
and links to `docs/BLUEPRINT.md` for architecture instead of copying it.

## When to update

| Change | README section |
|---|---|
| New run, test, migrate or seed command; new env var or bootstrap step | **How to run** (names from `.env.example` only — never values) |
| Stack or dependency change (FastAPI, Procrastinate, SQLAlchemy, Stripe, Caddy, Postgres version) | **Stack** |
| New top-level doc, ADR or runbook | **Project docs** table — no broken links |
| Implementation-order step (blueprint §4.8) completed, or phase change | **Status** |
| Convention agents or contributors must follow | **Development conventions** → link to `.agent/agents.md` |

## Required content once the app runs

Parallel workers queue exact README changes in their RM handoff (`parallel-work.md`); the integrator
updates the actual README in the same feature PR before readiness. Table ordering or overlapping link
additions do not block independent coding. Verify new commands against integrated code.

1. One-line architecture summary: single VPS, Docker Compose, Caddy + FastAPI + Procrastinate workers + Postgres 17, Python-only server.
2. **How to run** that actually works: `make dev`, `make test` (`uv run pytest -m "not e2e"`), `make migrate`, local Compose stack.
3. **Status**: link `docs/STATUS.md` for delivery state and the current authorized phase; do not restate an obsolete Phase-1 restriction.
4. Links: blueprint, `.agent/agents.md`, `docs/LIMITATIONS.md`, `CHANGELOG.md`.

## Do not

- Paste architecture diagrams or the cost table; link to the blueprint section.
- Leave placeholder text in **How to run** once a command exists.
- Add a mandatory env var or service dependency without updating README and `.env.example` together.
