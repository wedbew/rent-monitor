"""In-memory reference implementation of `CorpusRepository` (RM-377).

It states the semantics the Postgres repository must keep (insert-only offers, first location wins,
publish-only-with-coverage). `tests/unit/test_otodom_corpus.py` runs its contract tests against it; the
Postgres slice adds a second fixture param so the same tests run against real Postgres.
"""

import asyncio
from collections.abc import Sequence
from datetime import datetime

from rm_contracts.market import (
    BootstrapManifest,
    CatalogueConflictError,
    CoverageNotProvenError,
    ImportRun,
    LocationCatalogue,
    LocationCheckpoint,
    OfferObservation,
    RentalOffer,
    RunMode,
    RunState,
    SightingReport,
    UnknownLocationError,
    check_transition,
    offer_from_observation,
)


class InMemoryCorpus:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()  # stands in for ON CONFLICT + row locks
        self._catalogues: dict[int, LocationCatalogue] = {}
        self._runs: dict[str, ImportRun] = {}
        self._offers: dict[str, RentalOffer] = {}
        self._checkpoints: dict[str, LocationCheckpoint] = {}
        self._known_locations: set[str] = set()

    async def ensure_catalogue(self, catalogue: LocationCatalogue) -> LocationCatalogue:
        async with self._lock:
            stored = self._catalogues.get(catalogue.version)
            if stored is not None:
                if stored != catalogue:
                    raise CatalogueConflictError(f"version {catalogue.version} exists with other content")
                return stored
            self._catalogues[catalogue.version] = catalogue
            self._known_locations.update(e.location_id for e in catalogue.locations)
            return catalogue

    async def get_catalogue(self, version: int) -> LocationCatalogue | None:
        return self._catalogues.get(version)

    async def start_run(self, run: ImportRun) -> ImportRun:
        async with self._lock:
            if run.location_id not in self._known_locations:
                raise UnknownLocationError(run.location_id)
            return self._runs.setdefault(run.run_id, run)

    def _run(self, run_id: str) -> ImportRun:
        found = self._runs.get(run_id)
        if found is None:
            raise LookupError(run_id)
        return found

    async def save_progress(
        self, run_id: str, *, pages_fetched: int, pages_expected: int | None, truncated: bool = False
    ) -> ImportRun:
        async with self._lock:
            run = self._run(run_id)
            check_transition(run.state, RunState.running)
            updated = run.model_copy(
                update={
                    "state": RunState.running,
                    "pages_fetched": max(run.pages_fetched, pages_fetched),
                    "pages_expected": pages_expected if pages_expected is not None else run.pages_expected,
                    "truncated": run.truncated or truncated,
                }
            )
            self._runs[run_id] = ImportRun.model_validate(updated.model_dump())
            return self._runs[run_id]

    async def record_offers(
        self, run_id: str, observations: Sequence[OfferObservation], now: datetime
    ) -> SightingReport:
        async with self._lock:
            run = self._run(run_id)
            inserted = duplicates = unpriced = 0
            conflicts: list[str] = []
            seen: set[str] = set()
            for obs in observations:
                seen.add(obs.source_offer_id)
                existing = self._offers.get(obs.source_offer_id)
                if existing is None:
                    offer = offer_from_observation(
                        obs.model_copy(update={"location_id": run.location_id}), run_id, now
                    )
                    self._offers[obs.source_offer_id] = offer
                    inserted += 1
                    unpriced += 0 if offer.priced else 1
                elif existing.location_id == run.location_id:
                    duplicates += 1
                else:
                    conflicts.append(obs.source_offer_id)
            self._runs[run_id] = run.model_copy(
                update={
                    "observed": run.observed + len(seen),
                    "inserted": run.inserted + inserted,
                    "duplicates": run.duplicates + duplicates,
                    "location_conflicts": run.location_conflicts + len(conflicts),
                }
            )
            return SightingReport(
                inserted=inserted,
                duplicates=duplicates,
                location_conflicts=tuple(conflicts),
                unpriced=unpriced,
            )

    async def finish_run(
        self, run_id: str, *, state: RunState, now: datetime, error_category: str | None = None
    ) -> ImportRun:
        async with self._lock:
            run = self._run(run_id)
            if run.state is state and state in (RunState.published, RunState.failed):
                return run  # replay of a terminal finish is a no-op
            check_transition(run.state, state)
            if state is RunState.published:
                if not run.coverage_complete:
                    raise CoverageNotProvenError(run_id)
                self._advance_checkpoint(run, now)
            updated = run.model_copy(update={"state": state, "error_category": error_category})
            self._runs[run_id] = updated
            return updated

    def _advance_checkpoint(self, run: ImportRun, now: datetime) -> None:
        cp = self._checkpoints.get(run.location_id) or LocationCheckpoint(location_id=run.location_id)
        update: dict[str, object] = {"last_successful_refresh_at": now, "last_published_run_id": run.run_id}
        if run.mode is RunMode.bootstrap:
            update["bootstrap_completed_at"] = now
            update["covered_until"] = run.window_end
            update["unresolved_gap_since"] = None
        elif cp.covered_until is not None and run.window_start > cp.covered_until:
            # The window does not reach the watermark: keep it, make the gap visible.
            update["unresolved_gap_since"] = cp.unresolved_gap_since or cp.covered_until
        else:
            update["covered_until"] = max(cp.covered_until or run.window_end, run.window_end)
            update["unresolved_gap_since"] = None
        self._checkpoints[run.location_id] = LocationCheckpoint.model_validate(
            cp.model_copy(update=update).model_dump()
        )

    async def get_run(self, run_id: str) -> ImportRun | None:
        return self._runs.get(run_id)

    async def get_checkpoint(self, location_id: str) -> LocationCheckpoint | None:
        return self._checkpoints.get(location_id)

    async def list_offers(
        self, location_id: str, *, after_source_id: str | None = None, limit: int = 1000
    ) -> list[RentalOffer]:
        rows = sorted(
            (o for o in self._offers.values() if o.location_id == location_id),
            key=lambda o: int(o.source_offer_id),
        )
        if after_source_id is not None:
            rows = [o for o in rows if int(o.source_offer_id) > int(after_source_id)]
        return rows[: max(1, limit)]

    async def manifest(self, catalogue_version: int) -> BootstrapManifest:
        catalogue = self._catalogues.get(catalogue_version)
        if catalogue is None:
            raise LookupError(catalogue_version)
        pending: list[str] = []
        gaps: list[str] = []
        zero: list[str] = []
        for entry in catalogue.locations:
            cp = self._checkpoints.get(entry.location_id)
            if cp is None or cp.bootstrap_completed_at is None:
                pending.append(entry.location_id)
                continue
            if cp.unresolved_gap_since is not None:
                gaps.append(entry.location_id)
            if not any(o.location_id == entry.location_id for o in self._offers.values()):
                zero.append(entry.location_id)
        total = len(catalogue.locations)
        return BootstrapManifest(
            catalogue_version=catalogue_version,
            total=total,
            bootstrapped=total - len(pending),
            pending=tuple(pending),
            gaps=tuple(gaps),
            zero_offer_locations=tuple(zero),
            catalogue_complete=catalogue.complete,
        )
