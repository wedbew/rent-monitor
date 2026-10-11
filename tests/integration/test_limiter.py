"""The box-wide in-flight cap on real Postgres advisory locks."""

import asyncio
from uuid import uuid4

import pytest
from rm_worker.clients.limiter import PgAdvisoryLimiter
from rm_worker.clients.openrouter import VisionUnavailable
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration]


def limiter(engine: AsyncEngine, slots: int = 4) -> PgAdvisoryLimiter:
    # a private key range per test keeps tests independent of each other and of real vision slots
    return PgAdvisoryLimiter(
        engine, slots=slots, key_base=9_000_000 + uuid4().int % 1_000_000 * 10, poll_s=0.02
    )


async def test_never_more_than_four_in_flight(engine: AsyncEngine) -> None:
    lim = limiter(engine)
    active = 0
    peak = 0

    async def work() -> None:
        nonlocal active, peak
        async with lim.slot(30):
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            active -= 1

    await asyncio.gather(*(work() for _ in range(12)))
    assert peak == 4


async def test_slot_is_released_when_the_holder_raises(engine: AsyncEngine) -> None:
    lim = limiter(engine, slots=1)
    with pytest.raises(RuntimeError, match="boom"):
        async with lim.slot(5):
            raise RuntimeError("boom")
    async with lim.slot(1):
        pass


async def test_a_crashed_holder_connection_frees_its_slot(engine: AsyncEngine) -> None:
    lim = limiter(engine, slots=1)
    held = asyncio.Event()
    release = asyncio.Event()

    async def holder() -> None:
        async with lim.slot(5):
            held.set()
            await release.wait()

    task = asyncio.create_task(holder())
    await held.wait()
    async with engine.connect() as admin:
        await admin.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_locks WHERE locktype = 'advisory' AND granted "
                "AND pid <> pg_backend_pid() AND objid >= 9000000 AND pid IN "
                "(SELECT pid FROM pg_stat_activity WHERE datname = current_database())"
            )
        )
        await admin.commit()
    async with lim.slot(5):  # acquired without the first holder ever releasing
        pass
    release.set()
    with pytest.raises(Exception):  # noqa: B017, PT011  (the killed connection surfaces as a driver error)
        await task


async def test_waiting_longer_than_the_deadline_raises_vision_unavailable(engine: AsyncEngine) -> None:
    lim = limiter(engine, slots=1)
    async with lim.slot(5):
        with pytest.raises(VisionUnavailable, match="busy"):
            async with lim.slot(0.2):
                pass
