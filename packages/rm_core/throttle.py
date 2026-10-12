"""Cross-process request pacing and circuit breaker, stored in Postgres (blueprint §2, §6).

LEGAL[scraping]: caps requests to third-party hosts and pauses them when the host blocks us.

The slot is reserved in one short statement; the caller commits and only then sleeps, so no lock or
transaction is held while waiting. All timestamps come from the database clock, so workers on different
hosts cannot disagree.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, literal, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import HostThrottle

DEFAULT_INTERVAL = timedelta(seconds=1)
DEFAULT_BREAKER_WINDOW = timedelta(minutes=15)


async def reserve_slot(session: AsyncSession, host: str, interval: timedelta = DEFAULT_INTERVAL) -> float:
    """Reserve the next slot for `host`; return the seconds to wait (after committing) before using it."""
    step = literal(interval)
    stmt = insert(HostThrottle).values(host=host, next_at=func.clock_timestamp() + step)
    stmt = stmt.on_conflict_do_update(
        index_elements=[HostThrottle.host],
        set_={"next_at": func.greatest(HostThrottle.next_at, func.clock_timestamp()) + step},
    ).returning(HostThrottle.next_at - step, func.clock_timestamp())
    slot, now = (await session.execute(stmt)).one()
    return max(0.0, (slot - now).total_seconds())


OTODOM_HOST = "otodom.pl"  # the host the shared throttle and circuit breaker are keyed on


@dataclass(frozen=True)
class BreakerStatus:
    open: bool
    retry_after_s: int = 0
    reason: str | None = None


async def breaker_status(session: AsyncSession, host: str) -> BreakerStatus:
    row = (
        await session.execute(
            select(
                HostThrottle.breaker_open_until, HostThrottle.breaker_reason, func.clock_timestamp()
            ).where(HostThrottle.host == host)
        )
    ).one_or_none()
    if row is None or row[0] is None or row[0] <= row[2]:
        return BreakerStatus(open=False)
    return BreakerStatus(
        open=True, retry_after_s=max(1, int((row[0] - row[2]).total_seconds())), reason=row[1]
    )


async def trip_breaker(
    session: AsyncSession, host: str, reason: str, window: timedelta = DEFAULT_BREAKER_WINDOW
) -> None:
    """Open the breaker for `window`; an already longer window is never shortened."""
    until = func.clock_timestamp() + literal(window)
    stmt = insert(HostThrottle).values(host=host, breaker_open_until=until, breaker_reason=reason)
    stmt = stmt.on_conflict_do_update(
        index_elements=[HostThrottle.host],
        set_={
            "breaker_open_until": func.greatest(func.coalesce(HostThrottle.breaker_open_until, until), until),
            "breaker_reason": reason,
        },
    )
    await session.execute(stmt)


async def audit_queue_busy(session: AsyncSession) -> bool:
    """True while an `audit` job waits or runs: batch work then yields its slot (interactive first)."""
    busy = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM public.procrastinate_jobs "
            "WHERE queue_name = 'audit' AND status IN ('todo','doing'))"
        )
    )
    return bool(busy)
