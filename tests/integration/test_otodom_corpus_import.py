"""Otodom corpus importer on real Postgres with a fake search client (RM-392, OTO-02/03).

Real: Postgres 17, `PgCorpus`, the advisory location lock, the importer. Faked, by name: the Otodom search
(`tests/otodom_search_fake.py`, hand-built tiles, no seller data) and the clock. Never fetches live and never
seeds a real catalogue; offline evidence only.

LEGAL[scraping]: exercises the paging logic of an Otodom search importer against a fake (RM-392).
LEGAL[third-party-data]: stored fields are the whitelisted analytical ones only (RM-392).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import ceil

import pytest
import pytest_asyncio
from otodom_search_fake import FakeCorpusSearch, tile
from rm_contracts.market import AgeBasis, LocationCatalogue, LocationEntry, RunMode, RunState
from rm_core.market_corpus import PgCorpus
from rm_worker.importers.otodom_corpus import (
    DAY,
    DUE_AFTER,
    OVERLAP,
    CorpusImporter,
    PgLocationLock,
    parse_search_page,
    run_nightly,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_offer, app.market_import_run, app.market_import_checkpoint,"
    " app.market_location_territory, app.market_location, app.market_catalogue"
)
D0 = datetime(2026, 9, 1, 1, 10, tzinfo=UTC)  # the bootstrap night; target floors to 01:00
A = LocationEntry(location_id="loc-a", name="Alfa", otodom_path="testowe/alfa")
B = LocationEntry(location_id="loc-b", name="Beta", otodom_path="testowe/beta")
OFF = LocationEntry(location_id="loc-off", name="Off", otodom_path="testowe/off", launch_enabled=False)
CATALOGUE = LocationCatalogue.build(1, "hand-built-test-catalogue", [A, B, OFF])  # tiny; not the 727


@pytest_asyncio.fixture(loop_scope="session")
async def corpus(engine: AsyncEngine) -> PgCorpus:  # type: ignore[misc]
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    repo = PgCorpus(async_sessionmaker(engine, expire_on_commit=False))
    await repo.ensure_catalogue(CATALOGUE)
    yield repo  # type: ignore[misc]
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


def importer(corpus: PgCorpus, source: FakeCorpusSearch, engine: AsyncEngine | None = None, **kw: object):
    return CorpusImporter(
        corpus,
        source,
        lock=PgLocationLock(engine) if engine else None,
        page_cap=3,
        **kw,  # type: ignore[arg-type]
    )


def spread(first_id: int, n: int, start: datetime, step: timedelta) -> list[dict]:
    return [tile(first_id + i, start + step * i) for i in range(n)]


async def sync_at(imp: CorpusImporter, source: FakeCorpusSearch, entry: LocationEntry, now: datetime):
    """The site's clock and the run's clock move together, as in production."""
    source.now = now
    return await imp.sync_location(entry, now=now)


async def stored_ids(corpus: PgCorpus, loc: str = "loc-a") -> set[str]:
    return {o.source_offer_id for o in await corpus.list_offers(loc, limit=5000)}


async def test_bootstrap_deeper_than_the_page_cap_is_read_from_both_ends_and_complete(
    corpus: PgCorpus,
) -> None:
    # 40 tiles, 4 per page => 10 pages, but the cap is 3: a naive loop would stop at 12 tiles.
    source = FakeCorpusSearch(spread(1000, 40, D0 - timedelta(days=30), timedelta(hours=17)))
    (out,) = await sync_at(importer(corpus, source), source, A, D0)
    assert (out.mode, out.state, out.error_category) == (RunMode.bootstrap, "published", None)
    assert await stored_ids(corpus) == {str(1000 + i) for i in range(40)}
    run = await corpus.get_run(out.run_id or "")
    assert run is not None
    assert run.coverage_complete
    assert not run.truncated
    assert run.pages_fetched == run.pages_expected == out.pages
    assert all(p <= 3 for _, p, _, _ in source.calls)  # never asked past the cap
    assert {c[2].order for c in source.calls} == {"newest", "oldest"}  # both ends, then the middle
    assert any(c[2].days_since_created for c in source.calls)  # the middle walks with the verified filter
    assert {c[3] for c in source.calls} == {"batch"}  # batch lane only
    cp = await corpus.get_checkpoint("loc-a")
    assert cp is not None
    assert cp.bootstrap_completed_at is not None
    assert cp.covered_until == datetime(2026, 9, 1, 1, 0, tzinfo=UTC)  # the frozen, hour-aligned bound


async def test_tied_overfull_window_is_truncated_never_published(corpus: PgCorpus) -> None:
    same_instant = [tile(2000 + i, D0 - timedelta(days=2)) for i in range(30)]
    source = FakeCorpusSearch(same_instant)
    (out,) = await sync_at(importer(corpus, source), source, A, D0)
    assert out.state == "incomplete"
    assert out.error_category == "coverage_not_proven"
    run = await corpus.get_run(out.run_id or "")
    assert run is not None
    assert run.truncated
    assert run.state is RunState.incomplete
    assert await corpus.get_checkpoint("loc-a") is None  # nothing claimed
    assert len(await stored_ids(corpus)) > 0  # what was read stays (insert-once), but is not published


async def test_restart_after_a_midrun_failure_reuses_the_window_and_inserts_once(corpus: PgCorpus) -> None:
    tiles = spread(3000, 20, D0 - timedelta(days=10), timedelta(hours=11))
    flaky = FakeCorpusSearch(tiles, fail_on_call=4)
    (first,) = await sync_at(importer(corpus, flaky), flaky, A, D0)
    assert (first.state, first.error_category) == ("incomplete", "upstream_blocked")
    assert not first.blocked  # a retryable failure does not stop the whole night
    assert await corpus.get_checkpoint("loc-a") is None
    partial = len(await stored_ids(corpus))
    assert 0 < partial < 20

    healthy = FakeCorpusSearch(tiles)
    (second,) = await sync_at(importer(corpus, healthy), healthy, A, D0 + timedelta(minutes=20))
    assert second.state == "published"
    assert second.run_id != first.run_id
    assert second.run_id
    assert second.run_id.endswith("-a2")
    assert len(await stored_ids(corpus)) == 20
    again = await sync_at(importer(corpus, healthy), healthy, A, D0 + timedelta(minutes=30))
    assert [o.state for o in again] == ["not_due"]  # published: nothing is redone


async def test_overlapping_runs_on_one_location_do_one_unit_of_work(
    corpus: PgCorpus, engine: AsyncEngine
) -> None:
    tiles = spread(4000, 8, D0 - timedelta(days=3), timedelta(hours=5))
    source = FakeCorpusSearch(tiles, delay_s=0.05)
    imp = importer(corpus, source, engine)
    source.now = D0
    first, second = await asyncio.gather(imp.sync_location(A, now=D0), imp.sync_location(A, now=D0))
    states = sorted(o.state for o in first + second)
    assert states == ["busy", "published"]
    assert len(await stored_ids(corpus)) == 8
    run_pages = {c[1] for c in source.calls}
    assert run_pages <= {1, 2}  # one sweep of a 2-page result, not two


async def test_missed_nights_are_caught_up_by_wider_overlapping_windows(corpus: PgCorpus) -> None:
    old = spread(5000, 6, D0 - timedelta(days=5), timedelta(hours=3))
    source = FakeCorpusSearch(old, page_size=100)
    await sync_at(importer(corpus, source), source, A, D0)
    boot = await corpus.get_checkpoint("loc-a")
    assert boot is not None
    assert boot.covered_until is not None

    # 20 days pass with no run, then a one-off tile created exactly in the overlap and new ones in the gap.
    late = D0 + timedelta(days=20)
    source.tiles += [tile(5100 + i, boot.covered_until + timedelta(days=i, hours=2)) for i in range(19)]
    source.tiles.append(tile(5200, boot.covered_until - timedelta(minutes=30)))  # inside the overlap
    outs = await sync_at(importer(corpus, source), source, A, late)
    assert next(o.mode for o in outs) is RunMode.recovery
    assert [o.state for o in outs] == ["published"]  # one wide window, not a chain of bounded chunks
    cp = await corpus.get_checkpoint("loc-a")
    assert cp is not None
    assert cp.covered_until == datetime(2026, 9, 21, 1, 0, tzinfo=UTC)
    assert cp.unresolved_gap_since is None
    ids = await stored_ids(corpus)
    assert {str(5100 + i) for i in range(19)} | {"5200"} <= ids
    first_run = await corpus.get_run(outs[0].run_id or "")
    assert first_run is not None
    assert first_run.window_start == boot.covered_until - OVERLAP  # starts before the watermark
    first_window_days = ceil((first_run.window_end - first_run.window_start) / DAY) + 1
    assert any(c[2].days_since_created == first_window_days for c in source.calls)  # verified filter only


async def test_nightly_window_is_a_normal_incremental_run_with_overlap(corpus: PgCorpus) -> None:
    source = FakeCorpusSearch(spread(6000, 3, D0 - timedelta(days=1), timedelta(hours=1)), page_size=100)
    await sync_at(importer(corpus, source), source, A, D0)
    too_early = await sync_at(importer(corpus, source), source, A, D0 + timedelta(hours=5))
    assert [o.state for o in too_early] == ["not_due"]
    source.tiles.append(tile(6100, D0 + timedelta(hours=3)))
    (out,) = await sync_at(importer(corpus, source), source, A, D0 + DUE_AFTER + timedelta(hours=1))
    assert (out.mode, out.state, out.inserted) == (RunMode.incremental, "published", 1)


async def test_valid_empty_search_is_a_complete_refresh_not_a_failure(corpus: PgCorpus) -> None:
    source = FakeCorpusSearch([], page_size=100)
    (out,) = await sync_at(importer(corpus, source), source, B, D0)
    assert (out.state, out.inserted, out.pages) == ("published", 0, 1)
    cp = await corpus.get_checkpoint("loc-b")
    assert cp is not None
    assert cp.last_successful_refresh_at is not None
    manifest = await corpus.manifest(1)
    assert "loc-b" in manifest.zero_offer_locations


@pytest.mark.parametrize(
    "bad",
    [
        {"items": [tile(1, D0)]},  # no pagination
        {"items": "x", "pagination": {"totalPages": 1}},
        {"pagination": {"totalPages": 1}},
        {"items": [], "pagination": {"totalPages": True}},
        {"items": [], "pagination": {"totalPages": -1}},
        {"items": [tile(1, D0)], "pagination": {"totalPages": 3, "currentPage": 2}},  # asked page 1
    ],
)
async def test_malformed_pages_end_incomplete_and_keep_the_prior_state(corpus: PgCorpus, bad: dict) -> None:
    fake = FakeCorpusSearch(raw_override=bad)
    (out,) = await sync_at(importer(corpus, fake), fake, A, D0)
    assert (out.state, out.error_category) == ("incomplete", "schema_drift")
    assert await corpus.get_checkpoint("loc-a") is None


async def test_failed_nightly_keeps_the_previous_checkpoint(corpus: PgCorpus) -> None:
    source = FakeCorpusSearch(spread(7000, 3, D0 - timedelta(days=1), timedelta(hours=1)), page_size=100)
    await sync_at(importer(corpus, source), source, A, D0)
    before = await corpus.get_checkpoint("loc-a")
    source.calls.clear()
    source.fail_on_call = 1
    source.retryable = False
    (out,) = await sync_at(importer(corpus, source), source, A, D0 + timedelta(days=1, hours=2))
    assert (out.state, out.blocked) == ("incomplete", True)
    assert len(source.calls) == 1  # bounded: the importer does not loop on a refusal
    assert await corpus.get_checkpoint("loc-a") == before


async def test_offers_are_insert_once_and_whitelisted(corpus: PgCorpus) -> None:
    created = D0 - timedelta(minutes=40)  # inside the next run's overlap, so it is seen twice
    t = tile(8001, created, rent=2400, area=40)
    source = FakeCorpusSearch(
        [
            t,
            tile(8002, created, hidePrice=True),
            tile(8003, created, totalPrice=None),  # only the admin fee remains: never a rent
            tile(8004, D0 + timedelta(days=9)),  # a future publication time: fallback, flagged
            tile(8005, created, estate="HOUSE"),  # not a flat: rejected
            {"id": "junk", "title": "x", "agency": {"phone": "+48000000000"}, "createdAtFirst": "?"},
        ],
        page_size=100,
    )
    imp = importer(corpus, source, clock=lambda: D0)
    await sync_at(imp, source, A, D0)
    # The seller changes the rent after we saw the advert; the next run sees the same advert again.
    source.tiles[0] = tile(8001, created, rent=9999, area=40)
    await sync_at(imp, source, A, D0 + DUE_AFTER + timedelta(hours=1))
    by_id = {o.source_offer_id: o for o in await corpus.list_offers("loc-a")}
    assert set(by_id) == {"8001", "8002", "8003", "8004"}  # house and junk never stored
    assert by_id["8001"].asking_rent_pln == Decimal("2400.00")  # never refreshed
    assert by_id["8001"].published_at == created
    assert by_id["8001"].age_basis is AgeBasis.publication
    assert by_id["8002"].asking_rent_pln is None  # hidden price kept as identity only
    assert by_id["8003"].asking_rent_pln is None
    assert by_id["8004"].source_date_issue
    assert by_id["8004"].age_basis is AgeBasis.first_seen
    assert all(o.price_basis.value == "asking" for o in by_id.values())  # invariant 2
    cols = (await corpus.list_offers("loc-a"))[0].model_dump().keys()
    assert not {"title", "agency", "phone", "seller"} & set(cols)


async def test_the_sponsored_tile_is_never_stored_as_an_offer(corpus: PgCorpus) -> None:
    """Live finding 2026-10-20: every non-empty page ends with a sponsored `hpr/` tile (synthetic id above
    9e9, date 1999, another advert's price). It is not an offer of this location."""
    source = FakeCorpusSearch(spread(1100, 6, D0 - timedelta(days=2), timedelta(hours=3)), page_size=4)
    (out,) = await sync_at(importer(corpus, source), source, A, D0)
    assert out.state == "published"
    ids = await stored_ids(corpus)
    assert ids == {str(1100 + i) for i in range(6)}
    assert "9000062237" not in ids


async def test_an_empty_location_is_covered_with_zero_offers(corpus: PgCorpus) -> None:
    """Live finding: a location without rentals answers `totalPages: 0` (not 1) and no items."""
    source = FakeCorpusSearch([], page_size=36)
    (out,) = await sync_at(importer(corpus, source), source, A, D0)
    assert (out.state, out.inserted, out.pages) == ("published", 0, 1)
    assert "loc-a" in (await corpus.manifest(1)).zero_offer_locations


async def test_a_nightly_window_stops_at_the_first_advert_older_than_its_start(corpus: PgCorpus) -> None:
    old = spread(1200, 30, D0 - timedelta(days=60), timedelta(days=1))  # a long tail of old adverts
    source = FakeCorpusSearch(old, page_size=4)
    await sync_at(importer(corpus, source), source, A, D0)
    source.tiles.append(tile(1300, D0 + timedelta(hours=3)))
    source.calls.clear()
    (out,) = await sync_at(importer(corpus, source), source, A, D0 + DUE_AFTER + timedelta(hours=1))
    assert (out.mode, out.state, out.inserted) == (RunMode.incremental, "published", 1)
    assert {c[2].order for c in source.calls} == {"newest"}
    assert all(c[2].days_since_created is not None for c in source.calls)  # always the verified filter
    assert len(source.calls) <= 2  # the old tail is not read: the first older advert ends the window


@pytest.mark.invariant
def test_invariant_admin_fee_is_never_the_corpus_rent() -> None:
    """Invariant 3: `rentPrice` is the czynsz (OPEX); only `totalPrice` is the asking rent."""
    page = {"items": [tile(1, D0, rent=2000, area=40)], "pagination": {"totalPages": 1}}
    (obs,) = parse_search_page(page, location_id="loc-a", observed_at=D0).observations
    assert obs.asking_rent_pln == Decimal(2000)
    fee_only = {"items": [tile(2, D0, totalPrice=None)], "pagination": {"totalPages": 1}}
    (obs2,) = parse_search_page(fee_only, location_id="loc-a", observed_at=D0).observations
    assert obs2.asking_rent_pln is None


async def test_nightly_skips_disabled_locations_and_stops_when_blocked(corpus: PgCorpus) -> None:
    source = FakeCorpusSearch(spread(9000, 3, D0 - timedelta(days=1), timedelta(hours=1)), page_size=100)
    imp = importer(corpus, source)
    assert await imp.due_locations(CATALOGUE, D0) == ["loc-a", "loc-b"]  # the disabled one is never due
    source.now = D0
    ok = await run_nightly(imp, CATALOGUE, now=D0)
    assert ok.stopped is None
    assert [o.location_id for o in ok.outcomes] == ["loc-a", "loc-b"]
    assert await imp.due_locations(CATALOGUE, D0 + timedelta(hours=1)) == []
    later = D0 + timedelta(days=2)
    source.now = later
    source.fail_on_call = len(source.calls) + 1
    source.retryable = False
    stopped = await run_nightly(imp, CATALOGUE, now=later)
    assert stopped.stopped == "blocked"
    assert [o.location_id for o in stopped.outcomes] == ["loc-a"]  # loc-b not attempted: no hammering
    assert await corpus.get_run("incremental-loc-b-20260903T010000Z-a1") is None
