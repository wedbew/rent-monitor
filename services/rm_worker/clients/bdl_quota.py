"""Postgres-shared request quota for the GUS BDL client: one budget for every worker process.

LEGAL[scraping]: bounds the request rate to a third-party API; the real server limits are unconfirmed
(RM-391-L02), the windows are supplied by the caller and none is baked in here (RM-391).
GDPR[retention]: stamps hold a source name and a time, no personal data; the gate deletes rows older than
its longest window on every acquire (RM-391).

Satisfies `rm_worker.clients.bdl.QuotaGate`. The check-and-insert runs under a transaction-scoped advisory
lock, so concurrent workers cannot both take the last slot; sleeping happens outside the transaction and the
database clock is used for every comparison (no cross-host clock skew).
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta

from rm_core.db.models import LocationQuotaStamp
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.clients.bdl import BdlQuotaExhausted, QuotaWindow


def quota_windows(per_second: int, per_minute: int) -> tuple[QuotaWindow, ...]:
    """The service answers 429 above 10 requests per second; add our own per-minute cap."""
    return (QuotaWindow(limit=per_second, seconds=1.0), QuotaWindow(limit=per_minute, seconds=60.0))


@dataclass
class PgQuotaGate:
    sessions: async_sessionmaker[AsyncSession]
    windows: tuple[QuotaWindow, ...]
    source: str = "bdl"
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    _lock_key: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.windows or any(w.limit < 1 or w.seconds <= 0 for w in self.windows):
            raise ValueError("quota windows must be positive")
        self._lock_key = f"location_quota:{self.source}"

    async def _try_take(self) -> float:
        """0.0 when a slot was taken, else the seconds until one opens."""
        horizon = max(w.seconds for w in self.windows)
        async with self.sessions() as s, s.begin():
            await s.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(self._lock_key, 0))))
            now = await s.scalar(select(func.clock_timestamp()))
            assert now is not None  # noqa: S101
            await s.execute(
                delete(LocationQuotaStamp).where(
                    LocationQuotaStamp.source == self.source,
                    LocationQuotaStamp.at <= now - timedelta(seconds=horizon),
                )
            )
            wait = 0.0
            for w in self.windows:
                inside = (
                    await s.scalars(
                        select(LocationQuotaStamp.at)
                        .where(
                            LocationQuotaStamp.source == self.source,
                            LocationQuotaStamp.at > now - timedelta(seconds=w.seconds),
                        )
                        .order_by(LocationQuotaStamp.at)
                    )
                ).all()
                if len(inside) >= w.limit:
                    opens = (inside[-w.limit] - now).total_seconds() + w.seconds
                    wait = max(wait, opens)
            if wait <= 0:
                s.add(LocationQuotaStamp(source=self.source, at=now))
            return wait

    async def acquire(self, *, max_wait_s: float) -> None:
        wait = await self._try_take()
        if wait <= 0:
            return
        if wait > max_wait_s:
            raise BdlQuotaExhausted("BDL request quota used up", retry_after_s=wait)
        await self.sleep(wait)
        # Another worker may have taken the slot while we slept: ask again, but never wait past the budget.
        again = await self._try_take()
        if again > 0:
            raise BdlQuotaExhausted("BDL request quota used up", retry_after_s=again)
