"""Box-wide in-flight cap on Postgres session advisory locks (blueprint §6: at most 4 OpenRouter calls).

A slot is a session-level advisory lock on a dedicated connection. If the holder crashes or its link drops,
Postgres releases the lock by itself, so no slot can leak. At most `slots` connections are held at any time.
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from rm_worker.clients.openrouter import MAX_IN_FLIGHT, VisionUnavailable

DEFAULT_KEY_BASE = (
    7_310_000  # advisory-lock namespace for vision slots; any other feature must use another range
)


class PgAdvisoryLimiter:
    def __init__(
        self,
        engine: AsyncEngine,
        slots: int = MAX_IN_FLIGHT,
        key_base: int = DEFAULT_KEY_BASE,
        poll_s: float = 0.25,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._engine = engine
        self._slots = slots
        self._key_base = key_base
        self._poll_s = poll_s
        self._sleep = sleep

    @asynccontextmanager
    async def slot(self, max_wait_s: float) -> AsyncGenerator[None]:
        conn = await self._engine.connect()
        try:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            key = await self._acquire(conn, max_wait_s)
            try:
                yield
            finally:
                await conn.scalar(select(func.pg_advisory_unlock(key)))
        finally:
            await conn.close()

    async def _acquire(self, conn: AsyncConnection, max_wait_s: float) -> int:
        try:
            async with asyncio.timeout(max(max_wait_s, 0.0)):
                while True:
                    for i in range(self._slots):
                        key = self._key_base + i
                        if await conn.scalar(select(func.pg_try_advisory_lock(key))):
                            return key
                    await self._sleep(self._poll_s)
        except TimeoutError as exc:
            raise VisionUnavailable("all vision slots stayed busy until the deadline") from exc
