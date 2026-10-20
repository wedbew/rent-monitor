"""Postgres repository for BDL location context: reference, observations, ingestion cursor, publication.

LEGAL[third-party-data]: persists GUS BDL statistics and administrative identifiers; source terms and
attribution are unreviewed (B-023, B-012). It fetches nothing (RM-391).
GDPR[retention]: no personal data; annual statistics are kept as history, nothing here is per person (RM-391).

Semantics (the tests run them on real Postgres 17):
- the territorial reference is an immutable, checksummed version; asking for the same version with other
  content raises instead of overwriting;
- observations are insert-once on `(metric, version, territory, year)`; a later row with the same digest is a
  duplicate, one with another digest is a counted conflict and never replaces the first fact;
- an ingestion run is a deterministic id; its page cursor and that page's observations commit in ONE
  transaction, guarded by a lease, so a crash resumes at the first unsaved page and two workers never both
  write;
- publication fails closed (B-023): a release needs a complete run, a policy with every threshold decided
  and a passed gate; otherwise nothing changes and the previous pointer stays valid.
Every method is its own short transaction; none is held across network I/O.
"""

import hashlib
import json
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from rm_contracts.location_context import (
    MetricDefinition,
    Observation,
    ObservationStatus,
    PublicationPolicy,
    TerritoryLevel,
    TerritoryRef,
)
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import (
    LocationIngestRun,
    LocationObservation,
    LocationPublication,
    LocationPublicationPointer,
    LocationReference,
    LocationTerritory,
)
from rm_core.location_contracts import (
    CoverageBelowThresholdError,
    LocationContractError,
    TerritoryHierarchy,
    rank_territories,
    require_publishable,
)

RunState = Literal["planned", "running", "incomplete", "complete", "failed"]
MAX_PAGE = 10_000


INSERT_CHUNK = 2000  # rows per INSERT: 2,000 x ~9 columns stays far below PostgreSQL's 65,535 parameters


class ReferenceConflictError(LocationContractError):
    """The reference version exists with other content."""


class RunNotFoundError(LookupError):
    pass


class LeaseLostError(RuntimeError):
    """The caller no longer holds the run's lease (expired and taken, or never held)."""


class PageOutOfOrderError(RuntimeError):
    """A page beyond the saved cursor: a page would be skipped."""


class RunStateError(RuntimeError):
    """The run is in a state that does not allow this call (e.g. complete or failed)."""


class NotPublishableError(LocationContractError):
    """Publication refused: run incomplete, policy undecided or gate failed. Nothing was changed."""


def reference_checksum(territories: Collection[TerritoryRef]) -> str:
    """Order-independent SHA-256 of the full reference content."""
    rows = sorted(
        (t.model_dump(mode="json") for t in territories), key=lambda r: (r["level"], r["territory_id"])
    )
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run_id_for(variable_id: str, unit_level: int, years: Sequence[int], reference_version: int) -> str:
    key = json.dumps([variable_id, unit_level, sorted(set(years)), reference_version])
    return hashlib.sha256(key.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class IngestRun:
    run_id: str
    variable_id: str
    unit_level: int
    years: tuple[int, ...]
    reference_version: int
    metric_key: str
    metric_version: int
    state: RunState
    next_page: int
    observed: int
    inserted: int
    duplicates: int
    conflicts: int
    lease_owner: str | None
    error_category: str | None


@dataclass(frozen=True)
class PageReport:
    inserted: int
    duplicates: int
    conflicts: int
    replayed: bool = False


@dataclass(frozen=True)
class PublicationRelease:
    release_id: str
    metric_key: str
    metric_version: int
    year: int
    reference_version: int
    run_id: str
    expected: int
    eligible: int


def _run(row: LocationIngestRun) -> IngestRun:
    return IngestRun(
        run_id=row.run_id,
        variable_id=row.variable_id,
        unit_level=row.unit_level,
        years=tuple(row.years),
        reference_version=row.reference_version,
        metric_key=row.metric_key,
        metric_version=row.metric_version,
        state=cast(RunState, row.state),  # CHECKed vocabulary
        next_page=row.next_page,
        observed=row.observed,
        inserted=row.inserted,
        duplicates=row.duplicates,
        conflicts=row.conflicts,
        lease_owner=row.lease_owner,
        error_category=row.error_category,
    )


def _territory(row: LocationTerritory) -> TerritoryRef:
    return TerritoryRef(
        territory_id=row.territory_id,
        teryt=row.teryt,
        name=row.name,
        level=TerritoryLevel(row.level),
        parent_id=row.parent_id,
        has_powiat_rights=row.has_powiat_rights,
    )


def _observation(row: LocationObservation) -> Observation:
    return Observation(
        territory_id=row.territory_id,
        metric_key=row.metric_key,
        metric_version=row.metric_version,
        year=row.year,
        status=ObservationStatus(row.status),
        value=row.value,
        reason=row.reason,
        source_digest=row.source_digest,
    )


def _obs_values(o: Observation, run_id: str) -> dict[str, object]:
    return {
        "metric_key": o.metric_key,
        "metric_version": o.metric_version,
        "territory_id": o.territory_id,
        "year": o.year,
        "status": o.status.value,
        "value": o.value,
        "reason": o.reason,
        "source_digest": o.source_digest,
        "run_id": run_id,
    }


class PgLocationRepo:
    """Session-factory based; each call commits its own transaction."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    # --- territorial reference -------------------------------------------------------------------

    async def ensure_reference(
        self, version: int, source_ref: str, territories: Sequence[TerritoryRef]
    ) -> str:
        """Store the reference once. Returns its checksum; the same content again is a no-op."""
        TerritoryHierarchy(territories)  # validates ids, TERYT uniqueness and one-level-up parents
        checksum = reference_checksum(territories)
        async with self._sessions() as s, s.begin():
            inserted = await s.scalar(
                insert(LocationReference)
                .values(version=version, source_ref=source_ref, checksum=checksum)
                .on_conflict_do_nothing(index_elements=[LocationReference.version])
                .returning(LocationReference.version)
            )
            if inserted is not None:
                await s.execute(
                    insert(LocationTerritory),
                    [
                        {
                            "reference_version": version,
                            "territory_id": t.territory_id,
                            "teryt": t.teryt,
                            "name": t.name,
                            "level": t.level.value,
                            "parent_id": t.parent_id,
                            "has_powiat_rights": t.has_powiat_rights,
                        }
                        for t in territories
                    ],
                )
                return checksum
            stored = await s.get_one(LocationReference, version)
        if stored.checksum != checksum:
            raise ReferenceConflictError(f"reference {version} exists with other content")
        return checksum

    async def get_reference(self, version: int) -> tuple[TerritoryRef, ...] | None:
        async with self._sessions() as s:
            if await s.get(LocationReference, version) is None:
                return None
            rows = (
                await s.scalars(
                    select(LocationTerritory)
                    .where(LocationTerritory.reference_version == version)
                    .order_by(LocationTerritory.level, LocationTerritory.territory_id)
                )
            ).all()
            return tuple(_territory(r) for r in rows)

    # --- ingestion runs --------------------------------------------------------------------------

    async def start_run(
        self,
        *,
        variable_id: str,
        unit_level: int,
        years: Sequence[int],
        reference_version: int,
        metric_key: str,
        metric_version: int,
    ) -> IngestRun:
        """Create the run for this exact request, or return the one that exists (idempotent)."""
        rid = run_id_for(variable_id, unit_level, years, reference_version)
        async with self._sessions() as s, s.begin():
            await s.execute(
                insert(LocationIngestRun)
                .values(
                    run_id=rid,
                    variable_id=variable_id,
                    unit_level=unit_level,
                    years=sorted(set(years)),
                    reference_version=reference_version,
                    metric_key=metric_key,
                    metric_version=metric_version,
                )
                .on_conflict_do_nothing(index_elements=[LocationIngestRun.run_id])
            )
            return _run(await s.get_one(LocationIngestRun, rid))

    async def get_run(self, run_id: str) -> IngestRun:
        async with self._sessions() as s:
            row = await s.get(LocationIngestRun, run_id)
            if row is None:
                raise RunNotFoundError(run_id)
            return _run(row)

    async def claim_run(self, run_id: str, owner: str, lease_s: float) -> IngestRun | None:
        """Take the lease if it is free or expired. None = another worker holds it or the run is finished."""
        async with self._sessions() as s, s.begin():
            row = await s.scalar(
                update(LocationIngestRun)
                .where(
                    LocationIngestRun.run_id == run_id,
                    LocationIngestRun.state.in_(("planned", "running", "incomplete")),
                    (LocationIngestRun.lease_owner.is_(None))
                    | (LocationIngestRun.lease_expires_at < func.now())
                    | (LocationIngestRun.lease_owner == owner),
                )
                .values(
                    state="running",
                    lease_owner=owner,
                    lease_expires_at=func.now() + func.make_interval(0, 0, 0, 0, 0, 0, float(lease_s)),
                    error_category=None,
                    updated_at=func.now(),
                )
                .returning(LocationIngestRun)
            )
            return _run(row) if row is not None else None

    async def _held(self, s: AsyncSession, run_id: str, owner: str) -> LocationIngestRun:
        row = await s.scalar(
            select(LocationIngestRun).where(LocationIngestRun.run_id == run_id).with_for_update()
        )
        if row is None:
            raise RunNotFoundError(run_id)
        if row.state in ("complete", "failed"):
            raise RunStateError(f"run is {row.state}")
        expired = await s.scalar(select(row.lease_expires_at < func.now())) if row.lease_expires_at else True
        if row.lease_owner != owner or expired:
            raise LeaseLostError(run_id)
        return row

    async def record_page(
        self,
        run_id: str,
        owner: str,
        *,
        page_index: int,
        observations: Sequence[Observation],
        lease_s: float,
    ) -> PageReport:
        """Save one page's observations and advance the cursor, atomically, under the lease.

        A page before the cursor is a replay and a no-op (idempotent); one after it would skip data.
        """
        async with self._sessions() as s, s.begin():
            row = await self._held(s, run_id, owner)
            if page_index < row.next_page:
                return PageReport(0, 0, 0, replayed=True)
            if page_index > row.next_page or page_index >= MAX_PAGE:
                raise PageOutOfOrderError(f"page {page_index} but cursor is {row.next_page}")
            report = await self._insert_observations(s, run_id, observations)
            row.next_page = page_index + 1
            row.observed += len(observations)
            row.inserted += report.inserted
            row.duplicates += report.duplicates
            row.conflicts += report.conflicts
            row.lease_expires_at = func.now() + func.make_interval(0, 0, 0, 0, 0, 0, float(lease_s))
            row.updated_at = func.now()
            return report

    async def _insert_observations(
        self, s: AsyncSession, run_id: str, observations: Sequence[Observation]
    ) -> PageReport:
        distinct = {(o.metric_key, o.metric_version, o.territory_id, o.year): o for o in observations}
        if not distinct:
            return PageReport(0, 0, 0)
        ordered = [distinct[k] for k in sorted(distinct)]  # stable lock order across workers
        inserted: set[tuple[str, int, str, int]] = set()
        # One statement carries at most 65,535 bound parameters: a whole national cohort over ten years
        # (gap rows of a finished run) is ~25,000 rows, so insert in chunks.
        for start in range(0, len(ordered), INSERT_CHUNK):
            chunk = ordered[start : start + INSERT_CHUNK]
            inserted |= {
                (m, v, t, y)
                for m, v, t, y in await s.execute(
                    insert(LocationObservation)
                    .values([_obs_values(o, run_id) for o in chunk])
                    .on_conflict_do_nothing()
                    .returning(
                        LocationObservation.metric_key,
                        LocationObservation.metric_version,
                        LocationObservation.territory_id,
                        LocationObservation.year,
                    )
                )
            }
        duplicates = conflicts = 0
        stale = sorted(distinct.keys() - inserted)
        for start in range(0, len(stale), INSERT_CHUNK):
            keys = stale[start : start + INSERT_CHUNK]
            stored = {
                (r.metric_key, r.metric_version, r.territory_id, r.year): r.source_digest
                for r in (
                    await s.execute(
                        select(
                            LocationObservation.metric_key,
                            LocationObservation.metric_version,
                            LocationObservation.territory_id,
                            LocationObservation.year,
                            LocationObservation.source_digest,
                        ).where(
                            tuple_(
                                LocationObservation.metric_key,
                                LocationObservation.metric_version,
                                LocationObservation.territory_id,
                                LocationObservation.year,
                            ).in_(keys)
                        )
                    )
                ).all()
            }
            for key in keys:
                if stored[key] == distinct[key].source_digest:
                    duplicates += 1
                else:
                    conflicts += 1  # the source changed its mind: first fact stays, the conflict is counted
        return PageReport(len(inserted), duplicates, conflicts)

    async def complete_run(
        self, run_id: str, owner: str, *, gap_observations: Sequence[Observation]
    ) -> IngestRun:
        """Add typed `missing` rows for expected cells the source never returned, then mark complete."""
        async with self._sessions() as s, s.begin():
            row = await self._held(s, run_id, owner)
            # Gap rows only fill cells nobody wrote; an existing fact is never compared or counted here.
            distinct = {(o.territory_id, o.year): o for o in gap_observations}
            keys = sorted(distinct)
            for start in range(
                0, len(keys), INSERT_CHUNK
            ):  # a national cohort over ten years is ~25,000 rows
                filled = await s.scalars(
                    insert(LocationObservation)
                    .values([_obs_values(distinct[k], run_id) for k in keys[start : start + INSERT_CHUNK]])
                    .on_conflict_do_nothing()
                    .returning(LocationObservation.territory_id)
                )
                row.inserted += len(filled.all())
            row.state = "complete"
            row.lease_owner = None
            row.lease_expires_at = None
            row.error_category = None
            row.updated_at = func.now()
            await s.flush()
            return _run(row)

    async def release_run(
        self, run_id: str, owner: str, *, state: Literal["incomplete", "failed"], error_category: str
    ) -> IngestRun:
        """Give the lease back. `incomplete` can be resumed; `failed` is terminal and never publishable."""
        async with self._sessions() as s, s.begin():
            row = await self._held(s, run_id, owner)
            row.state = state
            row.lease_owner = None
            row.lease_expires_at = None
            row.error_category = error_category[:64]
            row.updated_at = func.now()
            await s.flush()
            return _run(row)

    # --- observations ----------------------------------------------------------------------------

    async def observations(self, metric_key: str, metric_version: int, year: int) -> tuple[Observation, ...]:
        async with self._sessions() as s:
            rows = (
                await s.scalars(
                    select(LocationObservation)
                    .where(
                        LocationObservation.metric_key == metric_key,
                        LocationObservation.metric_version == metric_version,
                        LocationObservation.year == year,
                    )
                    .order_by(LocationObservation.territory_id)
                )
            ).all()
            return tuple(_observation(r) for r in rows)

    async def observations_for_years(
        self, metric_key: str, metric_version: int, years: Collection[int]
    ) -> tuple[Observation, ...]:
        """Read-only: every stored row of one metric version for the given years (RM-396)."""
        if not years:
            return ()
        async with self._sessions() as s:
            rows = (
                await s.scalars(
                    select(LocationObservation)
                    .where(
                        LocationObservation.metric_key == metric_key,
                        LocationObservation.metric_version == metric_version,
                        LocationObservation.year.in_(sorted(set(years))),
                    )
                    .order_by(LocationObservation.year, LocationObservation.territory_id)
                )
            ).all()
            return tuple(_observation(r) for r in rows)

    # --- publication -----------------------------------------------------------------------------

    async def publish(
        self,
        run_id: str,
        *,
        defn: MetricDefinition,
        policy: PublicationPolicy | None,
        year: int,
    ) -> PublicationRelease:
        """Create an immutable release and move the pointer to it; fail closed otherwise (B-023).

        Refused (nothing written, the previous pointer stays valid) when the run is not `complete`, no
        policy exists, a threshold is undecided, or coverage is below it.
        """
        run = await self.get_run(run_id)
        if run.state != "complete":
            raise NotPublishableError(f"run is {run.state}, not complete")
        if (run.metric_key, run.metric_version) != (defn.key, defn.version) or year not in run.years:
            raise NotPublishableError("run does not cover this metric version and year")
        if policy is None:
            raise NotPublishableError("no publication policy is decided for this metric (B-023)")
        reference = await self.get_reference(run.reference_version)
        if reference is None:  # pragma: no cover  (FK guarantees it)
            raise NotPublishableError("reference vanished")
        hierarchy = TerritoryHierarchy(reference)
        cohort = [t.territory_id for t in reference if t.level is defn.native_level]
        in_cohort = set(cohort)
        # Published parent aggregates (powiat, voivodeship, country) are stored next to the native rows as
        # context; they never take part in the native ranking or its coverage gate.
        observations = tuple(
            o for o in await self.observations(defn.key, defn.version, year) if o.territory_id in in_cohort
        )
        ranking = rank_territories(
            defn, hierarchy, observations, year=year, expected=cohort, cohort_id=defn.native_level.value
        )
        try:
            gate = require_publishable(policy, defn, ranking)
        except CoverageBelowThresholdError as exc:
            raise NotPublishableError(str(exc)) from exc
        assert policy.min_coverage is not None  # noqa: S101  (a passed gate has both thresholds)
        assert policy.min_cohort_size is not None  # noqa: S101
        release_id = hashlib.sha256(
            json.dumps([defn.key, defn.version, year, run_id, str(policy.min_coverage)]).encode()
        ).hexdigest()[:32]
        async with self._sessions() as s, s.begin():
            await s.execute(
                insert(LocationPublication)
                .values(
                    release_id=release_id,
                    metric_key=defn.key,
                    metric_version=defn.version,
                    year=year,
                    reference_version=run.reference_version,
                    run_id=run_id,
                    expected=gate.expected,
                    eligible=gate.eligible,
                    policy_min_coverage=policy.min_coverage,
                    policy_min_cohort_size=policy.min_cohort_size,
                )
                .on_conflict_do_nothing(index_elements=[LocationPublication.release_id])
            )
            stmt = insert(LocationPublicationPointer).values(
                metric_key=defn.key, metric_version=defn.version, year=year, release_id=release_id
            )
            await s.execute(
                stmt.on_conflict_do_update(
                    index_elements=["metric_key", "metric_version", "year"],
                    set_={"release_id": stmt.excluded.release_id, "updated_at": func.now()},
                )
            )
        return PublicationRelease(
            release_id=release_id,
            metric_key=defn.key,
            metric_version=defn.version,
            year=year,
            reference_version=run.reference_version,
            run_id=run_id,
            expected=gate.expected,
            eligible=gate.eligible,
        )

    async def current_release(
        self, metric_key: str, metric_version: int, year: int
    ) -> PublicationRelease | None:
        async with self._sessions() as s:
            row = await s.scalar(
                select(LocationPublication)
                .join(
                    LocationPublicationPointer,
                    LocationPublicationPointer.release_id == LocationPublication.release_id,
                )
                .where(
                    LocationPublicationPointer.metric_key == metric_key,
                    LocationPublicationPointer.metric_version == metric_version,
                    LocationPublicationPointer.year == year,
                )
            )
            if row is None:
                return None
            return PublicationRelease(
                release_id=row.release_id,
                metric_key=row.metric_key,
                metric_version=row.metric_version,
                year=row.year,
                reference_version=row.reference_version,
                run_id=row.run_id,
                expected=row.expected,
                eligible=row.eligible,
            )


__all__ = [
    "IngestRun",
    "LeaseLostError",
    "NotPublishableError",
    "PageOutOfOrderError",
    "PageReport",
    "PgLocationRepo",
    "PublicationRelease",
    "ReferenceConflictError",
    "RunNotFoundError",
    "RunStateError",
    "reference_checksum",
    "run_id_for",
]
