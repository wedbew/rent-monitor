# RentMonitor — Agent Rules (canonical)

> Single source of truth for every AI agent working in this repo (Claude Code, Gemini CLI, Codex, Cursor).
> `CLAUDE.md`, `AGENTS.md` and `.gemini/settings.json` only point here. Keep this file under ~300 lines;
> long how-tos live in `.claude/skills/*/SKILL.md`.

## 0. Status of this document
- **POC is reference only; build from scratch to production quality** — read `rules/poc-reference.md` before any engine work.
- Orientation: `CONTEXT.md` at the repo root (summary, POC porting map, open decisions — living file, see §10). Toolchain: `docs/TOOLCHAIN.md`.
- Spec of record: `docs/blueprint.md` (RentMonitor SaaS — Architecture & Implementation Blueprint, 11 Oct 2026).
- Current phase: **Phase 1 — backend only.** Do not create or modify anything under `frontend/` except deleting
  `frontend/server/*.ts`, `frontend/src/lib/cashflow.ts`, `frontend/src/lib/appreciation.ts` when the ticket says so.
- If this file and the blueprint disagree, stop and ask in the issue. Do not pick one silently.

## 1. Non-negotiable invariants (each has a named test marked `@pytest.mark.invariant`)
1. **RENT is not a deal.** A RENT listing ends `rejected / RENT_NOT_DEAL`, no vision call, credit released.
2. **Asking ≠ deed.** Moniter/Otodom-sale prices are `asking`; GUS BDL/Cenogram are `deed`. Never average, merge or
   substitute one for the other. Enforced by the `asking_is_not_deed` CHECK constraint and by distinct types.
3. **Admin fee (`characteristics.rent`, czynsz) is OPEX, never income.**
4. **Deterministic math.** All cash flows, IRR, MOIC, CAGR, tax, Max Bid are computed by Python in
   `apps/deal-analyzer`. LLMs only classify images, transcribe OCR and propose adjustments clamped to ±15%.
5. **Fractional ownership** (`udział`, `1/2 udziału`, `udział w spadku`) is rejected from yield ranking and audits.
6. **JSON is canonical; Markdown is a view.**

You may not delete, skip, `xfail`, or weaken an `invariant` test. A PR that does is rejected by review.

## 2. Architecture boundaries
- `apps/*` are the analytical engines, **written from scratch** (ADR 0001): the POC `otodom-rent-report` is reference only —
  never copy, move or import it (`rules/poc-reference.md`). Code targets production quality under real traffic.
  `ContextRepository` and `ProgressSink` are native seams of the new engine.
- Never compute a financial number outside `apps/deal-analyzer`. API/worker copy values from `DealAnalysis`
  into typed columns; they never derive them.
- Layout (blueprint 4.1): `packages/rm-core` (settings, models, repositories, ledger, entitlements, flags),
  `packages/rm-contracts` (Pydantic API schemas + problem codes), `services/api` (FastAPI), `services/worker`
  (Procrastinate). `services/*` may import `packages/*`; `packages/*` never import `services/*`.
- Server runtime is **Python only**. No Node service, no Redis, no Celery, no second migration tool.
- One Postgres schema, `app`, owned by Alembic. Procrastinate's tables are applied by `procrastinate schema --apply`.
- All state lives in Postgres; API processes are stateless.

## 3. Coding standards
- Python ≥ 3.12, uv workspace. Add deps with `uv add --package <member> <pkg>`; commit `uv.lock`.
- Pydantic v2 with `ConfigDict(extra="forbid")` on every inbound model.
- SQLAlchemy 2.x async + psycopg 3. Sessions come from the dependency; route code never commits except where the
  blueprint shows it (audit create, webhook claim).
- **Money:** `Decimal` in Python, `NUMERIC` in Postgres. `float` is banned in persisted or returned money fields.
- **Time:** timezone-aware only (`datetime.now(UTC)`); ruff `DTZ` enforces it.
- Errors: RFC 9457 `application/problem+json` via `rm_api.problems.Problem` with a stable `code` from
  `rm_contracts.problems`. Never invent a code that is not in the error table; add it there first.
- Logging: **structlog** JSON only (no loguru, no print). Bind `request_id`, `user_id`, `audit_id`, `job_id`.
- Every external call (Otodom, OpenRouter, GUS BDL, Moniter, Stripe, Nominatim, Fakturownia, Resend) goes through an
  injectable client with explicit timeouts. Tests replace it with a fake; tests never hit the network.
- Async routes never block: CPU or blocking I/O goes to `asyncio.to_thread` or the worker.

## 4. Security boundaries
- Never read, print, commit or paste real values from `.env`. Use `.env.example` names only.
- Never run anything against production (VPS, live Stripe, production DB). Database tools point at the local
  Compose Postgres or Testcontainers. Stripe tools use the sandbox only.
- Tenant isolation: every tenant-owned query goes through a repository that takes a `Principal`. Foreign
  resources return **404, never 403**.
- Stripe webhooks: verify the signature on the **raw body** before any parsing. Idempotency by event id.
- Sessions: store only SHA-256 of tokens. Cookies `HttpOnly; Secure; SameSite=Lax`. Unsafe methods require
  `Origin == PUBLIC_APP_URL`.
- No `pull_request_target`, no secrets in jobs that run PR code, every action pinned to a commit SHA.
- Do not add a dependency without saying why in the PR body; prefer the standard library.

## 5. Testing rules
- `uv run pytest -m "not e2e"` must pass before you push. Postgres is real (Testcontainers `postgres:17`),
  never SQLite.
- New behaviour needs a test in the same PR. Bug fixes start with a failing test.
- Markers: `invariant`, `money`, `integration`, `e2e`. Register new markers in `pyproject.toml`.
- Money and concurrency code (ledger, quota, webhook, pass stacking) needs a concurrency or property test
  (hypothesis), not only a happy path.
- Migrations: `pytest tests/migrations` (pytest-alembic) and `squawk` must pass. Expand → deploy → contract.

## 6. Git workflow
- Work from an issue. Branch `rm-<issue>-<slug>` from `staging`.
- Commit / PR title: `type(RM-<issue>): subject` — types: feat fix perf refactor test docs build ci chore revert.
  Breaking change: `type(RM-n)!: ...`. Only the repository's root commit may omit the ticket.
- PR body contains `Closes #<issue>`, what changed, how it was tested, any blueprint deviation, a **Legal / GDPR** line
  (§11) and a **Context** line (`CONTEXT.md` updated: §n, or not affected and why).
- After opening a PR, monitor its checks and fix failures yourself (`rules/pull-requests.md`); stop and ask before weakening any test, rule or workflow.
- Never push to `main` or `staging` directly. Never force-push shared branches. Never merge your own PR.

## 7. Implementation order (blueprint 4.8) — do not start step N+1 with step N red
1. Engine seams → 2. Data plane (models, Alembic baseline, Procrastinate schema, importers) → 3. Auth →
4. Audits (submit, worker, SSE, reconciler) → 5. Billing (Checkout, BLIK pass, webhook, entitlements, VAT outbox)
→ 7. Ops (compose, backups) → 8. Market & screener. Step 6 (frontend) is Phase 2.

## 8. Tools available to agents
- MCP: `github` (this repo), `context7` (library docs — use it before writing Procrastinate, Stripe, SQLAlchemy
  async or sse-starlette code), `postgres` (restricted mode, local only), `stripe` (sandbox only).
- Commands: `make test`, `make lint`, `make types`, `make migrate`, `uv run pytest -m invariant`.
- Skills: `.claude/skills/{new-migration,add-endpoint,invariant-guard,stripe-webhook-change,ticket-flow}`.

## 9. When unsure
State what you confirmed (read in code, test output) separately from what you infer. Flag limitations explicitly.
Ask in the issue rather than guessing on money, auth, tenant isolation or anything irreversible.

## 10. Documentation upkeep (rules in `.agent/rules/`, tool-neutral)
Read the matching file when your change touches the area; update the doc in the **same PR**.
- `rules/architecture.md` — blueprint ↔ code agreement: routes, error codes, schema, billing, env, containers, new clients, ADRs.
- `rules/limitations.md` — `docs/LIMITATIONS.md` register (`L-XXX`, active/resolved/deferred, confirmed vs inferred).
- `rules/changelog.md` — `CHANGELOG.md` (Keep a Changelog), bullets end with `(RM-<issue>)`.
- `rules/readme.md` — `README.md`: How to run, Stack, Project docs, Status.
- `rules/legal-tags.md` — `LEGAL[...]` / `GDPR[...]` tags (see §11).
- `rules/poc-reference.md` — POC is read-only reference; greenfield rewrite; production-ready bar (ADR 0001).
- `rules/pull-requests.md` — PR template (`.github/pull_request_template.md`) and checklist semantics; required for every PR.
- `rules/context.md` — keep root `CONTEXT.md` current: update it in the same PR as any change that makes it stale; bump its "Last updated" line.
Cursor mirrors these in `.cursor/rules/*.mdc` as pointers only; edit the `.agent/rules/` file, never the pointer.

## 11. Legal and GDPR tagging (rule: `.agent/rules/legal-tags.md`)
- Features that may carry legal risk — Otodom scraping, listing-URL analysis, photo/floor-plan download and vision/OCR,
  third-party data reuse — **stay available but must be tagged**: `# LEGAL[scraping|url-analysis|images|third-party-data|republication|tax-invoice]: <fact> (RM-n)`.
- Code that touches personal data is tagged `GDPR[personal-data|processor|retention|erasure|consent]`. New personal-data
  columns state retention and erasure path.
- Tags are also bound at runtime (`rm_core.legal.LegalTag` → structlog `legal_tags`, `audit_event.payload`); tagged features get
  a default-on flag or setting so counsel can switch one off without a deploy.
- **While re-engineering from the POC's behaviour** (new fetchers, importers, engine, deleting `frontend/server/*.ts`): use
  `CONTEXT.md` §6 hot-spots plus a grep of existing tags, carry tags into the new code, and tag every matching site you write or pass. Never drop a tag; never remove a feature just because it is tagged.
- Tags mean "needs legal attention", not a legal verdict. Do not write "legal"/"illegal" conclusions; log unknowns in
  `docs/LIMITATIONS.md`. PR body gets a **Legal / GDPR** line (tags added/changed/removed).
