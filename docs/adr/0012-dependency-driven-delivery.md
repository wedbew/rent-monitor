# ADR 0012 - Dependency-driven delivery and a journey-first priority

- **Status:** accepted - **Date:** 2026-10-13 - **Decided by:** maintainer (delivery-engineer brief of 13 Oct 2026) - **Ticket:** RM-177
- **Amends:** `.agent/agents.md` section 7 ("do not start step N+1 with step N red"); `docs/ROADMAP.md` D-10

## Context
`docs/DELIVERY-AUDIT.md` (RM-177) found 70 merged PRs but no authenticated listing-to-result journey. Strict step order
(`agents.md` section 7) coexisted with parallel lanes in the roadmap, and D-10 (does "not started" count as "red"?) was never
answered, so agents had to guess. Status prose in README, CONTEXT and BLOCKERS contradicted GitHub.

## Decision
- Order is enforced by explicit `Depends on:` lines on issues, not by step number. A prerequisite is met when its issue is closed
  or its interface is merged to `staging`. D-10 is answered: *not started is not red*; only a failing check on `staging` stops work.
- Until the offline audit journey acceptance test is green in CI, that journey is P0 and optional surfaces wait.
- "Done" has four levels (implemented, integrated, provider-verified, launch-ready); only the first two are claimed from offline tests.
- `docs/STATUS.md` is the single delivery-state view; status housekeeping rides in implementation PRs.
- Sensitive areas keep human approval (money, auth, tenancy, migration contracts, invariants, workflows); approvals are recorded
  once against a head SHA.

## Not changed
Greenfield (ADR 0001), the invariants, release gates, the Phase 1 backend-only boundary, and the rule that agents never merge to `main`.

## Consequences
- Independent lanes (engine, market, ops, owner setup) may run in parallel; dependent work is blocked explicitly instead of implicitly.
- The dispatcher (`scripts/dispatch_next.py`) can pick work mechanically because readiness is machine-readable.
