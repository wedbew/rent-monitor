# Worker 3: BDL data lane startup — LCTX-01 (#378)

> Historical first-slice assignment; #380 has merged contracts/pure logic, not a BDL dataset.
> Exact publication policy remains partly undecided in B-023. Use the
> [completion prompt](../CLAUDE-FEATURE-GAP-FINISH-PROMPT.md) to assign current follow-up work.

**Assigned:** BDL territory and metric validation (hierarchy, approved metrics, comparisons)  
**Worktree:** `/Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-bdl`  
**Branch:** `rm-378-bdl-metrics`  
**Base SHA:** `141c449` (RM-374 merged)

## Phase 1: Verify checkout and read acceptance

```bash
cd /Users/marcin/Projects/rent-monitor/.claude/worktrees/worker-bdl
git status  # rm-378-bdl-metrics on 141c449
```

**From #378 acceptance:**
- Validated B-023 selected metrics: names, units, grains, coverage thresholds  
- Territory hierarchy with SIMC/TERYT references (read-only from GUS)
- Typed metric/observation models with provenance and publish gates
- Pure comparison/ranking logic in own module
- Unit tests: metric bounds, missing/conflicting data, publication thresholds

## Phase 2: Contract models and pure logic

**Existing to read first:**
- `packages/rm_core/db/models.py` → MarketSidecar (line 674) — existing market data structure
- `services/rm_worker/context.py` → MarketContext class (how market data flows to audit engine)
- `docs/BDL-LOCATION-CONTEXT-CONTRACT.md` → detailed metric/territory/ranking specs (REQUIRED READ)

### 2a. BDL territory and metric models in packages/rm_contracts/market.py (extend)

```python
from pydantic import ConfigDict, Field
from decimal import Decimal
from datetime import datetime
from typing import Optional, Literal

class TerritoryNode(BaseModel):
    """gmina/powiat/województwo hierarchy."""
    model_config = ConfigDict(extra="forbid")
    simc_id: str  # SIMC code for gmina, or custom for powiat/województwo
    name: str
    level: Literal["gmina", "powiat", "wojewodztwo"]
    parent_simc: Optional[str] = None  # parent gmina (powiat) or powiat (wojewodztwo)
    
class MetricDefinition(BaseModel):
    """Approved BDL metric specification (from B-023 decision)."""
    model_config = ConfigDict(extra="forbid")
    metric_id: str  # "supply_density", "rent_ratio", etc. (owner-approved list)
    name_pl: str
    unit: str  # "/km²", "%", "zł", etc.
    grain: Literal["gmina", "powiat", "wojewodztwo"]
    coverage_threshold: float  # min % of territories with data
    publication_threshold: Optional[float] = None  # suppress if below threshold
    version: int = 1
    
class Observation(BaseModel):
    """Single metric value for a territory in a period."""
    model_config = ConfigDict(extra="forbid")
    simc_id: str
    metric_id: str
    value: Decimal
    period: str  # "2026-10" or "2026-Q3"
    sample_count: Optional[int] = None
    status: Literal["measured", "estimated", "withheld", "missing"]  # explicit gaps
    source_digest: str  # SHA-256 of raw input (GUS data version)
```

**Acceptance:** pydantic validation, grain/threshold consistency checks (unit tests).

### 2b. Pure BDL logic module

Create packages/rm_core/market/bdl.py:

```python
from packages.rm_contracts.market import MetricDefinition, Observation
from decimal import Decimal

class BDLComparator:
    """Pure comparison logic; no DB, no I/O."""
    
    def __init__(self, metrics: dict[str, MetricDefinition]):
        self.metrics = metrics  # approved metrics by ID
        
    def rank_territories(
        self,
        metric_id: str,
        observations: list[Observation],
        include_withheld: bool = False
    ) -> list[tuple[str, Decimal, int]]:
        """
        Rank territories by metric value.
        Returns: [(simc_id, value, rank), ...]
        Withheld/missing excluded unless include_withheld=True.
        """
        
    def compare_periods(
        self,
        metric_id: str,
        simc_id: str,
        period_a: str,
        period_b: str,
        observations: list[Observation]
    ) -> Optional[dict]:
        """
        Compare metric for same territory across two periods.
        Returns: {"period_a": value, "period_b": value, "change": pct, ...}
        """
```

**Acceptance:** unit tests for ranking (ties, missing, bounds), period comparison, metric validation.

### 2c. Integration tests

Create tests/unit/test_bdl_metrics.py (unit, not integration, no DB):

```python
@pytest.mark.unit
def test_rank_territories_by_supply_density():
    """Rank 5 gminas by supply_density; return ordered list."""
    
@pytest.mark.unit
def test_rank_excludes_withheld_by_default():
    """If one gmina has status='withheld', exclude from ranking."""
    
@pytest.mark.unit
def test_compare_periods_calculates_change():
    """2025-10 vs 2026-10 observations; compute % change."""
    
@pytest.mark.unit
def test_coverage_threshold_check():
    """If only 40% of gminas have data but threshold is 50%, raise."""
```

## Phase 3: Handoff prep

When models and logic are ready:
1. Commit: `feat(RM-378a): LCTX-01 territory/metric models and comparison logic`
2. Create PR (draft), mark `integration pending`
3. Fill docs/parallel-handoffs/RM-378.md:
   - **Done:** TerritoryNode, MetricDefinition, Observation, pure comparator logic, unit tests
   - **Next:** DB models/migration (expand), ingestion seam, API contracts
   - **Blockers:** B-023 approved metrics list and reference/attribution policy (owner resolved)
   - **Files ready:** packages/rm_contracts/market.py (extends), packages/rm_core/market/bdl.py, tests/unit/test_bdl_metrics.py

## Files affected (Phase 1)

- **New/Extended:** packages/rm_contracts/market.py (add TerritoryNode, MetricDefinition, Observation)
- **New:** packages/rm_core/market/bdl.py (pure comparison logic)
- **New:** tests/unit/test_bdl_metrics.py
- **No migration or DB yet** (reserved for Phase 2, coordinator slot)

## Legal/GDPR tags

```python
# LEGAL[third-party-data]: BDL territory hierarchy and metric source (GUS)
# GDPR[processor]: metric data ingestion from external source
```

Use in module docstrings and in the ingestion seam (Phase 2).

## Important constraint

**This is pure logic, not ingestion.** Your Phase 1 slot is contract + unit tests. BDL source data fetch, Postgres ingestion and API publication happen in later wave phases with coordinator coordination. Do not attempt to fetch real GUS data yet.

## Reference

Read before starting:
- `docs/BDL-LOCATION-CONTEXT-CONTRACT.md` (22 metric candidates, hierarchy, approval gates)
- `docs/CONTEXT.md` §6 (BDL hot-spots and LEGAL tags)
- B-023 blocker note (owner-resolved metric/territory decisions 2026-10-16)

---

**Checkpoint:** Link draft PR when created. Coordinator verifies logic, merges staging, reserves migration slot for Phase 2.
