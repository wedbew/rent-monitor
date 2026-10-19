"""Rental corpus settings on real Postgres 17 with the fake Otodom search (RM-209).

Real: Postgres, `PgCorpus`, the advisory lock, the task helpers that read `Settings`. Faked: the Otodom search
(`tests/otodom_search_fake.py`, hand-built adverts, no seller data). Never fetches live.

LEGAL[scraping]: exercises the configured limits of the Otodom search importer against a fake (RM-209).
LEGAL[third-party-data]: stored fields are the whitelisted analytical ones only (RM-392).
"""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from otodom_search_fake import FakeCorpusSearch, tile
from rm_contracts.market import LocationCatalogue, LocationEntry, RunMode
from rm_core.market_corpus import PgCorpus
from rm_core.settings import Settings
from rm_worker.importers.otodom_corpus import DUE_AFTER
from rm_worker.tasks import batch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_offer, app.market_import_run, app.market_import_checkpoint,"
    " app.market_location, app.market_catalogue"
)
D0 = datetime(2026, 9, 1, 1, 10, tzinfo=UTC)  # the bootstrap night; the target floors to 01:00
A = LocationEntry(location_id="loc-a", name="Alfa", otodom_path="testowe/alfa")
B = LocationEntry(location_id="loc-b", name="Beta", otodom_path="testowe/beta")
OFF = LocationEntry(location_id="loc-off", name="Off", otodom_path="testowe/off", launch_enabled=False)
CAT1 = LocationCatalogue.build(1, "hand-built-test-catalogue", [A, B, OFF])
CAT2 = LocationCatalogue.build(2, "hand-built-test-catalogue", [A])
ALWAYS_OPEN: Callable[[], bool] = lambda: True  # noqa: E731 - the night window is tested separately


def db_settings(url: str, **overrides: Any) -> Settings:
    return Settings(_env_file=None, database_url=url, **overrides)  # type: ignore[call-arg]


def spread(first_id: int, n: int, start: datetime, step: timedelta) -> list[dict[str, Any]]:
    return [tile(first_id + i, start + step * i) for i in range(n)]


@pytest_asyncio.fixture(loop_scope="session")
async def corpus(engine: AsyncEngine) -> AsyncIterator[PgCorpus]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    repo = PgCorpus(async_sessionmaker(engine, expire_on_commit=False))
    await repo.ensure_catalogue(CAT1)
    await repo.ensure_catalogue(CAT2)
    yield repo
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def stored_ids(corpus: PgCorpus, loc: str = "loc-a") -> set[str]:
    return {o.source_offer_id for o in await corpus.list_offers(loc, limit=5000)}


@pytest.fixture
def deferred(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    async def record(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(batch.sync_corpus_location, "defer_async", record)
    return calls


async def test_dispatch_reads_the_configured_catalogue_version(
    corpus: PgCorpus, migrated_url: str, deferred: list[dict[str, object]]
) -> None:
    v1 = db_settings(migrated_url, otodom_market_catalogue_version=1)
    assert await batch.dispatch_nightly_now(v1, now=D0) == ["loc-a", "loc-b"]  # the disabled one is never due
    v2 = db_settings(migrated_url, otodom_market_catalogue_version=2)
    assert await batch.dispatch_nightly_now(v2, now=D0) == ["loc-a"]
    assert deferred[-1] == {"location_id": "loc-a", "catalogue_version": 2}
    missing = db_settings(migrated_url, otodom_market_catalogue_version=9)
    before = len(deferred)
    assert await batch.dispatch_nightly_now(missing, now=D0) == []  # no catalogue: nothing deferred
    assert len(deferred) == before


async def test_request_budget_from_settings_ends_the_run_incomplete(
    corpus: PgCorpus, migrated_url: str
) -> None:
    source = FakeCorpusSearch(spread(1000, 40, D0 - timedelta(days=30), timedelta(hours=17)))  # 10 pages
    small = db_settings(migrated_url, otodom_market_request_budget=2)
    (out,) = await batch.sync_location_now(small, "loc-a", source=source, now=D0, may_fetch=ALWAYS_OPEN)
    assert (out.state, out.error_category) == ("incomplete", "budget")
    assert len(source.calls) == 2  # the budget is a bound on requests, never a silent cut-off
    assert await corpus.get_checkpoint("loc-a") is None
    assert (
        len(await stored_ids(corpus)) == 8
    )  # two pages of four, insert-once and kept; the run is not published


async def test_overlap_from_settings_moves_the_first_catch_up_window(
    corpus: PgCorpus, migrated_url: str
) -> None:
    source = FakeCorpusSearch(spread(2000, 6, D0 - timedelta(days=3), timedelta(hours=5)), page_size=100)
    await batch.sync_location_now(
        db_settings(migrated_url), "loc-a", source=source, now=D0, may_fetch=ALWAYS_OPEN
    )
    boot = await corpus.get_checkpoint("loc-a")
    assert boot is not None
    assert boot.covered_until is not None

    source.calls.clear()
    later = D0 + DUE_AFTER + timedelta(hours=1)
    (out,) = await batch.sync_location_now(
        db_settings(migrated_url, otodom_market_overlap_minutes=15),
        "loc-a",
        source=source,
        now=later,
        may_fetch=ALWAYS_OPEN,
    )
    assert (out.mode, out.state) == (RunMode.incremental, "published")
    starts = [c[2].created_from for c in source.calls if c[2].created_from is not None]
    assert min(starts) == boot.covered_until - timedelta(minutes=15)


async def test_closed_night_window_stops_before_any_request_and_keeps_the_checkpoint(
    corpus: PgCorpus, migrated_url: str
) -> None:
    source = FakeCorpusSearch(spread(3000, 3, D0 - timedelta(days=1), timedelta(hours=1)), page_size=100)
    await batch.sync_location_now(
        db_settings(migrated_url), "loc-a", source=source, now=D0, may_fetch=ALWAYS_OPEN
    )
    before = await corpus.get_checkpoint("loc-a")
    source.calls.clear()
    source.tiles.append(tile(3100, D0 + timedelta(days=1, hours=2)))

    (out,) = await batch.sync_location_now(
        db_settings(migrated_url),
        "loc-a",
        source=source,
        now=D0 + timedelta(days=1, hours=2),
        may_fetch=lambda: False,
    )
    assert (out.state, out.error_category, out.blocked) == ("incomplete", "night_window", False)
    assert source.calls == []  # the closed window issues no request at all
    assert await corpus.get_checkpoint("loc-a") == before
    assert "3100" not in await stored_ids(corpus)


async def test_blocked_nightly_keeps_earlier_offers_unchanged_and_the_checkpoint(
    corpus: PgCorpus, migrated_url: str
) -> None:
    source = FakeCorpusSearch(spread(4000, 3, D0 - timedelta(days=1), timedelta(hours=1)), page_size=100)
    await batch.sync_location_now(
        db_settings(migrated_url), "loc-a", source=source, now=D0, may_fetch=ALWAYS_OPEN
    )
    before_cp = await corpus.get_checkpoint("loc-a")
    before_offers = {o.source_offer_id: o.asking_rent_pln for o in await corpus.list_offers("loc-a")}
    assert len(before_offers) == 3

    source.tiles.append(tile(4100, D0 + timedelta(days=1, hours=3)))
    source.fail_on_call = len(source.calls) + 1
    source.retryable = False
    (out,) = await batch.sync_location_now(
        db_settings(migrated_url),
        "loc-a",
        source=source,
        now=D0 + timedelta(days=2),
        may_fetch=ALWAYS_OPEN,
    )
    assert (out.state, out.blocked) == ("incomplete", True)
    assert await corpus.get_checkpoint("loc-a") == before_cp
    after = {o.source_offer_id: o.asking_rent_pln for o in await corpus.list_offers("loc-a")}
    assert after == before_offers  # the blocked run published nothing and changed nothing


async def test_import_switch_off_reads_nothing_and_writes_nothing(
    corpus: PgCorpus, migrated_url: str
) -> None:
    source = FakeCorpusSearch(spread(5000, 4, D0 - timedelta(days=1), timedelta(hours=1)), page_size=100)
    off = db_settings(migrated_url, otodom_market_import_enabled=False)
    assert await batch.sync_location_now(off, "loc-a", source=source, now=D0, may_fetch=ALWAYS_OPEN) == []
    assert source.calls == []
    assert await corpus.get_checkpoint("loc-a") is None
    assert await stored_ids(corpus) == set()
