# Feature-gap batch execution checkpoint — 2026-10-17

> **Historical first-wave checkpoint.** PRs #379/#380/#381 have since merged. The assertions below
> that the exact B-023 metric/source policy was approved are not supported by the canonical blocker
> register. Use current source, reconciled RM-376/377/378 handoffs and
> [the 2026-10-18 audit](../FEATURE-GAP-REVERIFICATION-2026-10-18.md) before dispatching follow-ups.

**Status:** Wave 1 foundation issues created; worktrees prepared; Explore agent verifying real paths.

## Lanes and ownership

| Lane | Issue | Worker | Branch | Worktree | Base SHA | Status |
|---|---|---|---|---|---|---|
| Media | #376 (G-01a) | Worker 1 | `rm-376-media-foundation` | `.claude/worktrees/worker-media` | `141c449` | ready to start |
| Otodom | #377 (OTO-01) | Worker 2 | `rm-377-otodom-corpus` | `.claude/worktrees/worker-otodom` | `141c449` | ready to start |
| BDL | #378 (LCTX-01) | Worker 3 | `rm-378-bdl-metrics` | `.claude/worktrees/worker-bdl` | `141c449` | ready to start |
| Coordinator/Integrator | n/a | Coordinator | `staging` (main checkout) | `/Users/marcin/Projects/rent-monitor` | current | managing merges |

## Shared-file reservations (integration tasks only)

| File | Reserved by | Phase |
|---|---|---|
| `packages/rm_core/db/models.py` | One migration owner at a time (expand → deploy → contract) | Coordination |
| `packages/rm_contracts/market.py` | Merged first, then all consumers | Wave 1 |
| `migrations/versions/` | Serialize: one per working branch | Coordination |
| `docs/CONTEXT.md` | Integrator only (worker provides handoff delta) | Integration |
| `docs/STATUS.md` | Integrator only (worker provides evidence) | Integration |
| `docs/BLOCKERS.md` | Integrator only (worker provides exact blocker note) | Integration |
| `docs/parallel-handoffs/RM-*.md` | Worker-owned unique per issue | Handoff |

## Wave 1 first slice acceptance and dependencies

### G-01a: Media foundation (#376)
- **Acceptance:** Postgres persist media manifest, versioned DealAnalysis model, authenticated API route, ForeignKey 404, serialization round-trip, partial failures explicit
- **Test scope:** real-Postgres integration, manifest cardinality validation, owned audit filter
- **Files to verify:** packages/rm_core/db/models.py, packages/rm_contracts/media.py, packages/rm_core/repositories/media.py, services/rm_api/routes/media.py, tests/integration/test_media_manifest.py
- **No blocking dependencies:** can proceed immediately after path verification

### OTO-01: Otodom corpus (#377)
- **Acceptance:** 727-location catalogue versioning, immutable offer corpus with source-ID uniqueness, deduplication rule, run/checkpoint staging, empty/partial/failed visibility
- **Test scope:** real provider (fake for tests), retry safety, concurrency, overlap handling
- **Files to verify:** packages/rm_core/db/models.py location/offer tables, packages/rm_contracts/market.py offer model, packages/rm_core/repositories/market.py CRUD, existing otodom_city_report client reuse (injectable)
- **Blocker:** Approved Otodom catalogue artifact (owner resolved B-023: all 727 confirmed 2026-10-16)

### LCTX-01: BDL metrics (#378)
- **Acceptance:** BDL territory hierarchy (gmina/powiat/województwo), approved metric definitions from B-023, pure comparison logic, publication thresholds applied
- **Test scope:** metric validation, missing/conflicting observation handling, suppression rules, unit-testable pure logic
- **Files to verify:** packages/rm_core/db/models.py territory tables, packages/rm_contracts/market.py observation model, packages/rm_core/market/bdl.py pure logic, tests/unit/test_bdl_metrics.py
- **Blocker:** B-023 metric/reference/attribution policy (owner approved 2026-10-16)

## Integration process (after wave 1 completion)

1. Worker completes slice, opens **draft PR** with `integration pending` label
2. Worker records `docs/parallel-handoffs/RM-<issue>.md` with doc deltas and new blockers using TEMPLATE.md
3. Worker hands **exclusive branch ownership** to coordinator at pushed SHA (no further commits)
4. Coordinator:
   - Merges latest `staging` into worker's branch (no force-push)
   - Resolves handoff: updates CONTEXT/STATUS/BLOCKERS/LIMITATIONS in same PR
   - Regenerates OpenAPI, schemas, lockfiles (command list in feature-gap guide §12)
   - Reruns checks on integrated SHA
   - Marks ready for review
5. Merge one PR at a time into staging, verify CI green
6. Coordinator returns branch ownership if worker takes next independent slice

## Standing authorization scope

Effective 2026-10-14 (owner-approved in session):
- ✅ Implement, test, open and **merge into `staging`** backend work (auth, sessions, isolation, ledger, billing)
- ✅ Create real child issues, branches, PRs under existing parents (#282, #283, #284, #21, #16, #48, #49, #209)
- ❌ Never promote `staging` → `main` (human decision only)
- ❌ Never weaken tests, skip checks, force-push shared branches, bypass branch protection
- ❌ Never read `.env`, write real credentials, run live payments/purchases
- ❌ Never destructive DB operations, SSH/firewall/DNS changes without owner approval

## Timing and next steps

**Now:** Explore agent verifying real paths → worker session kickoff
**Immediate:** Each worker verifies branch checkout, starts with contract files (models, schemas, tests), proceeds to persistence and API slices
**Check-in:** Report actual checkedout path, first PR link, blocks after each worker session ends

---
**Last update:** 2026-10-17 12:25 UTC · RM-374 coordination session · Claude Haiku 4.5
