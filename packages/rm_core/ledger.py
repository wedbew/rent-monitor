"""Credit ledger and quota (blueprint §3 design rules, §4.5 a). Money-adjacent: every path is
idempotent and race-safe.

Two sources are consumed in order: the paid period's allowance (expires with the period) first, then
discrete credits (never
expire). A unit is *reserved* when an audit is queued and *settled* when it ends: captured on success,
released on any other
terminal state, so a failed audit never costs the user. Credit movements are an append-only ledger with
a unique idempotency
key; `credit_account.balance` is a cache that must always equal the sum of the ledger (`ledger_mismatches`).
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import (
    Audit,
    ChargeSource,
    ChargeState,
    CreditAccount,
    CreditLedger,
    CreditReason,
    UsagePeriod,
)
from rm_core.entitlements import Entitlements

FEATURE_COST = {"deal_audit": 1, "deal_audit_analyst": 2, "redesign": 1}


class UnknownFeatureError(KeyError):
    """The feature has no price: refuse rather than charge zero."""


@dataclass(frozen=True)
class Reservation:
    audit_id: UUID
    feature: str
    source: ChargeSource
    usage_period_id: int | None
    cost: int


def cost_of(feature: str) -> int:
    try:
        return FEATURE_COST[feature]
    except KeyError as exc:
        raise UnknownFeatureError(feature) from exc


async def ensure_credit_account(
    session: AsyncSession, user_id: str, *, verified: bool, signup_credits: int
) -> bool:
    """Create the account row; grant the signup credits exactly once for a verified user. Returns True
    if granted now."""
    await session.execute(
        insert(CreditAccount)
        .values(user_id=user_id, balance=0)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    if not verified or signup_credits <= 0:
        return False
    return await _grant(
        session, user_id, signup_credits, reason=CreditReason.signup_grant, key=f"signup:{user_id}"
    )


async def _grant(
    session: AsyncSession,
    user_id: str,
    delta: int,
    *,
    reason: CreditReason,
    key: str,
    note: str | None = None,
    audit_id: UUID | None = None,
) -> bool:
    """Insert one ledger row and move the balance in the same transaction; a repeated key does nothing."""
    inserted = await session.scalar(
        insert(CreditLedger)
        .values(
            user_id=user_id, delta=delta, reason=reason, idempotency_key=key, note=note, audit_id=audit_id
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
        .returning(CreditLedger.id)
    )
    if inserted is None:
        return False
    await session.execute(
        update(CreditAccount)
        .where(CreditAccount.user_id == user_id)
        .values(balance=CreditAccount.balance + delta)
    )
    return True


async def admin_adjust(session: AsyncSession, user_id: str, delta: int, *, key: str, note: str) -> bool:
    """Operator credit change (idempotent by `key`). The balance can never go below zero (CHECK
    constraint)."""
    await session.execute(
        insert(CreditAccount)
        .values(user_id=user_id, balance=0)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    return await _grant(
        session, user_id, delta, reason=CreditReason.admin_adjust, key=f"admin:{key}", note=note
    )


async def reserve(
    session: AsyncSession, user_id: str, feature: str, ent: Entitlements, *, audit_id: UUID
) -> Reservation | None:
    """Hold the price of `feature`. None means quota exhausted (the API answers 402). Rows are locked
    FOR UPDATE."""
    cost = cost_of(feature)
    if ent.is_pro and ent.period is not None:  # 1) the expiring allowance first
        period = await session.scalar(
            select(UsagePeriod).where(UsagePeriod.id == ent.period.id).with_for_update()
        )
        if period is not None and period.used + cost <= period.allowance:
            period.used += cost
            return Reservation(audit_id, feature, ChargeSource.plan, period.id, cost)
    account = await session.scalar(
        select(CreditAccount).where(CreditAccount.user_id == user_id).with_for_update()
    )
    if account is None or account.balance < cost:  # 2) then the non-expiring credits
        return None
    account.balance -= cost
    return Reservation(audit_id, feature, ChargeSource.credit, None, cost)


async def record_reservation(session: AsyncSession, res: Reservation, user_id: str) -> None:
    """Write the ledger row of a credit reservation. Call after the audit row is flushed (foreign key)."""
    if res.source is ChargeSource.credit:
        session.add(
            CreditLedger(
                user_id=user_id,
                delta=-res.cost,
                reason=CreditReason.reserve,
                idempotency_key=f"reserve:{res.audit_id}",
                audit_id=res.audit_id,
            )
        )


async def settle(session: AsyncSession, audit_id: UUID, *, capture: bool) -> bool:
    """End an audit's charge: capture it, or release it back. Idempotent and race-safe.

    The state change is an atomic claim (`UPDATE ... WHERE charge_state = 'reserved' RETURNING`), so
    when several workers
    or a reconciler settle the same audit at once exactly one proceeds. Returns True if this call did
    the settling.
    """
    target = ChargeState.captured if capture else ChargeState.released
    claimed = (
        await session.execute(
            update(Audit)
            .where(Audit.id == audit_id, Audit.charge_state == ChargeState.reserved)
            .values(charge_state=target)
            .returning(Audit.user_id, Audit.charge_source, Audit.usage_period_id, Audit.analyst)
        )
    ).one_or_none()
    if claimed is None:
        return False
    if capture:
        return True
    user_id, source, period_id, analyst = claimed
    cost = FEATURE_COST["deal_audit_analyst" if analyst else "deal_audit"]
    if source is ChargeSource.plan and period_id is not None:
        await session.execute(
            update(UsagePeriod).where(UsagePeriod.id == period_id).values(used=UsagePeriod.used - cost)
        )
    elif source is ChargeSource.credit:
        await session.scalar(
            select(CreditAccount.user_id).where(CreditAccount.user_id == user_id).with_for_update()
        )
        await _grant(
            session, user_id, cost, reason=CreditReason.release, key=f"release:{audit_id}", audit_id=audit_id
        )
    return True


async def ledger_mismatches(session: AsyncSession) -> list[str]:
    """Users whose cached balance differs from the ledger sum (nightly money check; any row is a
    Sentry error)."""
    sums = (
        select(CreditLedger.user_id, func.sum(CreditLedger.delta).label("total"))
        .group_by(CreditLedger.user_id)
        .subquery()
    )
    stmt = (
        select(CreditAccount.user_id)
        .outerjoin(sums, sums.c.user_id == CreditAccount.user_id)
        .where(CreditAccount.balance != func.coalesce(sums.c.total, 0))
    )
    return list((await session.scalars(stmt)).all())
