# ADR 0007 — Library pins: SQLAlchemy, Stripe SDK, Procrastinate

- **Status:** **proposed — owner decision D-02 outstanding** · **Date:** 2026-10-11 · **Ticket:** RM-31

## Context
The blueprint text says SQLAlchemy 2.0; PyPI's current release is 2.1.4 (read 2026-10-11). The blueprint targets Stripe API
`2026-09-30.endive`; which SDK major defaults to that version is unconfirmed (PyPI shows `stripe` 16.0.0). Procrastinate is 3.10.0,
Alembic 1.20.0, psycopg 3.3.6, sse-starlette 3.5.0 (all read 2026-10-11).

## Proposal
- **SQLAlchemy:** start on the blueprint's **2.0 line** (`>=2.0,<2.1`) because the blueprint's models and §4.5 samples were written
  for it and nothing exists yet that would justify the 2.1 delta. Revisit 2.1 as its own ticket; the async/psycopg 3 surface is
  the same. If the owner prefers 2.1, change the one range in `packages/rm-core/pyproject.toml`.
- **Stripe:** pin the SDK **exactly** and send `Stripe-Version` explicitly from `STRIPE_API_VERSION`; verify the SDK's default API
  version with `context7` and a unit test when the billing ticket (#14) starts. No SDK pin is added before then.
- **Procrastinate:** `>=3.10,<4`; Alembic `>=1.20,<2`; psycopg `[binary,pool]>=3.3,<4`.

## Consequences
- Nothing here is irreversible while no migrations or billing code exist; the first baseline migration (#11) uses only
  constructs valid on both SQLAlchemy lines.
- The owner confirms or overrides in issue #43 / D-02; on confirmation change **Status** to accepted.
