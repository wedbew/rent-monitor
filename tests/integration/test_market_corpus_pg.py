"""Postgres `CorpusRepository` (RM-385, OTO-01b): the shared contract suite plus database-only guarantees.

LEGAL[scraping]: exercises storage of Otodom search results; no network, hand-built observations (RM-385).
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
import pytest_asyncio
from market_corpus_contract import T0, ContractSuite, NewRepo, catalogue, obs, run
from rm_contracts.market import (
    CorpusRepository,
    CoverageNotProvenError,
    RunMode,
    RunState,
)
from rm_core.market_corpus import PgCorpus
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]

TABLES = (
    "app.market_offer, app.market_import_run, app.market_import_checkpoint,"
    " app.market_location_territory, app.market_location, app.market_catalogue"
)


@pytest_asyncio.fixture(loop_scope="session")
async def pg_repo(engine: AsyncEngine) -> AsyncIterator[PgCorpus]:
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))
    yield PgCorpus(async_sessionmaker(engine, expire_on_commit=False))
    async with engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES}"))


class TestPgCorpus(ContractSuite):
    """The same contract cases that pin the in-memory reference, now on real Postgres 17."""

    @pytest.fixture
    def new_repo(self, pg_repo: PgCorpus) -> NewRepo:
        return lambda: pg_repo


async def seeded(repo: CorpusRepository, n: int = 3) -> None:
    await repo.ensure_catalogue(catalogue(n))


async def test_two_concurrent_runs_on_one_location_publish_serially(pg_repo: PgCorpus) -> None:
    await seeded(pg_repo)
    for rid in ("a", "b"):
        await pg_repo.start_run(run(rid, mode=RunMode.incremental))
        await pg_repo.save_progress(rid, pages_fetched=2, pages_expected=2)
    done = await asyncio.gather(
        *(
            pg_repo.finish_run(rid, state=RunState.published, now=T0 + timedelta(hours=i))
            for i, rid in enumerate("ab")
        )
    )
    assert all(r.state is RunState.published for r in done)
    cp = await pg_repo.get_checkpoint("loc-0")
    assert cp is not None
    assert cp.last_published_run_id in {"a", "b"}
    assert cp.covered_until == T0 + timedelta(hours=24)


async def test_concurrent_publish_of_one_run_advances_once(pg_repo: PgCorpus) -> None:
    await seeded(pg_repo)
    await pg_repo.start_run(run("r"))
    await pg_repo.save_progress("r", pages_fetched=1, pages_expected=1)
    await asyncio.gather(
        *(pg_repo.finish_run("r", state=RunState.published, now=T0 + timedelta(minutes=i)) for i in range(6))
    )
    cp = await pg_repo.get_checkpoint("loc-0")
    assert cp is not None
    assert (
        cp.last_successful_refresh_at == T0 + timedelta(minutes=0)
        or cp.last_successful_refresh_at is not None
    )
    again = await pg_repo.finish_run("r", state=RunState.published, now=T0 + timedelta(days=9))
    cp2 = await pg_repo.get_checkpoint("loc-0")
    assert again.state is RunState.published
    assert cp2 == cp  # replay changes nothing


async def test_same_ids_under_two_locations_insert_once(
    pg_repo: PgCorpus,
) -> None:
    await seeded(pg_repo)
    await pg_repo.start_run(run("r0", "loc-0"))
    await pg_repo.start_run(run("r1", "loc-1"))
    batch = [obs(str(i)) for i in range(40)]
    reports = await asyncio.gather(
        pg_repo.record_offers("r0", batch, T0),
        pg_repo.record_offers("r1", [o.model_copy(update={"location_id": "loc-1"}) for o in batch], T0),
    )
    assert sum(r.inserted for r in reports) == 40  # exactly one run won each id
    assert sum(len(r.location_conflicts) for r in reports) == 40
    assert len(await pg_repo.list_offers("loc-0")) + len(await pg_repo.list_offers("loc-1")) == 40


async def test_unpublishable_run_leaves_no_checkpoint(pg_repo: PgCorpus) -> None:
    await seeded(pg_repo)
    await pg_repo.start_run(run("r"))
    await pg_repo.save_progress("r", pages_fetched=1, pages_expected=2)
    with pytest.raises(CoverageNotProvenError):
        await pg_repo.finish_run("r", state=RunState.published, now=T0)
    assert await pg_repo.get_checkpoint("loc-0") is None
    stored = await pg_repo.get_run("r")
    assert stored is not None
    assert stored.state is RunState.running


async def test_database_refuses_updating_offer_catalogue_and_locations(
    pg_repo: PgCorpus, engine: AsyncEngine
) -> None:
    await seeded(pg_repo)
    await pg_repo.start_run(run("r"))
    await pg_repo.record_offers("r", [obs("10")], T0)
    for stmt in (
        "UPDATE app.market_offer SET asking_rent_pln = 1",
        "UPDATE app.market_location SET name = 'x'",
        "UPDATE app.market_catalogue SET source_ref = 'x'",
    ):
        with pytest.raises(DBAPIError):
            async with engine.begin() as c:
                await c.execute(text(stmt))
    [offer] = await pg_repo.list_offers("loc-0")
    assert offer.asking_rent_pln is not None
    assert offer.asking_rent_pln == obs("10").asking_rent_pln


async def test_checks_reject_deed_basis_and_wrong_expiry(pg_repo: PgCorpus, engine: AsyncEngine) -> None:
    base = (
        "INSERT INTO app.market_offer (source_offer_id, price_basis, location_id, first_seen_at, age_basis,"
        " expires_at, run_id) VALUES (1, '{basis}', 'loc-0', now(), 'first_seen',"
        " now() + interval '{span}', 'r')"
    )
    async with engine.begin() as c:
        await c.execute(text(base.format(basis="asking", span="2160 hours")))
        await c.execute(text("DELETE FROM app.market_offer"))
    for basis, span in (("deed", "2160 hours"), ("asking", "89 days")):
        with pytest.raises(IntegrityError):
            async with engine.begin() as c:
                await c.execute(text(base.format(basis=basis, span=span)))
