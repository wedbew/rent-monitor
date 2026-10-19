"""Risk-free rate on real Postgres (RM-210): refresh, idempotency, freshness, fallback and refusal.

Offline: the ECB is an `httpx.MockTransport` (no network). The database is the session's Testcontainers
Postgres.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from macro_csv import csv_of, row
from rm_core.db.models import RiskFreeRate as RiskFreeRow
from rm_core.deadline import Deadline
from rm_core.risk_free import (
    ECB_SERIES_KEY,
    SETTING_SOURCE,
    RiskFreeRate,
    record_failure,
    record_observation,
)
from rm_worker.clients.macro import EcbRateClient
from rm_worker.context import ContextUnavailableError, MarketContext
from rm_worker.tasks.macro import FAILURE_REJECTED, FAILURE_UNAVAILABLE, refresh_risk_free_now
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 19, 6, 15, tzinfo=UTC)
FRESH_DAY = date(2026, 10, 19)  # 19 days after the end of 2026-09
STALE_DAY = date(2027, 3, 1)  # well past 120 days after 2026-09
SETTING = Decimal("0.055")


@pytest_asyncio.fixture(loop_scope="session")
async def sm(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with engine.begin() as c:
        await c.execute(text("DELETE FROM app.risk_free_rate"))
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as c:
        await c.execute(text("DELETE FROM app.risk_free_rate"))


def ecb(body: str | None = None, *, status: int = 200) -> EcbRateClient:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body if body is not None else csv_of(row()))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    return EcbRateClient(http, base_url="https://ecb.test/service/data")


async def stored(sm: async_sessionmaker[AsyncSession]) -> RiskFreeRow | None:
    async with sm() as s:
        row_ = await s.get(RiskFreeRow, ECB_SERIES_KEY)
        if row_ is not None:
            s.expunge(row_)
        return row_


def context(sm: async_sessionmaker[AsyncSession], *, setting: Decimal | None, today: date) -> MarketContext:
    day: Callable[[], date] = lambda: today  # noqa: E731 - a fixed clock for the freshness rule
    return MarketContext(sm, risk_free=setting, today=day)


async def pick(ctx: MarketContext) -> RiskFreeRate:
    return await ctx.risk_free_rate(deadline=Deadline.after(5))


# --- refresh: store, idempotency, monotone, failures ------------------------------------------------------


async def test_refresh_stores_the_latest_observation_and_is_idempotent(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    assert await refresh_risk_free_now(sm, ecb(), NOW) == "stored"
    first = await stored(sm)
    assert first is not None
    assert first.rate == Decimal("0.062300")
    assert first.observation_period == date(2026, 9, 1)
    assert first.source == "ecb"
    assert first.last_failure_code is None

    # A second identical run (a retry or an overlapping daily run) changes nothing observable.
    assert await refresh_risk_free_now(sm, ecb(), NOW) == "stored"
    again = await stored(sm)
    assert again is not None
    assert (again.rate, again.observation_period) == (first.rate, first.observation_period)
    async with sm() as s:
        assert await s.scalar(select(func.count()).select_from(RiskFreeRow)) == 1


async def test_an_older_observation_never_overwrites_a_newer_one(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    await refresh_risk_free_now(sm, ecb(), NOW)
    older = csv_of(row(period="2026-08", value="5.50"))
    assert await refresh_risk_free_now(sm, ecb(older), NOW) == "kept"
    current = await stored(sm)
    assert current is not None
    assert current.observation_period == date(2026, 9, 1)
    assert current.rate == Decimal("0.062300")


async def test_a_failed_refresh_keeps_the_previous_value_and_records_the_failure(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    await refresh_risk_free_now(sm, ecb(), NOW)
    assert await refresh_risk_free_now(sm, ecb(status=503), NOW) == "failed"
    failed = await stored(sm)
    assert failed is not None
    assert failed.rate == Decimal("0.062300")  # the previous value is kept
    assert failed.last_failure_code == FAILURE_UNAVAILABLE
    assert failed.last_failed_at is not None

    # The next good answer clears the failure fields.
    assert await refresh_risk_free_now(sm, ecb(), NOW) == "stored"
    healed = await stored(sm)
    assert healed is not None
    assert healed.last_failure_code is None
    assert healed.last_failed_at is None


async def test_an_implausible_answer_is_refused_and_not_stored(sm: async_sessionmaker[AsyncSession]) -> None:
    assert await refresh_risk_free_now(sm, ecb(csv_of(row(value="25.0"))), NOW) == "failed"
    rejected = await stored(sm)
    assert rejected is not None
    assert rejected.rate is None  # a failure row only; no value was stored
    assert rejected.last_failure_code == FAILURE_REJECTED


async def test_the_database_refuses_an_implausible_rate(sm: async_sessionmaker[AsyncSession]) -> None:
    async with sm() as s:
        s.add(
            RiskFreeRow(
                series_key="IRS.TEST.IMPLAUSIBLE",
                source="test",
                observation_period=date(2026, 9, 1),
                rate=Decimal("0.5"),
                fetched_at=NOW,
                last_attempt_at=NOW,
            )
        )
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_a_failure_before_any_value_leaves_a_failure_only_row(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    async with sm() as s, s.begin():
        await record_failure(s, code=FAILURE_UNAVAILABLE, now=NOW)
    row_ = await stored(sm)
    assert row_ is not None
    assert row_.rate is None
    assert row_.observation_period is None


# --- MarketContext: freshness, fallback, refusal ----------------------------------------------------------


async def test_a_fresh_stored_rate_is_used_with_its_source_and_month(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    await refresh_risk_free_now(sm, ecb(), NOW)
    used = await pick(context(sm, setting=SETTING, today=FRESH_DAY))
    assert used.rate == Decimal("0.062300")
    assert used.source == f"ecb:{ECB_SERIES_KEY}"
    assert used.as_of == date(2026, 9, 1)


async def test_a_stale_stored_rate_falls_back_to_the_setting(sm: async_sessionmaker[AsyncSession]) -> None:
    await refresh_risk_free_now(sm, ecb(), NOW)
    used = await pick(context(sm, setting=SETTING, today=STALE_DAY))
    assert used.rate == SETTING
    assert used.source == SETTING_SOURCE
    assert used.as_of is None


async def test_a_stale_stored_rate_with_no_setting_refuses(sm: async_sessionmaker[AsyncSession]) -> None:
    await refresh_risk_free_now(sm, ecb(), NOW)
    with pytest.raises(ContextUnavailableError):
        await pick(context(sm, setting=None, today=STALE_DAY))


async def test_an_empty_store_uses_the_setting_and_refuses_without_it(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    assert (await pick(context(sm, setting=SETTING, today=FRESH_DAY))).source == SETTING_SOURCE
    with pytest.raises(ContextUnavailableError):
        await pick(context(sm, setting=None, today=FRESH_DAY))


async def test_a_failure_only_row_does_not_count_as_a_stored_rate(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    async with sm() as s, s.begin():
        await record_failure(s, code=FAILURE_UNAVAILABLE, now=NOW)
    assert (await pick(context(sm, setting=SETTING, today=FRESH_DAY))).source == SETTING_SOURCE
    with pytest.raises(ContextUnavailableError):
        await pick(context(sm, setting=None, today=FRESH_DAY))


async def test_record_observation_rejects_an_implausible_value_before_writing(
    sm: async_sessionmaker[AsyncSession],
) -> None:
    async with sm() as s, s.begin():
        with pytest.raises(ValueError, match="implausible"):
            await record_observation(s, observation_period=date(2026, 9, 1), rate=Decimal("0.5"), now=NOW)
