---
name: invariant-guard
description: List, run and add the business invariant tests; refuses to delete, skip or weaken them. Use when touching engine, ledger, market data or tests/*invariant*.
---

Invariants (`agents.md` §1), each needs a named test marked `@pytest.mark.invariant`:
`test_invariant_rent_is_not_a_deal`, `test_invariant_asking_is_not_deed`, `test_invariant_admin_fee_is_opex`,
`test_invariant_deterministic_math` (blueprint §4.6). Run: `uv run pytest -m invariant -q -rs`.

- Never delete, skip, `xfail`, loosen an assertion or change a fixture to make one pass. If one looks wrong, stop and ask in the issue.
- Adding one: name `test_invariant_<rule>`, marker `invariant`, offline, deterministic, asserts the *business outcome* (status, DB constraint, number),
  and add its name to the `required` set in the `invariants` CI job.
- The CI `invariants` job is gated by repo variable `ENABLE_INVARIANTS_JOB`; the PR that lands the four tests enables it and re-adds the required check.
