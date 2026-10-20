"""Postgres implementation of `rm_contracts.market.CorpusRepository` (RM-385, OTO-01b).

LEGAL[scraping]: persists what a later importer fetched from Otodom search pages; fetches nothing (RM-385).
LEGAL[third-party-data]: asking rents of third-party adverts, kept for analysis, not re-published (RM-385).
GDPR[personal-data]: only whitelisted analytical fields reach the database; no seller columns (RM-385).

Semantics match `tests/market_corpus_fake.py` (the contract suite runs against both):
- offers are insert-once on `(source, source_offer_id)` with `ON CONFLICT DO NOTHING`; a later sighting never
  changes content, and a sighting under another location is counted as a conflict (first assignment wins);
- `finish_run(published)` locks the run row and then the checkpoint row and advances the watermark in the
  same transaction, so two runs on one location publish one after the other;
- every method is its own short transaction; none is held across I/O.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from rm_contracts.market import (
    BootstrapManifest,
    CatalogueConflictError,
    CoverageNotProvenError,
    ImportRun,
    InvalidRunTransitionError,
    LocationCatalogue,
    LocationCheckpoint,
    LocationEntry,
    OfferObservation,
    RentalOffer,
    RunState,
    SightingReport,
    UnknownLocationError,
    advance_checkpoint,
    check_transition,
    offer_from_observation,
)
from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import (
    MarketCatalogue,
    MarketDistrict,
    MarketImportCheckpoint,
    MarketImportRun,
    MarketLocation,
    MarketOffer,
    MarketOfferDistrict,
    MarketOfferRooms,
)

DATASET = "otodom_rental"
MAX_LIST = 5000


def _run(row: MarketImportRun) -> ImportRun:
    return ImportRun.model_validate(
        {
            "run_id": row.run_id,
            "location_id": row.location_id,
            "mode": row.mode,
            "window_start": row.window_start,
            "window_end": row.window_end,
            "state": row.state,
            "pages_expected": row.pages_expected,
            "pages_fetched": row.pages_fetched,
            "truncated": row.truncated,
            "observed": row.observed,
            "inserted": row.inserted,
            "duplicates": row.duplicates,
            "location_conflicts": row.location_conflicts,
            "error_category": row.error_category,
        }
    )


def _checkpoint(row: MarketImportCheckpoint) -> LocationCheckpoint:
    return LocationCheckpoint(
        location_id=row.location_id,
        bootstrap_completed_at=row.bootstrap_completed_at,
        covered_until=row.covered_until,
        unresolved_gap_since=row.unresolved_gap_since,
        last_successful_refresh_at=row.last_successful_refresh_at,
        last_published_run_id=row.last_published_run_id,
    )


def _offer(row: MarketOffer) -> RentalOffer:
    return RentalOffer(
        source=row.source,
        source_offer_id=str(int(row.source_offer_id)),
        location_id=row.location_id,
        asking_rent_pln=row.asking_rent_pln,
        area_m2=row.area_m2,
        rooms=row.rooms,
        published_at=row.published_at,
        first_seen_at=row.first_seen_at,
        age_basis=row.age_basis,  # type: ignore[arg-type]  # validated by the model
        expires_at=row.expires_at,
        source_date_issue=row.source_date_issue,
        run_id=row.run_id,
    )


class PgCorpus:
    """`CorpusRepository` on Postgres. Takes a session factory; each call commits its own transaction."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    # --- catalogue -------------------------------------------------------------------------------

    async def _load_catalogue(self, s: AsyncSession, version: int) -> LocationCatalogue | None:
        head = await s.get(MarketCatalogue, version)
        if head is None:
            return None
        rows = (
            await s.scalars(
                select(MarketLocation)
                .where(MarketLocation.catalogue_version == version)
                .order_by(MarketLocation.position)
            )
        ).all()
        return LocationCatalogue(
            version=head.version,
            source_ref=head.source_ref,
            checksum=head.checksum,
            locations=tuple(
                LocationEntry(
                    location_id=r.location_id,
                    name=r.name,
                    otodom_path=r.otodom_path,
                    launch_enabled=r.launch_enabled,
                )
                for r in rows
            ),
        )

    async def ensure_catalogue(self, catalogue: LocationCatalogue) -> LocationCatalogue:
        async with self._sessions() as s, s.begin():
            inserted = await s.scalar(
                insert(MarketCatalogue)
                .values(
                    version=catalogue.version, source_ref=catalogue.source_ref, checksum=catalogue.checksum
                )
                .on_conflict_do_nothing(index_elements=[MarketCatalogue.version])
                .returning(MarketCatalogue.version)
            )
            if inserted is not None:
                await s.execute(
                    insert(MarketLocation),
                    [
                        {
                            "catalogue_version": catalogue.version,
                            "location_id": e.location_id,
                            "position": i,
                            "name": e.name,
                            "otodom_path": e.otodom_path,
                            "launch_enabled": e.launch_enabled,
                        }
                        for i, e in enumerate(catalogue.locations)
                    ],
                )
                return catalogue
            stored = await self._load_catalogue(s, catalogue.version)
        if stored is None:  # pragma: no cover  (the version row exists: the insert conflicted with it)
            raise LookupError(catalogue.version)
        if stored != catalogue:
            raise CatalogueConflictError(f"version {catalogue.version} exists with other content")
        return stored

    async def get_catalogue(self, version: int) -> LocationCatalogue | None:
        async with self._sessions() as s:
            return await self._load_catalogue(s, version)

    # --- runs ------------------------------------------------------------------------------------

    async def start_run(self, run: ImportRun) -> ImportRun:
        async with self._sessions() as s, s.begin():
            known = await s.scalar(
                select(MarketLocation.location_id)
                .where(MarketLocation.location_id == run.location_id)
                .limit(1)
            )
            if known is None:
                raise UnknownLocationError(run.location_id)
            await s.execute(
                insert(MarketImportRun)
                .values(
                    run_id=run.run_id,
                    location_id=run.location_id,
                    mode=run.mode.value,
                    window_start=run.window_start,
                    window_end=run.window_end,
                    state=run.state.value,
                    pages_expected=run.pages_expected,
                    pages_fetched=run.pages_fetched,
                    truncated=run.truncated,
                )
                .on_conflict_do_nothing(index_elements=[MarketImportRun.run_id])
            )
            return _run(await s.get_one(MarketImportRun, run.run_id))

    async def _locked_run(self, s: AsyncSession, run_id: str) -> MarketImportRun:
        row = await s.scalar(
            select(MarketImportRun).where(MarketImportRun.run_id == run_id).with_for_update()
        )
        if row is None:
            raise LookupError(run_id)
        return row

    async def save_progress(
        self, run_id: str, *, pages_fetched: int, pages_expected: int | None, truncated: bool = False
    ) -> ImportRun:
        async with self._sessions() as s, s.begin():
            row = await self._locked_run(s, run_id)
            check_transition(RunState(row.state), RunState.running)
            row.state = RunState.running.value
            row.pages_fetched = max(row.pages_fetched, pages_fetched)
            if pages_expected is not None:
                row.pages_expected = pages_expected
            row.truncated = row.truncated or truncated
            row.updated_at = func.now()
            await s.flush()
            return _run(row)  # validates the bounds before the transaction commits

    async def record_offers(
        self, run_id: str, observations: Sequence[OfferObservation], now: datetime
    ) -> SightingReport:
        async with self._sessions() as s, s.begin():
            # The row lock orders this call against finish_run on the same run; offers still insert
            # concurrently across runs (the unique key decides who wins).
            row = await self._locked_run(s, run_id)
            if RunState(row.state) in (RunState.published, RunState.failed):
                raise InvalidRunTransitionError(f"{row.state} run accepts no offers")
            distinct = {o.source_offer_id: o for o in observations}
            offers = [
                offer_from_observation(o.model_copy(update={"location_id": row.location_id}), run_id, now)
                for o in sorted(distinct.values(), key=lambda o: int(o.source_offer_id))
            ]
            inserted_ids: set[int] = set()
            if offers:
                inserted_ids = {
                    int(i)
                    for i in await s.scalars(
                        insert(MarketOffer)
                        .values([_offer_values(o) for o in offers])
                        .on_conflict_do_nothing(index_elements=["source", "source_offer_id"])
                        .returning(MarketOffer.source_offer_id)
                    )
                }
            rest = [int(o.source_offer_id) for o in offers if int(o.source_offer_id) not in inserted_ids]
            await self._attach_districts(s, row.location_id, observations, inserted_ids)
            owner: dict[int, str] = {}
            if rest:
                found = await s.execute(
                    select(MarketOffer.source_offer_id, MarketOffer.location_id).where(
                        MarketOffer.source == "otodom", MarketOffer.source_offer_id.in_(rest)
                    )
                )
                owner = {int(i): loc for i, loc in found}
            duplicates = sum(1 for i in rest if owner.get(i) == row.location_id)
            conflicts = tuple(str(i) for i in rest if owner.get(i) != row.location_id)
            unpriced = sum(1 for o in offers if int(o.source_offer_id) in inserted_ids and not o.priced)
            row.observed += len(distinct)
            row.inserted += len(inserted_ids)
            row.duplicates += duplicates
            row.location_conflicts += len(conflicts)
            row.updated_at = func.now()
            return SightingReport(
                inserted=len(inserted_ids),
                duplicates=duplicates,
                location_conflicts=conflicts,
                unpriced=unpriced,
            )

    async def _attach_districts(
        self,
        s: AsyncSession,
        location_id: str,
        observations: Sequence[OfferObservation],
        fresh_ids: set[int],
    ) -> int:
        """Store the district of every observation whose offer belongs to `location_id`. The offer is read
        first, so a conflicting place or an unknown id attaches nothing; the offer row is never touched."""
        await self._attach_rooms(s, location_id, observations)
        wanted = {
            int(o.source_offer_id): o
            for o in observations
            if o.district_id is not None and o.district_name is not None
        }
        if not wanted:
            return 0
        mine = {
            int(i)
            for i in await s.scalars(
                select(MarketOffer.source_offer_id).where(
                    MarketOffer.source == "otodom",
                    MarketOffer.location_id == location_id,
                    MarketOffer.source_offer_id.in_([Decimal(i) for i in wanted]),
                )
            )
        } | (fresh_ids & wanted.keys())
        chosen = {i: o for i, o in wanted.items() if i in mine}
        if not chosen:
            return 0
        names = {o.district_id: o.district_name for o in chosen.values()}
        await s.execute(
            insert(MarketDistrict)
            .values([{"location_id": location_id, "district_id": d, "name": n} for d, n in names.items()])
            .on_conflict_do_nothing(index_elements=["location_id", "district_id"])
        )
        attached = await s.scalars(
            insert(MarketOfferDistrict)
            .values(
                [
                    {
                        "source": "otodom",
                        "source_offer_id": Decimal(i),
                        "location_id": location_id,
                        "district_id": o.district_id,
                    }
                    for i, o in sorted(chosen.items())
                ]
            )
            .on_conflict_do_nothing(index_elements=["source", "source_offer_id"])
            .returning(MarketOfferDistrict.source_offer_id)
        )
        return len(attached.all())

    async def district_counts(self, location_id: str) -> dict[str, tuple[str, int]]:
        async with self._sessions() as s:
            rows = await s.execute(
                select(
                    MarketDistrict.district_id,
                    MarketDistrict.name,
                    func.count(MarketOfferDistrict.source_offer_id),
                )
                .join(
                    MarketOfferDistrict,
                    (MarketOfferDistrict.location_id == MarketDistrict.location_id)
                    & (MarketOfferDistrict.district_id == MarketDistrict.district_id),
                    isouter=True,
                )
                .where(MarketDistrict.location_id == location_id)
                .group_by(MarketDistrict.district_id, MarketDistrict.name)
            )
            return {d: (n, int(c)) for d, n, c in rows}

    async def _attach_rooms(
        self, s: AsyncSession, location_id: str, observations: Sequence[OfferObservation]
    ) -> None:
        """Store the room count for offers of this place that were stored without one. Insert-once."""
        counted = {int(o.source_offer_id): o.rooms for o in observations if o.rooms is not None}
        if not counted:
            return
        missing = (
            await s.scalars(
                select(MarketOffer.source_offer_id).where(
                    MarketOffer.source == "otodom",
                    MarketOffer.location_id == location_id,
                    MarketOffer.rooms.is_(None),
                    MarketOffer.source_offer_id.in_([Decimal(i) for i in counted]),
                )
            )
        ).all()
        if not missing:
            return
        await s.execute(
            insert(MarketOfferRooms)
            .values(
                [
                    {"source": "otodom", "source_offer_id": Decimal(i), "rooms": counted[int(i)]}
                    for i in missing
                ]
            )
            .on_conflict_do_nothing(index_elements=["source", "source_offer_id"])
        )

    async def record_districts(
        self, location_id: str, observations: Sequence[OfferObservation], now: datetime
    ) -> int:
        async with self._sessions() as s, s.begin():
            return await self._attach_districts(s, location_id, observations, set())

    async def finish_run(
        self, run_id: str, *, state: RunState, now: datetime, error_category: str | None = None
    ) -> ImportRun:
        async with self._sessions() as s, s.begin():
            row = await self._locked_run(s, run_id)
            current = RunState(row.state)
            if current is state and state in (RunState.published, RunState.failed):
                return _run(row)  # replay of a terminal finish is a no-op
            check_transition(current, state)
            run = _run(row)
            if state is RunState.published:
                if not run.coverage_complete:
                    raise CoverageNotProvenError(run_id)
                # Lock order is always run then checkpoint, so concurrent publishes cannot deadlock.
                await s.execute(
                    insert(MarketImportCheckpoint)
                    .values(location_id=row.location_id, dataset=DATASET)
                    .on_conflict_do_nothing(index_elements=["location_id", "dataset"])
                )
                cp_row = await s.scalar(
                    select(MarketImportCheckpoint)
                    .where(
                        MarketImportCheckpoint.location_id == row.location_id,
                        MarketImportCheckpoint.dataset == DATASET,
                    )
                    .with_for_update()
                )
                assert cp_row is not None  # noqa: S101  (inserted above, locked here)
                after = advance_checkpoint(_checkpoint(cp_row), run, now)
                await s.execute(
                    update(MarketImportCheckpoint)
                    .where(
                        MarketImportCheckpoint.location_id == row.location_id,
                        MarketImportCheckpoint.dataset == DATASET,
                    )
                    .values(
                        bootstrap_completed_at=after.bootstrap_completed_at,
                        covered_until=after.covered_until,
                        unresolved_gap_since=after.unresolved_gap_since,
                        last_successful_refresh_at=after.last_successful_refresh_at,
                        last_published_run_id=after.last_published_run_id,
                    )
                )
            row.state = state.value
            row.error_category = error_category
            row.updated_at = func.now()
            await s.flush()
            return _run(row)

    async def get_run(self, run_id: str) -> ImportRun | None:
        async with self._sessions() as s:
            row = await s.get(MarketImportRun, run_id)
            return None if row is None else _run(row)

    async def get_checkpoint(self, location_id: str) -> LocationCheckpoint | None:
        async with self._sessions() as s:
            row = await s.get(MarketImportCheckpoint, (location_id, DATASET))
            return None if row is None else _checkpoint(row)

    # --- reads -----------------------------------------------------------------------------------

    async def list_offers(
        self, location_id: str, *, after_source_id: str | None = None, limit: int = 1000
    ) -> list[RentalOffer]:
        query = select(MarketOffer).where(MarketOffer.location_id == location_id)
        if after_source_id is not None:
            query = query.where(MarketOffer.source_offer_id > Decimal(int(after_source_id)))
        query = query.order_by(MarketOffer.source_offer_id).limit(min(max(1, limit), MAX_LIST))
        async with self._sessions() as s:
            return [_offer(r) for r in (await s.scalars(query)).all()]

    async def manifest(self, catalogue_version: int) -> BootstrapManifest:
        async with self._sessions() as s:
            catalogue = await self._load_catalogue(s, catalogue_version)
            if catalogue is None:
                raise LookupError(catalogue_version)
            has_offer = exists().where(MarketOffer.location_id == MarketLocation.location_id)
            rows = await s.execute(
                select(
                    MarketLocation.location_id,
                    MarketImportCheckpoint.bootstrap_completed_at,
                    MarketImportCheckpoint.unresolved_gap_since,
                    has_offer,
                )
                .select_from(MarketLocation)
                .outerjoin(
                    MarketImportCheckpoint,
                    (MarketImportCheckpoint.location_id == MarketLocation.location_id)
                    & (MarketImportCheckpoint.dataset == DATASET),
                )
                .where(MarketLocation.catalogue_version == catalogue_version)
                .order_by(MarketLocation.position)
            )
            pending: list[str] = []
            gaps: list[str] = []
            zero: list[str] = []
            for location_id, bootstrapped_at, gap_since, any_offer in rows:
                if bootstrapped_at is None:
                    pending.append(location_id)
                    continue
                if gap_since is not None:
                    gaps.append(location_id)
                if not any_offer:
                    zero.append(location_id)
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


def _offer_values(o: RentalOffer) -> dict[str, object]:
    return {
        "source": o.source,
        "source_offer_id": Decimal(int(o.source_offer_id)),
        "price_basis": o.price_basis.value,
        "location_id": o.location_id,
        "asking_rent_pln": o.asking_rent_pln,
        "area_m2": o.area_m2,
        "rooms": o.rooms,
        "published_at": o.published_at,
        "first_seen_at": o.first_seen_at,
        "age_basis": o.age_basis.value,
        "expires_at": o.expires_at,
        "source_date_issue": o.source_date_issue,
        "run_id": o.run_id,
    }
