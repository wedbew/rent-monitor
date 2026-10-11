---
name: new-migration
description: Add an Alembic migration in schema app safely (expand, deploy, contract). Use for any table/column/constraint/index change.
---

1. Change `packages/rm-core/src/rm_core/db/models.py` first (naming convention, `app` schema, `Decimal`/`NUMERIC` for money, CHECKs kept: `asking_is_not_deed`, ledger rules).
2. `uv run alembic revision --autogenerate -m "<what>"`; edit by hand; never touch Procrastinate tables (`procrastinate schema --apply` owns them).
3. **Expand-only** in this PR: add nullable/defaulted columns, new tables, concurrent indexes. Contract (drop/rename/NOT NULL) is a later PR after the old image is gone.
4. Personal-data column → tag `GDPR[personal-data]`, state retention and erasure path (`rules/legal-tags.md`).
5. `uv run pytest tests/migrations -q` (pytest-alembic: single head, up/down, model match) and `squawk` on `alembic upgrade head --sql`.
6. Humans approve contract steps and anything touching money, auth or tenancy tables (`rules/pull-requests.md`). Update blueprint §3 only if approved.
