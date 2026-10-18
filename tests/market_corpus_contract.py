"""Repository contract for `CorpusRepository`, run in-memory and Postgres (RM-377, RM-385).

Subclass `ContractSuite`, name it `Test...`, and provide the `new_repo` fixture: a callable that returns a
fresh, empty repository. Importing this module collects nothing by itself.
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from rm_contracts.market import (
    EXPECTED_CATALOGUE_SIZE,
    CatalogueConflictError,
    CorpusRepository,
    CoverageNotProvenError,
    DataStatus,
    ImportRun,
    InvalidRunTransitionError,
    LocationCatalogue,
    LocationEntry,
    OfferObservation,
    RunMode,
    RunState,
    UnknownLocationError,
)

NewRepo = Callable[[], CorpusRepository]

T0 = datetime(2026, 10, 17, 1, 0, tzinfo=UTC)


def entry(i: int) -> LocationEntry:
    return LocationEntry(location_id=f"loc-{i}", name=f"Place {i}", otodom_path=f"cala-polska/place-{i}")


def catalogue(n: int = 3, version: int = 1) -> LocationCatalogue:
    return LocationCatalogue.build(version, "owner-verified-2026-10-16", [entry(i) for i in range(n)])


def obs(sid: str, *, loc: str = "loc-0", rent: str | None = "2500", area: str | None = "40", **kw: object):
    return OfferObservation(
        source_offer_id=sid,
        location_id=loc,
        asking_rent_pln=Decimal(rent) if rent else None,
        area_m2=Decimal(area) if area else None,
        observed_at=T0,
        **kw,  # type: ignore[arg-type]
    )


def run(rid: str, loc: str = "loc-0", mode: RunMode = RunMode.bootstrap, start: datetime = T0) -> ImportRun:
    return ImportRun(
        run_id=rid, location_id=loc, mode=mode, window_start=start, window_end=start + timedelta(hours=24)
    )


async def seeded(new_repo: Callable[[], CorpusRepository], n: int = 3) -> CorpusRepository:
    repo = new_repo()
    await repo.ensure_catalogue(catalogue(n))
    return repo


class ContractSuite:
    async def test_catalogue_versions_are_immutable_and_idempotent(self, new_repo: NewRepo) -> None:
        repo = new_repo()
        c = catalogue(3)
        assert await repo.ensure_catalogue(c) == c
        assert await repo.ensure_catalogue(c) == c
        with pytest.raises(CatalogueConflictError):
            await repo.ensure_catalogue(catalogue(4))  # same version, other content
        assert await repo.get_catalogue(2) is None
        assert (await repo.ensure_catalogue(catalogue(4, version=2))).version == 2

    async def test_run_for_unknown_location_rejected(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        with pytest.raises(UnknownLocationError):
            await repo.start_run(run("r", loc="nope"))

    async def test_insert_offers_is_retry_safe_and_immutable(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        first = await repo.record_offers("r1", [obs("10", rent="2500"), obs("11")], T0)
        assert (first.inserted, first.duplicates) == (2, 0)
        again = await repo.record_offers("r1", [obs("10", rent="9999"), obs("11")], T0 + timedelta(days=1))
        assert (again.inserted, again.duplicates) == (0, 2)
        stored = {o.source_offer_id: o for o in await repo.list_offers("loc-0")}
        assert stored["10"].asking_rent_pln == Decimal("2500")  # a later sighting never changes rent
        assert stored["10"].first_seen_at == T0  # nor the clock

    async def test_conflicting_location_keeps_first_and_is_flagged(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1", "loc-0"))
        await repo.start_run(run("r2", "loc-1"))
        await repo.record_offers("r1", [obs("10")], T0)
        report = await repo.record_offers("r2", [obs("10", loc="loc-1"), obs("12", loc="loc-1")], T0)
        assert report.location_conflicts == ("10",)
        assert report.inserted == 1
        assert [o.source_offer_id for o in await repo.list_offers("loc-0")] == ["10"]
        assert [o.source_offer_id for o in await repo.list_offers("loc-1")] == ["12"]
        r2 = await repo.get_run("r2")
        assert r2 is not None
        assert r2.location_conflicts == 1

    async def test_concurrent_sightings_insert_once(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        await repo.start_run(run("r2"))
        reports = await asyncio.gather(
            *(repo.record_offers(rid, [obs(str(i)) for i in range(50)], T0) for rid in ("r1", "r2") * 5)
        )
        assert sum(r.inserted for r in reports) == 50
        assert len(await repo.list_offers("loc-0")) == 50

    async def test_list_offers_keyset_paging(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        await repo.record_offers("r1", [obs(str(i)) for i in (9, 100, 20, 3)], T0)
        page1 = await repo.list_offers("loc-0", limit=2)
        page2 = await repo.list_offers("loc-0", after_source_id=page1[-1].source_offer_id, limit=2)
        assert [o.source_offer_id for o in page1 + page2] == ["3", "9", "20", "100"]

    async def test_checkpoint_resume_after_interruption(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        await repo.save_progress("r1", pages_fetched=3, pages_expected=9)
        await repo.save_progress("r1", pages_fetched=2, pages_expected=None)  # never moves backwards
        resumed = await repo.get_run("r1")
        assert resumed is not None
        assert resumed.pages_fetched == 3
        assert resumed.pages_expected == 9
        assert resumed.state is RunState.running
        await repo.finish_run("r1", state=RunState.incomplete, now=T0)
        assert await repo.get_checkpoint("loc-0") is None  # prior checkpoint untouched
        await repo.save_progress("r1", pages_fetched=9, pages_expected=9)  # resume from page 4 and finish
        done = await repo.finish_run("r1", state=RunState.published, now=T0 + timedelta(hours=1))
        assert done.state is RunState.published

    async def test_publish_requires_proven_coverage(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        await repo.save_progress("r1", pages_fetched=5, pages_expected=9)
        with pytest.raises(CoverageNotProvenError):
            await repo.finish_run("r1", state=RunState.published, now=T0)
        await repo.start_run(run("r2"))
        await repo.save_progress("r2", pages_fetched=9, pages_expected=9, truncated=True)  # a cap
        with pytest.raises(CoverageNotProvenError):
            await repo.finish_run("r2", state=RunState.published, now=T0)
        assert await repo.get_checkpoint("loc-0") is None

    async def test_zero_offer_location_is_published_not_failed(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        await repo.save_progress("r1", pages_fetched=1, pages_expected=1)
        done = await repo.finish_run("r1", state=RunState.published, now=T0)
        assert done.state is RunState.published
        assert done.observed == 0
        assert done.inserted == 0
        cp = await repo.get_checkpoint("loc-0")
        assert cp is not None
        assert cp.bootstrap_completed_at == T0
        assert cp.last_successful_refresh_at == T0
        assert "loc-0" in (await repo.manifest(1)).zero_offer_locations

    async def test_publish_is_replay_safe_and_terminal(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        await repo.save_progress("r1", pages_fetched=1, pages_expected=1)
        await repo.finish_run("r1", state=RunState.published, now=T0)
        await repo.finish_run("r1", state=RunState.published, now=T0 + timedelta(hours=5))  # replay: no-op
        cp = await repo.get_checkpoint("loc-0")
        assert cp is not None
        assert cp.last_successful_refresh_at == T0
        with pytest.raises(InvalidRunTransitionError):
            await repo.save_progress("r1", pages_fetched=1, pages_expected=1)

    async def test_incremental_gap_is_visible_and_watermark_kept(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("boot"))
        await repo.save_progress("boot", pages_fetched=1, pages_expected=1)
        await repo.finish_run("boot", state=RunState.published, now=T0)
        boot_end = T0 + timedelta(hours=24)
        # A window that starts after the watermark leaves 15 minutes uncovered.
        late = run("inc", mode=RunMode.incremental, start=boot_end + timedelta(minutes=15))
        await repo.start_run(late)
        await repo.save_progress("inc", pages_fetched=1, pages_expected=1)
        await repo.finish_run("inc", state=RunState.published, now=boot_end + timedelta(hours=1))
        cp = await repo.get_checkpoint("loc-0")
        assert cp is not None
        assert cp.covered_until == boot_end
        assert cp.unresolved_gap_since == boot_end
        assert cp.data_status(boot_end + timedelta(hours=2)) is DataStatus.stale
        assert (await repo.manifest(1)).gaps == ("loc-0",)
        # A recovery window overlapping the watermark closes the gap.
        rec = run("rec", mode=RunMode.recovery, start=boot_end - timedelta(hours=1))
        await repo.start_run(rec)
        await repo.save_progress("rec", pages_fetched=1, pages_expected=1)
        await repo.finish_run("rec", state=RunState.published, now=boot_end + timedelta(hours=3))
        healed = await repo.get_checkpoint("loc-0")
        assert healed is not None
        assert healed.unresolved_gap_since is None
        assert healed.covered_until == rec.window_end

    async def test_manifest_ready_only_when_all_727_locations_bootstrapped(self, new_repo: NewRepo) -> None:
        repo = new_repo()
        full = LocationCatalogue.build(1, "x", [entry(i) for i in range(EXPECTED_CATALOGUE_SIZE)])
        await repo.ensure_catalogue(full)
        m = await repo.manifest(1)
        assert m.total == 727
        assert m.bootstrapped == 0
        assert not m.ready
        for i in range(EXPECTED_CATALOGUE_SIZE):
            rid = f"b{i}"
            await repo.start_run(run(rid, f"loc-{i}"))
            await repo.save_progress(rid, pages_fetched=1, pages_expected=1)
            if i < EXPECTED_CATALOGUE_SIZE - 1:
                await repo.finish_run(rid, state=RunState.published, now=T0)
        assert not (await repo.manifest(1)).ready
        assert len((await repo.manifest(1)).pending) == 1
        await repo.finish_run(f"b{EXPECTED_CATALOGUE_SIZE - 1}", state=RunState.published, now=T0)
        assert (await repo.manifest(1)).ready

    async def test_partial_catalogue_is_never_ready(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo, 2)
        for i in range(2):
            await repo.start_run(run(f"b{i}", f"loc-{i}"))
            await repo.save_progress(f"b{i}", pages_fetched=1, pages_expected=1)
            await repo.finish_run(f"b{i}", state=RunState.published, now=T0)
        m = await repo.manifest(1)
        assert m.bootstrapped == 2
        assert not m.pending
        assert not m.ready

    async def test_terminal_run_accepts_no_offers(self, new_repo: NewRepo) -> None:
        repo = await seeded(new_repo)
        await repo.start_run(run("r1"))
        await repo.save_progress("r1", pages_fetched=1, pages_expected=1)
        await repo.finish_run("r1", state=RunState.published, now=T0)
        with pytest.raises(InvalidRunTransitionError):
            await repo.record_offers("r1", [obs("10")], T0)
        assert await repo.list_offers("loc-0") == []
