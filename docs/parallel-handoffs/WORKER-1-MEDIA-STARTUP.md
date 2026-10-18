# Worker 1: Media lane startup — G-01a (#376)

> Historical first-slice assignment; #381 has merged. Do not restart these commands. Use the
> [completion prompt](../CLAUDE-FEATURE-GAP-FINISH-PROMPT.md) to assign current follow-up work.

**Assigned:** media foundation (manifest persistence, API route, Postgres identity)  
**Worktree:** `/Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-media`  
**Branch:** `rm-376-media-foundation`  
**Base SHA:** `141c449` (RM-374 merged)

## Phase 1: Verify checkout and read acceptance

```bash
cd /Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-media
git status  # should show branch rm-376-media-foundation on 141c449
git log --oneline -3  # confirm base
```

**Read acceptance from #376 issue:**
- Manifest: audit → media items with stable ID, ordinal, source type, download state, digest
- Postgres persistence of metadata within current architecture; bounded binary storage BETA option spec
- Versioned DealAnalysis media model with validated cardinality (25 photos + 2 plans max)
- Real-Postgres journey: manifest create/retrieve, foreign ID 404, serialization round-trip
- Partial failures and expired media explicit

## Phase 2: Contract files first (no DB change yet)

**Order:** Types → Contracts → Repositories → API route (defer: migration, worker pipeline, UI)

### 2a. Typed models in packages/rm_contracts/media.py (NEW)

Create new file with:
```python
from pydantic import ConfigDict, Field
from decimal import Decimal
from datetime import datetime
from typing import Optional

class MediaManifestItem(BaseModel):
    media_id: str  # opaque UUID, stable across serialization
    ordinal: int  # position in submission (0-indexed)
    source_type: Literal["url", "manual", "upload"]  # NOT just "photo" vs "plan"
    state: Literal["pending", "downloaded", "ocr_done", "failed"]
    content_digest: str  # SHA-256 of prepared bytes (not original)
    dimensions: Optional[tuple[int, int]] = None  # (height, width) after orient/decode
    mime: Literal["image/jpeg", "image/png", "image/webp"]
    
class MediaManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_id: str
    items: list[MediaManifestItem]
    created_at: datetime
    versions: list[int] = [1]  # schema versions seen
```

**Acceptance:** unit test + pydantic validation; test extra fields rejected.

### 2b. Repository interface in packages/rm_core/repositories/media.py (NEW)

```python
from typing import Optional
from packages.rm_contracts.media import MediaManifest, MediaManifestItem
from packages.rm_core.legal import LegalTag

class MediaRepository:
    async def persist_manifest(
        self, 
        audit_id: str, 
        items: list[MediaManifestItem],
        legal_tags: list[LegalTag] = None
    ) -> MediaManifest:
        """Persist a manifest without storing binary blobs yet."""
    
    async def get_manifest(self, audit_id: str, principal: Principal) -> Optional[MediaManifest]:
        """Retrieve manifest; foreign audit returns None, not exception."""
        
    async def validate_cardinality(self, items: list) -> bool:
        """25 photos + 2 plans max. Return True or raise ValidationError."""
```

**Acceptance:** signature-only interface, no Postgres yet, unit tests for signature.

### 2c. Integration test skeleton

Create tests/integration/test_media_manifest.py:
```python
@pytest.mark.integration
async def test_media_manifest_persist_and_retrieve(real_postgres):
    # Use fake manifest, persist via repo, retrieve, round-trip
    
@pytest.mark.integration
async def test_foreign_audit_returns_none():
    # Tenant A creates manifest for audit #1
    # Tenant B requests audit #1's manifest → None (not 403)
    
@pytest.mark.integration  
async def test_cardinality_24_photos_2_plans_accepted():
    # 24 photos + 2 plans pass

@pytest.mark.integration
async def test_cardinality_25_photos_1_plan_rejected():
    # 25 photos + 1 plan fails
```

**Acceptance:** real Postgres fixture, tenant isolation test, cardinality enforcement.

## Phase 3: Handoff prep

When contracts + tests are ready (no migration yet):
1. Commit: `feat(RM-376a): media contracts and repository interface`
2. Create PR (draft, title `feat(RM-376): media foundation — Phase 1 contracts`)
3. Mark `integration pending`
4. Fill `docs/parallel-handoffs/RM-376.md` with:
   - **Done:** media models, manifest contract, repository interface, cardinality tests (unit + integration)
   - **Next:** DB migration, persistence seam, API route
   - **Blockers:** Approved storage/retention policy for binary BETA option (record in same PR)
   - **Files ready:** packages/rm_contracts/media.py, packages/rm_core/repositories/media.py, tests/integration/test_media_manifest.py

## Files affected (Phase 1)

- **New:** packages/rm_contracts/media.py
- **New:** packages/rm_core/repositories/media.py
- **New:** tests/integration/test_media_manifest.py
- **Modified:** packages/rm_core/repositories/__init__.py (export MediaRepository)
- **No Postgres changes yet** (migration deferred to Phase 2, coordinator slot)

## Legal/GDPR tags

```python
# LEGAL[images]: photo/plan manifest and identity store
# GDPR[retention|personal-data|erasure]: media lifecycle
```

Use in file docstrings and storage decisions.

---

**Checkpoint:** Send link to draft PR when created. Coordinator will verify contracts, merge latest staging, then reserve migration slot for Phase 2.
