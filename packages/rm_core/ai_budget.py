"""Monthly AI spend control (blueprint §6 "Atomic AI budget", L-003). Amounts are `Decimal`, NUMERIC(14,6).

Before each model call a reservation is taken with ONE atomic statement
(`UPDATE ai_budget SET reserved_usd = reserved_usd + :est WHERE spent_usd + reserved_usd + :est <= cap_usd`),
so concurrent workers can never jointly exceed the cap. After the call the estimate is swapped for the
actual cost; a failed or cancelled call releases it. Every state change is a claim on the reservation row,
so settling or releasing twice is harmless, and a nightly sweep returns holds left behind by crashed
workers. A cap of 0 is the kill switch (vision off, audits degrade).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

import sentry_sdk
import structlog
from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import AiBudget, AiReservation, AiUsage

WARN_RATIO = Decimal("0.8")
STALE_AFTER = timedelta(minutes=30)  # longer than the 900 s audit deadline plus retries
log = structlog.get_logger(__name__)


def _current_month() -> object:
    return func.date(func.date_trunc("month", func.timezone("UTC", func.clock_timestamp())))


@dataclass(frozen=True)
class CallUsage:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated: bool = False  # the provider reported no cost, so the reservation estimate was used
    audit_id: UUID | None = None


class BudgetLevel(StrEnum):
    OK = "ok"
    WARNING = "warning"  # at or above 80 % of the cap
    EXHAUSTED = "exhausted"  # spent plus reserved has reached the cap: vision is off


@dataclass(frozen=True)
class BudgetStatus:
    month: date
    cap_usd: Decimal
    spent_usd: Decimal
    reserved_usd: Decimal
    level: BudgetLevel

    @property
    def used_ratio(self) -> Decimal:
        return (self.spent_usd + self.reserved_usd) / self.cap_usd if self.cap_usd > 0 else Decimal(1)


def _level(cap: Decimal, spent: Decimal, reserved: Decimal) -> BudgetLevel:
    if cap <= 0 or spent + reserved >= cap:
        return BudgetLevel.EXHAUSTED
    return BudgetLevel.WARNING if spent + reserved >= cap * WARN_RATIO else BudgetLevel.OK


async def budget_status(session: AsyncSession) -> BudgetStatus | None:
    row = (
        await session.execute(select(AiBudget).where(AiBudget.month == _current_month()))
    ).scalar_one_or_none()
    if row is None:
        return None
    return BudgetStatus(
        row.month,
        row.cap_usd,
        row.spent_usd,
        row.reserved_usd,
        _level(row.cap_usd, row.spent_usd, row.reserved_usd),
    )


class PgBudgetTicket:
    def __init__(self, gate: "PostgresBudgetGate", reservation_id: UUID) -> None:
        self._gate = gate
        self._id = reservation_id

    @property
    def reservation_id(self) -> UUID:
        return self._id

    async def settle(self, actual_usd: Decimal, usage: CallUsage | None = None) -> None:
        await self._gate.settle(self._id, actual_usd, usage)

    async def release(self) -> None:
        await self._gate.release(self._id)


class PostgresBudgetGate:
    """Implements the worker's `BudgetGate` against Postgres. Each call is its own short transaction."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], *, monthly_cap_usd: Decimal) -> None:
        self._sm = sessionmaker
        self._cap = monthly_cap_usd

    async def reserve(self, estimate_usd: Decimal) -> PgBudgetTicket | None:
        async with self._sm() as session, session.begin():
            # The configured cap is authoritative: changing it takes effect on the next reservation.
            await session.execute(
                insert(AiBudget)
                .values(month=_current_month(), cap_usd=self._cap)
                .on_conflict_do_update(index_elements=[AiBudget.month], set_={"cap_usd": self._cap})
            )
            month = await session.scalar(
                update(AiBudget)
                .where(
                    AiBudget.month == _current_month(),
                    AiBudget.spent_usd + AiBudget.reserved_usd + estimate_usd <= AiBudget.cap_usd,
                )
                .values(reserved_usd=AiBudget.reserved_usd + estimate_usd)
                .returning(AiBudget.month)
            )
            if month is None:
                return None
            reservation_id = await session.scalar(
                insert(AiReservation).values(month=month, amount_usd=estimate_usd).returning(AiReservation.id)
            )
            assert reservation_id is not None  # noqa: S101
            return PgBudgetTicket(self, reservation_id)

    async def settle(self, reservation_id: UUID, actual_usd: Decimal, usage: CallUsage | None) -> None:
        async with self._sm() as session, session.begin():
            claimed = (
                await session.execute(
                    update(AiReservation)
                    .where(AiReservation.id == reservation_id, AiReservation.state == "reserved")
                    .values(state="settled")
                    .returning(AiReservation.month, AiReservation.amount_usd)
                )
            ).one_or_none()
            if claimed is None:
                return  # already settled, released or swept
            month, held = claimed
            row = (
                await session.execute(
                    update(AiBudget)
                    .where(AiBudget.month == month)
                    .values(
                        reserved_usd=AiBudget.reserved_usd - held, spent_usd=AiBudget.spent_usd + actual_usd
                    )
                    .returning(
                        AiBudget.cap_usd, AiBudget.spent_usd, AiBudget.reserved_usd, AiBudget.warned_at
                    )
                )
            ).one()
            u = usage or CallUsage(model="unknown")
            session.add(
                AiUsage(
                    month=month,
                    audit_id=u.audit_id,
                    model=u.model[:120],
                    prompt_tokens=u.prompt_tokens,
                    completion_tokens=u.completion_tokens,
                    cost_usd=actual_usd,
                    cost_estimated=u.estimated,
                )
            )
            cap, spent, reserved, warned_at = row
            if warned_at is None and cap > 0 and spent + reserved >= cap * WARN_RATIO:
                await session.execute(
                    update(AiBudget).where(AiBudget.month == month).values(warned_at=func.clock_timestamp())
                )
                log.warning("ai_budget_warning", month=str(month), used_ratio=str((spent + reserved) / cap))
                sentry_sdk.capture_message(
                    f"AI budget at {int(WARN_RATIO * 100)} % for {month}", level="warning"
                )

    async def release(self, reservation_id: UUID) -> None:
        async with self._sm() as session, session.begin():
            await _return_hold(session, reservation_id, "released")


async def _return_hold(session: AsyncSession, reservation_id: UUID, new_state: str) -> bool:
    claimed = (
        await session.execute(
            update(AiReservation)
            .where(AiReservation.id == reservation_id, AiReservation.state == "reserved")
            .values(state=new_state)
            .returning(AiReservation.month, AiReservation.amount_usd)
        )
    ).one_or_none()
    if claimed is None:
        return False
    month, held = claimed
    await session.execute(
        update(AiBudget).where(AiBudget.month == month).values(reserved_usd=AiBudget.reserved_usd - held)
    )
    return True


async def sweep_stale_reservations(
    sessionmaker: async_sessionmaker[AsyncSession], *, older_than: timedelta = STALE_AFTER
) -> tuple[int, Decimal]:
    """Release holds left by crashed workers. Returns (count, total amount returned). Run nightly."""
    async with sessionmaker() as session, session.begin():
        stale = (
            await session.scalars(
                select(AiReservation.id).where(
                    AiReservation.state == "reserved",
                    AiReservation.created_at < func.clock_timestamp() - literal(older_than),
                )
            )
        ).all()
        count, total = 0, Decimal(0)
        for rid in stale:
            amount = await session.scalar(select(AiReservation.amount_usd).where(AiReservation.id == rid))
            if await _return_hold(session, rid, "swept"):
                count += 1
                total += amount or Decimal(0)
        if count:
            log.error(
                "ai_reservations_swept", count=count, usd=str(total)
            )  # a crash left money held: tell Sentry
        return count, total
