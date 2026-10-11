"""Postgres-backed request slots and circuit breaker for the Otodom client (LEGAL[scraping], RM-22)."""

from datetime import timedelta

from rm_core.throttle import audit_queue_busy, breaker_status, reserve_slot, trip_breaker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class PostgresHostPolicy:
    """Implements `SlotReserver` and `BreakerStore`. Each call is its own short transaction."""

    def __init__(
        self, sessionmaker: async_sessionmaker[AsyncSession], interval: timedelta = timedelta(seconds=1)
    ) -> None:
        self._sm = sessionmaker
        self._interval = interval

    async def reserve(self, host: str) -> float:
        async with self._sm() as session, session.begin():
            return await reserve_slot(session, host, self._interval)

    async def audit_queue_busy(self) -> bool:
        async with self._sm() as session:
            return await audit_queue_busy(session)

    async def is_open(self, host: str) -> int | None:
        async with self._sm() as session:
            status = await breaker_status(session, host)
        return status.retry_after_s if status.open else None

    async def trip(self, host: str, reason: str) -> None:
        async with self._sm() as session, session.begin():
            await trip_breaker(session, host, reason)
