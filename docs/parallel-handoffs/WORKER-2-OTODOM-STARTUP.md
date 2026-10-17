# Worker 2: Otodom data lane startup — OTO-01 (#377)

**Assigned:** Otodom rental corpus persistence (catalogue, offer identity, dedup, coverage)  
**Worktree:** `/Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-otodom`  
**Branch:** `rm-377-otodom-corpus`  
**Base SHA:** `141c449` (RM-374 merged)

## Phase 1: Verify checkout and read acceptance

```bash
cd /Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-otodom
git status  # rm-377-otodom-corpus on 141c449
```

**From #377 acceptance:**
- Verified 727-location catalogue with versioned artifact reference
- Immutable offer corpus: source ID, location, original asking rent, area/rooms, timestamps  
- Offer deduplication with location-assignment rule, explicit coverage/empty counts
- Run/staging/checkpoint records; bootstrap readiness manifest
- Tests: retry safety, conflicting sightings, concurrency, zero-offer locations

## Phase 2: Contract models and repositories

**Existing to read first:**
- `packages/rm_core/comparables.py` → StoredComparable, ComparableSet, RentComparableRow (models, NOT Otodom-specific)
- `services/rm_worker/importers/otodom_rental.py` (existing demand importer; inspect what it does, do NOT copy)
- `services/rm_worker/clients/otodom.py` → LOCATION_PATH, fetch_rental_search (location handling, injectable client)
- `packages/rm_core/throttle.py` + `services/rm_worker/clients/otodom_policy.py` (host throttle, interactive priority)

### 2a. Catalogue and offer models in packages/rm_contracts/market.py (extend if exists)

```python
# New in packages/rm_contracts/market.py or new file if needed
from pydantic import ConfigDict, Field
from decimal import Decimal
from datetime import datetime

class OtodomLocationCatalogue(BaseModel):
    """Verified 727-location metadata."""
    model_config = ConfigDict(extra="forbid")
    catalogue_id: str  # UUID, immutable  
    source_version: int  # tracks source
    locations: list[LocationEntry]  # gmina ID, name, otodom search path
    checksum: str  # SHA-256 of sorted location list

class RentalOfferRow(BaseModel):
    """Single offer from otodom rental search; immutable once inserted."""
    model_config = ConfigDict(extra="forbid")
    source_id: str  # otodom offer ID (unique key)
    location_id: str  # gmina reference
    asking_rent_pln: Decimal  # original listing rent
    area_m2: Optional[int] = None  # parsed from listing
    rooms: Optional[int] = None
    first_seen_timestamp: datetime  # ISO 8601
    publication_timestamp: datetime  # from listing
    
class ImportCheckpoint(BaseModel):
    """Run state for bootstrap/nightly recovery."""
    run_id: str  # UUID
    location_id: str
    page_number: int
    total_pages: Optional[int] = None  # None if paginating by offset
    status: Literal["in_progress", "completed", "failed"]
    seen_offer_ids: set[str] = Field(default_factory=set)  # for dedup within run
    error: Optional[str] = None
```

**Acceptance:** pydantic validation, extra fields rejected, serialization round-trip.

### 2b. Repositories: catalogue + offer CRUD

Create packages/rm_core/repositories/market.py (new) or extend existing:

```python
class OtodomCatalogueRepository:
    async def ensure_catalogue(
        self,
        locations: list[LocationEntry],
        version: int
    ) -> OtodomLocationCatalogue:
        """Upsert or fetch existing catalogue by version."""
        
    async def get_catalogue(self, catalogue_id: str) -> Optional[OtodomLocationCatalogue]:
        """Read-only; raises 404 semantics at API level."""

class RentalOfferRepository:
    async def insert_offer(
        self,
        offer: RentalOfferRow,
        location_id: str
    ) -> RentalOfferRow:
        """Insert new offer; raise conflict if source_id exists for this location."""
        
    async def get_offers_by_location(
        self,
        location_id: str,
        limit: int = 1000
    ) -> list[RentalOfferRow]:
        """Pageable fetch."""
        
    async def get_checkpoint(self, run_id: str) -> Optional[ImportCheckpoint]:
        """Resume state."""

class ImportCheckpointRepository:
    async def upsert_checkpoint(self, checkpoint: ImportCheckpoint):
        """Persist run progress; idempotent on run_id + location."""
```

**Acceptance:** unit tests for interface signature; no Postgres yet.

### 2c. Integration tests

Create tests/integration/test_otodom_corpus.py:

```python
@pytest.mark.integration
async def test_insert_offer_new(real_postgres):
    """Insert first offer for location; succeeds."""
    
@pytest.mark.integration
async def test_insert_duplicate_source_id_raises(real_postgres):
    """Same source_id twice in same location; raises."""
    
@pytest.mark.integration
async def test_checkpoint_resume(real_postgres):
    """Save checkpoint at page 3, fetch it back, continue from page 4."""
    
@pytest.mark.integration
async def test_zero_offers_location_succeeds(real_postgres):
    """Location with no priced results; checkpoint shows zero, not failed."""
```

## Phase 3: Handoff prep

When contracts are ready:
1. Commit: `feat(RM-377a): OTO-01 corpus contracts and repositories`
2. Create PR (draft), mark `integration pending`
3. Fill docs/parallel-handoffs/RM-377.md:
   - **Done:** catalogue/offer models, offer CRUD repos, checkpoint state, cardinality/dedup tests
   - **Next:** DB migration (expand), importer slice (bootstrap logic)
   - **Blockers:** Approved Otodom catalogue artifact and location-assignment rule (B-023 resolved)
   - **Files ready:** packages/rm_contracts/market.py (extends), packages/rm_core/repositories/market.py, tests/

## Files affected (Phase 1)

- **New/Extended:** packages/rm_contracts/market.py
- **New:** packages/rm_core/repositories/market.py
- **New:** tests/integration/test_otodom_corpus.py
- **Modified:** packages/rm_core/repositories/__init__.py (export)
- **No migration yet** (reserved for Phase 2, coordinator slot)

## Legal/GDPR tags

```python
# LEGAL[scraping|third-party-data]: otodom offer fetch and corpus
```

Use in client/importer docstrings.

## Important notes

- **Do NOT copy** existing otodom_rental.py importer; read it for reference only
- **Reuse existing client:** services/rm_worker/clients/otodom.py already has location/search logic; you will call it (injectable pattern)
- **Throttle already exists:** packages/rm_core/throttle.py; integrate in Phase 2 importer
- **Catalogue versioning:** immutable once inserted; source-version tracks updates

---

**Checkpoint:** Link draft PR when created. Coordinator verifies contracts, merges staging, reserves migration slot.
