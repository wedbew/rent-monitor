"""Cross-process pacing and circuit breaker on real Postgres (blueprint §2, §6)."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from rm_core.throttle import audit_queue_busy, breaker_status, reserve_slot, trip_breaker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]


async def test_parallel_reservations_get_distinct_evenly_spaced_slots(engine: AsyncEngine) -> None:
    host = f"t-{uuid4().hex[:10]}"
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def one() -> float:
        async with sm() as s, s.begin():
            return await reserve_slot(s, host, timedelta(seconds=1))

    waits = sorted(await asyncio.gather(*(one() for _ in range(10))))
    # the i-th reservation waits about i seconds: nobody shares a slot
    for i, w in enumerate(waits):
        assert i - 0.5 <= w <= i + 0.5, waits
    assert len({round(w) for w in waits}) == 10


async def test_first_reservation_is_immediate_and_idle_hosts_do_not_accumulate_debt(
    engine: AsyncEngine,
) -> None:
    host = f"t-{uuid4().hex[:10]}"
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        assert await reserve_slot(s, host, timedelta(milliseconds=50)) < 0.05
    await asyncio.sleep(0.2)
    async with sm() as s, s.begin():
        assert await reserve_slot(s, host, timedelta(milliseconds=50)) < 0.05


async def test_breaker_opens_reports_remaining_time_and_never_shortens(engine: AsyncEngine) -> None:
    host = f"t-{uuid4().hex[:10]}"
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        assert (await breaker_status(s, host)).open is False
        await trip_breaker(s, host, "upstream_blocked", timedelta(minutes=15))
    async with sm() as s, s.begin():
        status = await breaker_status(s, host)
        assert status.open is True
        assert 890 <= status.retry_after_s <= 900
        assert status.reason == "upstream_blocked"
        await trip_breaker(s, host, "later_shorter", timedelta(seconds=5))
    async with sm() as s:
        assert (await breaker_status(s, host)).retry_after_s > 800


async def test_breaker_closes_after_its_window(engine: AsyncEngine) -> None:
    host = f"t-{uuid4().hex[:10]}"
    sm = async_sessionmaker(engine)
    async with sm() as s, s.begin():
        await trip_breaker(s, host, "x", timedelta(milliseconds=100))
    await asyncio.sleep(0.25)
    async with sm() as s:
        assert (await breaker_status(s, host)).open is False


@pytest.mark.usefixtures("procrastinate_schema")
async def test_audit_queue_busy_reflects_waiting_and_running_audit_jobs(engine: AsyncEngine) -> None:
    sm = async_sessionmaker(engine)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.procrastinate_jobs"))
    async with sm() as s:
        assert await audit_queue_busy(s) is False
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.procrastinate_jobs (queue_name, task_name, args, status) "
                "VALUES ('batch', 'refresh_city', '{}', 'todo'), ('audit', 'run_audit', '{}', 'succeeded')"
            )
        )
    async with sm() as s:
        assert await audit_queue_busy(s) is False  # other queues and finished audits do not count
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.procrastinate_jobs (queue_name, task_name, args, status) "
                "VALUES ('audit', 'run_audit', '{}', 'todo')"
            )
        )
    async with sm() as s:
        assert await audit_queue_busy(s) is True
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.procrastinate_jobs"))
