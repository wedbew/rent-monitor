"""Client + Postgres policy + snapshot store, end to end with a fake transport."""

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from rm_core.deadline import Deadline
from rm_core.throttle import trip_breaker
from rm_worker.clients.otodom import ListingGone, OtodomClient, RawResponse, UpstreamBlocked
from rm_worker.clients.otodom_policy import PostgresHostPolicy
from rm_worker.snapshot_service import get_snapshot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]


class Transport:
    def __init__(self, *responses: RawResponse) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def get(self, url: str, *, headers: dict[str, str], total_s: float) -> RawResponse:
        self.calls += 1
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


def offer(short_id: str, **ad: object) -> RawResponse:
    data = {"props": {"pageProps": {"ad": {"id": 7, **ad}}}}
    body = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'.encode()
    return RawResponse(200, {}, body, f"https://www.otodom.pl/pl/oferta/x-{short_id}")


@pytest.fixture
def ids() -> str:
    return "ID" + uuid4().hex[:6]


async def _cleanup(engine: AsyncEngine, short_id: str, host: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.listing_snapshot WHERE otodom_id = :i"), {"i": short_id})
        await conn.execute(text("DELETE FROM app.listing WHERE otodom_id = :i"), {"i": short_id})
        await conn.execute(text("DELETE FROM app.host_throttle WHERE host = :h"), {"h": host})


async def test_second_audit_of_the_same_listing_reuses_the_shared_snapshot(
    engine: AsyncEngine, ids: str
) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    transport = Transport(offer(ids, title="Flat"))
    client = OtodomClient(
        transport, PostgresHostPolicy(sm, timedelta(milliseconds=10)), PostgresHostPolicy(sm)
    )
    try:
        first = await get_snapshot(sm, client, ids, deadline=Deadline.after(30))
        second = await get_snapshot(sm, client, ids, deadline=Deadline.after(30))
        assert first == second
        assert transport.calls == 1
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT payload FROM app.listing_snapshot WHERE id = :i"), {"i": first}
                )
            ).one()
        assert row[0]["title"] == "Flat"
    finally:
        await _cleanup(engine, ids, "otodom.pl")


async def test_open_breaker_stops_fetching_until_it_closes(engine: AsyncEngine, ids: str) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    transport = Transport(offer(ids))
    policy = PostgresHostPolicy(sm, timedelta(milliseconds=10))
    client = OtodomClient(transport, policy, policy)
    try:
        async with sm() as s, s.begin():
            await trip_breaker(s, "otodom.pl", "upstream_blocked", timedelta(minutes=15))
        with pytest.raises(UpstreamBlocked) as err:
            await get_snapshot(sm, client, ids, deadline=Deadline.after(30))
        assert err.value.retry_after_s is not None
        assert err.value.retry_after_s > 800
        assert transport.calls == 0
    finally:
        await _cleanup(engine, ids, "otodom.pl")


async def test_gone_listing_stores_nothing(engine: AsyncEngine, ids: str) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    policy = PostgresHostPolicy(sm, timedelta(milliseconds=10))
    client = OtodomClient(Transport(RawResponse(404, {}, b"", "https://www.otodom.pl/x")), policy, policy)
    try:
        with pytest.raises(ListingGone):
            await get_snapshot(sm, client, ids, deadline=Deadline.after(30))
        async with engine.connect() as conn:
            count = await conn.scalar(
                text("SELECT count(*) FROM app.listing WHERE otodom_id = :i"), {"i": ids}
            )
        assert count == 0
    finally:
        await _cleanup(engine, ids, "otodom.pl")
