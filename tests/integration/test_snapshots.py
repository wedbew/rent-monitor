"""6-hour cross-tenant snapshot sharing keyed by (otodom_id, content hash)."""

import asyncio

import pytest
from rm_core.db.models import ListingSnapshot
from rm_core.snapshots import FetchedListing, content_hash, find_fresh_snapshot, store_snapshot
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.integration]


def fetched(otodom_id: str = "ID4SNAP1", **ad: object) -> FetchedListing:
    payload = {"id": 1, **ad}
    return FetchedListing(
        otodom_id, f"https://www.otodom.pl/pl/oferta/{otodom_id}", payload, content_hash(payload)
    )


async def test_store_is_idempotent_for_identical_content(session: AsyncSession) -> None:
    a = await store_snapshot(session, fetched(title="Flat"))
    b = await store_snapshot(session, fetched(title="Flat"))
    assert a == b
    assert await session.scalar(select(func.count()).select_from(ListingSnapshot)) == 1


async def test_changed_content_creates_a_new_snapshot_and_latest_wins(session: AsyncSession) -> None:
    a = await store_snapshot(session, fetched(title="Flat"))
    await session.execute(text("UPDATE app.listing_snapshot SET fetched_at = now() - interval '1 hour'"))
    b = await store_snapshot(session, fetched(title="Flat, price dropped"))
    assert a != b
    assert await find_fresh_snapshot(session, "ID4SNAP1") == b


async def test_snapshot_older_than_six_hours_is_not_shared(session: AsyncSession) -> None:
    sid = await store_snapshot(session, fetched())
    assert await find_fresh_snapshot(session, "ID4SNAP1") == sid
    await session.execute(
        text("UPDATE app.listing_snapshot SET fetched_at = now() - interval '6 hours 1 minute'")
    )
    assert await find_fresh_snapshot(session, "ID4SNAP1") is None
    assert await find_fresh_snapshot(session, "ID4OTHER") is None


async def test_concurrent_stores_of_the_same_content_converge_on_one_row(engine: AsyncEngine) -> None:
    sm = async_sessionmaker(engine)
    item = fetched("ID4RACE1", title="Flat")

    async def store() -> object:
        async with sm() as s, s.begin():
            return await store_snapshot(s, item)

    try:
        ids = await asyncio.gather(*(store() for _ in range(10)))
        assert len(set(ids)) == 1
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.listing_snapshot WHERE otodom_id = 'ID4RACE1'"))
            await conn.execute(text("DELETE FROM app.listing WHERE otodom_id = 'ID4RACE1'"))


def test_hash_ignores_key_order_but_not_content() -> None:
    assert content_hash({"a": 1, "b": [1, 2]}) == content_hash({"b": [1, 2], "a": 1})
    assert content_hash({"a": 1}) != content_hash({"a": 2})
