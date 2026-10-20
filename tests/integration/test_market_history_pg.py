"""Daily asking-rent summaries on real Postgres (RM-395, OTO-04).

LEGAL[third-party-data]: hand-built asking figures through the corpus repository; no network (RM-395).
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from deal_analyzer.market_stats import summarise_asking
from market_corpus_contract import catalogue, obs, run
from rm_contracts.market import DataStatus, OfferObservation, RunMode, RunState
from rm_core.market_corpus import PgCorpus
from rm_core.market_history import ALL, PgMarketHistory
from rm_core.settings import Settings
from rm_worker.tasks.batch import publish_summaries_now
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_daily_summary, app.market_offer, app.market_import_run, app.market_import_checkpoint,"
    " app.market_location_territory, app.market_location, app.market_catalogue"
)
BOOT = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
TODAY = NOW.date()


@pytest_asyncio.fixture(loop_scope="session")
async def stores(engine: AsyncEngine) -> AsyncIterator[tuple[PgCorpus, PgMarketHistory]]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    sm = async_sessionmaker(engine, expire_on_commit=False)
    corpus = PgCorpus(sm)
    await corpus.ensure_catalogue(catalogue(3))
    yield corpus, PgMarketHistory(sm)
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


async def ingest(
    corpus: PgCorpus,
    rid: str,
    observations: list[OfferObservation],
    *,
    seen: datetime,
    mode: RunMode = RunMode.bootstrap,
    publish: bool = True,
    loc: str = "loc-0",
    start: datetime | None = None,
) -> None:
    await corpus.start_run(run(rid, loc, mode, start=start or seen - timedelta(hours=24)))
    await corpus.save_progress(rid, pages_fetched=1, pages_expected=1)
    await corpus.record_offers(rid, observations, seen)
    if publish:
        await corpus.finish_run(rid, state=RunState.published, now=seen)


def priced(start: int, n: int) -> list[OfferObservation]:
    return [obs(str(start + i), rent=str(2000 + 10 * i), area="40", rooms=2) for i in range(n)]


async def count_rows(engine: AsyncEngine) -> int:
    async with engine.connect() as c:
        return int(await c.scalar(text("SELECT count(*) FROM app.market_daily_summary")) or 0)


async def test_bootstrap_pending_publishes_nothing(
    stores: tuple[PgCorpus, PgMarketHistory], engine: AsyncEngine
) -> None:
    _, history = stores
    res = await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    assert res.status == "bootstrap_pending"
    assert await count_rows(engine) == 0
    view = await history.view("loc-0", now=NOW)
    assert view.data_status is DataStatus.unavailable
    assert view.cohort == ()
    assert not view.usable_for_ranking


async def test_valid_empty_bootstrap_publishes_a_zero_day(stores: tuple[PgCorpus, PgMarketHistory]) -> None:
    corpus, history = stores
    await ingest(corpus, "b", [], seen=BOOT)
    res = await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    assert (res.status, res.rows) == ("published", 2)
    view = await history.view("loc-0", now=NOW)
    (row,) = view.cohort
    assert (row.observed_count, row.priced_count, row.sufficient, row.median_ppm2) == (0, 0, False, None)
    assert view.data_status is DataStatus.stale  # refreshed 9 days ago
    assert not view.usable_for_ranking


async def test_cohort_and_additions_stay_separate_and_asking_only(
    stores: tuple[PgCorpus, PgMarketHistory],
) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 12), seen=BOOT)  # 12 priced, first seen at bootstrap
    seen = NOW - timedelta(hours=2)
    late = [obs("500", published_at=NOW - timedelta(days=5), rent="3000", area="50", rooms=3)]
    fresh = [obs("501", rent="2500", area="50", rooms=3)]
    await ingest(corpus, "n", late + fresh, seen=seen, mode=RunMode.incremental, start=BOOT)
    await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)

    view = await history.view("loc-0", now=NOW)
    assert view.data_status is DataStatus.fresh
    by_key = {o.cohort_key: o for o in view.cohort}
    assert by_key[ALL].observed_count == 14
    assert by_key[ALL].sufficient
    assert view.usable_for_ranking
    assert by_key["rooms_3"].observed_count == 2
    assert all(o.price_basis == "asking" and o.series == "cohort" for o in view.cohort)

    (today_row,) = await history.history("loc-0", "additions", TODAY, TODAY)
    assert today_row.observed_count == 1  # only the offer whose source date is today
    assert today_row.first_observed_count == 2  # the late-published one was first observed today too
    assert today_row.series == "additions"


async def test_unpublished_run_offers_are_ignored(stores: tuple[PgCorpus, PgMarketHistory]) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 3), seen=BOOT)
    await ingest(
        corpus, "bad", priced(100, 5), seen=NOW - timedelta(hours=2), mode=RunMode.incremental, publish=False
    )
    await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    view = await history.view("loc-0", now=NOW)
    assert next(o for o in view.cohort if o.cohort_key == ALL).observed_count == 3


async def test_expiry_applies_without_maintenance(stores: tuple[PgCorpus, PgMarketHistory]) -> None:
    corpus, history = stores
    old = [obs("1", published_at=BOOT - timedelta(days=89), rent="2000", area="40", rooms=2)]
    await ingest(corpus, "b", old, seen=BOOT)  # expires 1 day after BOOT
    await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    view = await history.view("loc-0", now=NOW)
    assert next(o for o in view.cohort if o.cohort_key == ALL).observed_count == 0


async def test_rerun_is_idempotent_and_summaries_are_immutable(
    stores: tuple[PgCorpus, PgMarketHistory], engine: AsyncEngine
) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 11), seen=BOOT)
    first = await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    n = await count_rows(engine)
    await ingest(corpus, "n", priced(900, 4), seen=NOW - timedelta(hours=1), mode=RunMode.incremental)
    again = await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    assert (first.status, again.status) == ("published", "already_published")
    assert await count_rows(engine) == n  # the published day never changes
    async with engine.begin() as c:
        with pytest.raises(DBAPIError):
            await c.execute(text("UPDATE app.market_daily_summary SET observed_count = 0"))


async def test_two_concurrent_publishers_publish_once(
    stores: tuple[PgCorpus, PgMarketHistory], engine: AsyncEngine
) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 12), seen=BOOT)
    results = await asyncio.gather(
        *(history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking) for _ in range(6))
    )
    assert sorted(r.status for r in results).count("published") == 1
    assert [r.status for r in results].count("already_published") == 5
    assert await count_rows(engine) == next(r.rows for r in results if r.status == "published")


async def test_deed_basis_cannot_be_stored(
    stores: tuple[PgCorpus, PgMarketHistory], engine: AsyncEngine
) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 2), seen=BOOT)
    await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    async with engine.begin() as c:
        # the immutable trigger fires on UPDATE only; INSERT of a deed row hits the CHECK
        with pytest.raises(IntegrityError):
            await c.execute(
                text(
                    "INSERT INTO app.market_daily_summary (location_id, dataset, summary_date, series,"
                    " cohort_key, calc_version, price_basis, as_of, observed_count, priced_count,"
                    " sufficient, input_digest)"
                    " VALUES ('x','otodom_rental','2026-01-01','cohort','all',1,'deed', now(), 0, 0, false,"
                    " repeat('a', 64))"
                )
            )


async def test_gap_makes_the_view_stale_and_delay_is_labelled(
    stores: tuple[PgCorpus, PgMarketHistory],
) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 12), seen=BOOT)
    # an incremental window that does not reach the watermark leaves a visible gap
    await corpus.start_run(run("gap", "loc-0", RunMode.incremental, start=BOOT + timedelta(days=3)))
    await corpus.save_progress("gap", pages_fetched=1, pages_expected=1)
    await corpus.finish_run("gap", state=RunState.published, now=NOW - timedelta(hours=1))
    cp = await corpus.get_checkpoint("loc-0")
    assert cp is not None
    assert cp.unresolved_gap_since is not None
    view = await history.view("loc-0", now=NOW)
    assert view.data_status is DataStatus.stale
    assert not view.usable_for_ranking
    await history.publish_day("loc-0", TODAY, now=NOW, summarise=summarise_asking)
    (row,) = await history.history("loc-0", "cohort", TODAY, TODAY)
    assert row.sufficient  # evidence is fine; the status, not the sample, flags the gap
    delayed = await history.view("loc-0", now=NOW + timedelta(hours=40))
    assert delayed.data_status is DataStatus.stale  # gap persists


async def test_delayed_then_fresh_without_gap(stores: tuple[PgCorpus, PgMarketHistory]) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 12), seen=NOW - timedelta(hours=40))
    assert (await history.view("loc-0", now=NOW)).data_status is DataStatus.delayed
    await ingest(
        corpus,
        "n",
        [],
        seen=NOW - timedelta(hours=1),
        mode=RunMode.incremental,
        start=NOW - timedelta(hours=40),
    )
    assert (await history.view("loc-0", now=NOW)).data_status is DataStatus.fresh


async def test_backfill_publishes_past_days_but_not_before_bootstrap(
    stores: tuple[PgCorpus, PgMarketHistory],
) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 11), seen=BOOT)
    day = BOOT.date()
    out = await history.backfill(
        "loc-0", day - timedelta(days=2), day + timedelta(days=2), now=NOW, summarise=summarise_asking
    )
    assert out[day - timedelta(days=1)].status == "before_bootstrap"
    assert out[day].status == "published"
    assert out[day + timedelta(days=2)].status == "published"
    rows = await history.history("loc-0", "cohort", day, day + timedelta(days=2))
    assert [r.backfilled for r in rows] == [True, True, True]
    assert all(r.observed_count == 11 for r in rows)
    again = await history.backfill("loc-0", day, day, now=NOW, summarise=summarise_asking)
    assert again[day].status == "already_published"
    with pytest.raises(ValueError, match="past days"):
        await history.backfill("loc-0", day, TODAY, now=NOW, summarise=summarise_asking)


async def test_publish_all_isolates_failures(stores: tuple[PgCorpus, PgMarketHistory]) -> None:
    corpus, history = stores
    await ingest(corpus, "b", priced(1, 2), seen=BOOT)
    calls = {"n": 0}

    def flaky(values: object) -> object:
        calls["n"] += 1
        raise RuntimeError("boom")

    results = await history.publish_all(
        ["loc-0", "loc-1"],
        TODAY,
        now=NOW,
        summarise=flaky,  # type: ignore[arg-type]
    )
    assert isinstance(results["loc-0"], RuntimeError)
    assert getattr(results["loc-1"], "status", None) == "bootstrap_pending"


async def test_publish_task_respects_the_kill_switch_and_missing_catalogue() -> None:
    off = Settings(_env_file=None, otodom_market_import_enabled=False)  # type: ignore[call-arg]
    assert await publish_summaries_now(off, NOW) == {"published": 0, "skipped": 0, "failed": 0}


async def test_history_range_is_bounded(stores: tuple[PgCorpus, PgMarketHistory]) -> None:
    _, history = stores
    with pytest.raises(ValueError, match="at most 400"):
        await history.history("loc-0", "cohort", date(2024, 1, 1), date(2026, 1, 1))
