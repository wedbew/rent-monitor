---
name: add-endpoint
description: Add an /api route to the FastAPI service with typed contracts, auth, tenant isolation, problem codes and tests. Use for any new or changed route.
---

1. Route must be in blueprint §2 *Route map*; if not, stop and ask. Define request/response in `packages/rm_contracts` (`ConfigDict(extra="forbid")`, bounded fields).
2. Auth dependency: `CurrentUser` / `require_admin` / entitlement dependency. Tenant-owned data only through a `Principal`-scoped repository; foreign id → **404**.
3. Errors via `rm_api.problems.Problem` with a code from `rm_contracts.problems.ProblemCode`; add a new code there first, then to the blueprint §2 error table.
4. Routes never commit except where the blueprint shows it; blocking work goes to `asyncio.to_thread` or the worker; outbound calls use injectable clients with timeouts.
5. Tests: happy path, validation failure, unauthenticated (401), other tenant (404), concurrency where state changes. Regenerate OpenAPI (`scripts/gen_openapi.py`) so frontend types do not drift.
6. Docs: blueprint route table, `CHANGELOG.md`, `CONTEXT.md` if scope changed.
