# Feature-Gap Batch Execution Summary — 2026-10-17

**Status:** Ready to dispatch three parallel workers. Staging: `93fb778` (execution plan + startup guides committed).

---

## What's been set up

### 1. Wave 1 foundation issues created and ready
| Issue | Lane | Scope | Worker | Branch |
|---|---|---|---|---|
| #376 | Media | G-01a: persist media manifest, API route, Postgres identity | 1 | `rm-376-media-foundation` |
| #377 | Otodom | OTO-01: rental corpus, catalogue, offer dedup, run state | 2 | `rm-377-otodom-corpus` |
| #378 | BDL | LCTX-01: territory hierarchy, metric models, comparison logic | 3 | `rm-378-bdl-metrics` |

### 2. Three isolated worktrees created
```
.claude/worktrees/worker-media    → rm-376-media-foundation
.claude/worktrees/worker-otodom   → rm-377-otodom-corpus
.claude/worktrees/worker-bdl      → rm-378-bdl-metrics
```
All based on `141c449` (RM-374 merged), independent from main staging checkout.

### 3. Execution documentation committed to staging
- `docs/parallel-handoffs/EXECUTION-CHECKPOINT-2026-10-17.md` — lane ownership, shared-file reservations, integration process, standing auth scope
- `docs/parallel-handoffs/WORKER-1-MEDIA-STARTUP.md` — concrete first-slice guidance (contracts → repos → tests, no migration yet)
- `docs/parallel-handoffs/WORKER-2-OTODOM-STARTUP.md` — Otodom corpus Phase 1 contracts and repository interface
- `docs/parallel-handoffs/WORKER-3-BDL-STARTUP.md` — BDL territory/metrics pure logic and unit tests

Each guide includes:
- Exact files to create/modify in Phase 1
- Acceptance criteria (from issue #376/#377/#378)
- Real file paths verified by Explore agent
- Integration test structure
- Handoff checkpoint instructions

---

## How to start each worker

Each worker operates in their worktree independently. They all follow the same protocol:

### Worker 1: MEDIA lane
```bash
cd /Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-media

# Verify checkout
git status  # should show rm-376-media-foundation on 141c449
git log --oneline -3

# Read guidance
cat /Users/marcin/Projects/rent-monitor/docs/parallel-handoffs/WORKER-1-MEDIA-STARTUP.md

# Implementation order:
# 1. Create packages/rm_contracts/media.py (typed models)
# 2. Create packages/rm_core/repositories/media.py (interface only, no DB)
# 3. Create tests/integration/test_media_manifest.py (Postgres fixtures)
# 4. Commit and open draft PR, mark "integration pending"
# 5. Fill docs/parallel-handoffs/RM-376.md with handoff delta
# 6. Signal coordinator when ready (link to PR)
```

### Worker 2: OTODOM lane
```bash
cd /Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-otodom

# Same pattern: verify → read startup guide → implement contracts/repos/tests → PR + handoff
# See docs/parallel-handoffs/WORKER-2-OTODOM-STARTUP.md
```

### Worker 3: BDL lane
```bash
cd /Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-bdl

# Pure logic first (no DB): TerritoryNode, MetricDefinition, Observation models
# Then BDLComparator with ranking/comparison unit tests
# See docs/parallel-handoffs/WORKER-3-BDL-STARTUP.md
```

---

## Coordinator role (main checkout, staging)

While workers implement, coordinator:
1. **Monitors** for draft PRs and handoff docs in RM-<issue>.md
2. **Reserves** migration slots one per working branch (expand → deploy → contract sequence)
3. **Integrates** shared docs (CONTEXT, STATUS, BLOCKERS, LIMITATIONS) **in the same feature PR**
4. **Regenerates** OpenAPI, schemas, frontend types from final merged sources
5. **Reruns** checks on integrated SHA before marking ready
6. **Merges** one PR at a time into staging after checks pass
7. **Verifies** staging CI green before next merge

**Key rule:** Coordinator edits shared docs, not workers. Workers write unique RM-<issue>.md handoffs.

---

## Standing authorization scope (from 2026-10-14)

✅ **Approved for all workers:**
- Implement backend features (auth, sessions, isolation, ledger, billing, now market/media)
- Test with offline fakes, real Postgres, real tests
- Open PRs to staging, merge after checks pass (no promotion to main)
- Create child issues, branches, PRs under existing parents (#282, #283, #284, #21, #16, #48, #49, #209, now #376, #377, #378)

❌ **Boundaries (do not cross):**
- Never promote staging → main (human decision)
- Never read `.env`, write real credentials, run live payments/purchases
- Never destructive DB operations, force-push, weakened tests, skipped checks
- Never SSH/firewall/DNS changes, locking out users

---

## Current blockers resolved

| Blocker | Status | When | Evidence |
|---|---|---|---|
| B-023: Market-data policy decisions | ✅ Resolved | 2026-10-16 | Owner confirmed all 727 Otodom locations, Postgres storage, nightly capture, trends in scope |
| Phase 2 (frontend) authorization | ✅ Resolved | 2026-10-15 | Owner approved #267, `.agent/agents.md` §0 updated |
| Standing backend authorization | ✅ Active | 2026-10-14 | Owner approved merging backend PRs to staging autonomously |

**No blockers remain** for Wave 1 contract/repository/test work.

---

## Next immediate steps (coordinator)

1. **Now:** Each worker clones/syncs their worktree and reads startup guide
2. **Hour 1-2:** Workers create contract files, run local tests (`uv run pytest`)
3. **Hour 2-3:** Workers open draft PRs, mark `integration pending`, fill RM-<issue>.md handoff
4. **Hour 3+:** Coordinator reviews contracts, merges latest staging into feature branches, regenerates schemas
5. **Merge:** One lane at a time once checks pass (migration slot reserved)

---

## Files to reference during implementation

| Need | Path | Scope |
|---|---|---|
| Feature-gap requirements | `docs/FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md` | §7 (media), §8 (equipment), §10 (questions), §6 (manual), §9 (interior), §5 (Rynek data) |
| Otodom data policy | `docs/OTODOM-NIGHTLY-IMPORT.md` | All-location bootstrap, nightly, recovery, trends |
| BDL contract proposal | `docs/BDL-LOCATION-CONTEXT-CONTRACT.md` | Territory hierarchy, metric definitions, comparison gates |
| Parallel work rules | `.agent/rules/parallel-work.md` | Isolation, shared-file ownership, integration process |
| Existing API structure | `services/rm_api/app.py` (lines 157-167) | How routers are registered |
| DB models | `packages/rm_core/db/models.py` | Existing table patterns, versioning |
| Latest migration | `migrations/versions/0013_audit_request_key.py` | Alembic structure and style |
| Privacy handling | `packages/rm_core/privacy.py` | Erasure, retention, export patterns |

---

## Success criteria for Wave 1

When all three workers' PRs are merged to staging:

✅ Media: Manifest persistence, foreign-key 404, versioned DealAnalysis model
✅ Otodom: Catalogue/offer models, dedup contract, checkpoint state, run cardinality
✅ BDL: Territory/metric models, pure comparison logic, coverage thresholds

No database migrations yet (Phase 2, coordinator slot). No UI changes (Phase 3+).

---

## Communication protocol

**Checkpoint format** after each worker session ends:

```
## [Worker Name] checkpoint

**Done:** [specific behavior/model/test completed, not file count]
**Checks run:** [exact command + summary line, e.g., "uv run pytest tests/integration/test_media_manifest.py -q" → "3 passed"]
**PR link:** [GitHub issue/PR number]
**Blockers:** [exact owner action needed, or "none"]
**Next:** [next concrete slice, e.g., "Phase 2: DB migration and repository persistence"]
```

Post in the related issue #376/#377/#378.

---

**Execution plan ready. Awaiting worker dispatch.**

Last update: 2026-10-17 12:30 UTC (staging: 93fb778)
