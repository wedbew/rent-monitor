"""Who gets Pro, and how much quota is left (blueprint §3 "Stripe webhook lifecycle", `has_pro`).

Fails closed: an active or trialing subscription stops counting 48 h after its period end unless a
renewal arrived, and a
past-due one only counts until `grace_until`. A paid 30-day pass counts while its period covers now.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import CreditAccount, Subscription, SubStatus, UsagePeriod

FAIL_CLOSED_AFTER = timedelta(hours=48)
PlanCode = Literal["free", "pro"]


def has_pro(sub: Subscription | None, now: datetime) -> bool:
    if sub is None:
        return False
    if sub.status in (SubStatus.active, SubStatus.trialing):
        return now < sub.current_period_end + FAIL_CLOSED_AFTER
    return sub.status is SubStatus.past_due and sub.grace_until is not None and now < sub.grace_until


@dataclass(frozen=True)
class PeriodSnapshot:
    id: int
    kind: str
    period_end: datetime
    allowance: int
    used: int

    @property
    def remaining(self) -> int:
        return max(self.allowance - self.used, 0)


@dataclass(frozen=True)
class Entitlements:
    user_id: str
    is_pro: bool
    plan_code: PlanCode
    period: PeriodSnapshot | None  # the period whose allowance is spent first
    credit_balance: int
    subscription_status: SubStatus | None
    grace_until: datetime | None


async def db_now(session: AsyncSession) -> datetime:
    value = await session.scalar(select(func.clock_timestamp()))
    assert value is not None  # noqa: S101
    return value


async def load_entitlements(
    session: AsyncSession, user_id: str, *, now: datetime | None = None
) -> Entitlements:
    moment = now or await db_now(session)
    sub = await session.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.current_period_end.desc())
        .limit(1)
    )
    period = await session.scalar(
        select(UsagePeriod)
        .where(
            UsagePeriod.user_id == user_id,
            UsagePeriod.period_start <= moment,
            UsagePeriod.period_end > moment,
        )
        .order_by(UsagePeriod.period_end.desc())
        .limit(1)
    )
    balance = await session.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == user_id)) or 0
    pass_active = period is not None and period.kind == "pass"
    pro = has_pro(sub, moment) or pass_active
    snapshot = (
        PeriodSnapshot(period.id, period.kind, period.period_end, period.allowance, period.used)
        if period is not None and pro
        else None
    )
    return Entitlements(
        user_id=user_id,
        is_pro=pro,
        plan_code="pro" if pro else "free",
        period=snapshot,
        credit_balance=balance,
        subscription_status=sub.status if sub is not None else None,
        grace_until=sub.grace_until if sub is not None else None,
    )
