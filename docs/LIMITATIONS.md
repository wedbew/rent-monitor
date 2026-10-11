# Limitations register

Entry format and rules: `.agent/rules/limitations.md`. IDs never reused. Seeded from blueprint "Limitations to carry into planning" and §5.

## Active

### L-001 — Otodom terms of service and EU database-right exposure
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** Fetch stage, `listing_snapshot`, city report, tags `LEGAL[scraping]`, `LEGAL[republication]`
- **Evidence:** inferred (blueprint §5; not assessed, not legal advice)
- **Description:** Commercial scraping of Otodom may conflict with its terms and database rights. Needs Polish legal review before charging.
- **Workaround:** Audits are user-initiated single-listing analyses; raw snapshots stay private. Features stay available and tagged.
- **Target:** Blueprint §5 risk register; pre-launch legal review

### L-002 — Datacenter IP may be blocked by Otodom
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** `UPSTREAM_BLOCKED` path, audit queue
- **Evidence:** inferred (no test from OVH ranges)
- **Description:** Unknown whether OVH VPS addresses are blocked.
- **Workaround:** `UPSTREAM_BLOCKED` releases the credit; about $10/month headroom reserved for a proxy.
- **Target:** Test from the VPS in week 1 (blueprint §5)

### L-003 — Per-audit OpenRouter cost is unmeasured
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** `PRO_MONTHLY_AUDIT_ALLOWANCE` (40, placeholder), pricing, release gate 4
- **Evidence:** estimate
- **Description:** No measured tokens/USD per audit; the Pro allowance has no cost basis yet.
- **Workaround:** Log tokens and USD per audit from day one; monthly budget kill-switch.
- **Target:** Set allowance after two weeks of measured COGS

### L-004 — POC engine models money as float
- **Status:** resolved by design (ADR 0001): the engine is rewritten with `Decimal`; kept as a lesson, not a defect to carry
- **Discovered:** 2026-10-11
- **Affects:** `apps/deal-analyzer` (`output.py`, `operating.py`), API/worker boundary
- **Evidence:** confirmed in POC read (CONTEXT.md §5 G1–G2)
- **Description:** Engine uses float; `agents.md` §3 requires Decimal in persisted/returned money fields.
- **Workaround:** None needed; do not reproduce float money in new code.
- **Target:** Data-plane step (blueprint 4.8 step 2)

## Resolved

_None yet._
