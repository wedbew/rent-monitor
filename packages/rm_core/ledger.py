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
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import (
    Audit,
    ChargeSource,
    ChargeState,
    CreditAccount,
    CreditLedger,
    CreditReason,
    LotSource,
    ReportCreditAllocation,
    ReportCreditLot,
    UsagePeriod,
)
from rm_core.entitlements import Entitlements

FEATURE_COST = {"deal_audit": 1, "deal_audit_analyst": 2, "redesign": 1}


class UnknownFeatureError(KeyError):
    """The feature has no price: refuse rather than charge zero."""


class BillingHoldError(Exception):
    """The account has a billing hold (units were consumed before a purchase was reversed): no new
    reservation until staff resolve it."""


@dataclass(frozen=True)
class Reservation:
    audit_id: UUID
    feature: str
    source: ChargeSource
    usage_period_id: int | None
    cost: int
    allocations: tuple[tuple[int, int], ...] = ()  # (lot id, units) held for a credit reservation


LOT_SOURCE_OF = {
    CreditReason.signup_grant: LotSource.signup,
    CreditReason.admin_adjust: LotSource.admin,
    CreditReason.topup: LotSource.purchase,
}


async def lock_user(session: AsyncSession, user_id: str) -> CreditAccount | None:
    """Serialise every credit operation of one user. The lock order is fixed everywhere
    (docs/PADDLE-INTEGRATION.md section 4): advisory user lock, then `credit_account`, then lots in FIFO
    order, then audit and allocation rows. A path that has already locked an audit row must not take this
    lock afterwards, so settlement callers use `lock_owner` before they touch the audit."""
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"credit:{user_id}"})
    return await session.scalar(
        select(CreditAccount).where(CreditAccount.user_id == user_id).with_for_update()
    )


async def lock_owner(session: AsyncSession, audit_id: UUID) -> str | None:
    """Take the owner's credit lock before the audit row is updated. Returns the owner, or None if unknown."""
    user_id = await session.scalar(select(Audit.user_id).where(Audit.id == audit_id))
    if user_id is not None:
        await lock_user(session, user_id)
    return user_id


async def _lots(session: AsyncSession, user_id: str, *, spendable: bool = False) -> list[ReportCreditLot]:
    stmt = (
        select(ReportCreditLot)
        .where(ReportCreditLot.user_id == user_id)
        .order_by(ReportCreditLot.created_at, ReportCreditLot.id)
        .with_for_update()
    )
    if spendable:
        stmt = stmt.where(ReportCreditLot.available > 0, ReportCreditLot.frozen.is_(False))
    return list((await session.scalars(stmt)).all())


async def _cover_balance(session: AsyncSession, account: CreditAccount) -> None:
    """If units exist that no lot explains (the balance was changed outside this service, or a row predates
    lots), give them an explicit `migration` lot instead of pretending they have provenance. Needs the user
    lock."""
    held = await session.scalar(
        select(func.coalesce(func.sum(ReportCreditLot.available), 0)).where(
            ReportCreditLot.user_id == account.user_id
        )
    )
    missing = account.balance - int(held or 0)
    if missing > 0:
        session.add(
            ReportCreditLot(
                user_id=account.user_id,
                source=LotSource.migration,
                grant_key=f"heal:{account.user_id}:{uuid4().hex}",
                granted=missing,
                available=missing,
            )
        )
        await session.flush()


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


async def _take_from_lots(
    session: AsyncSession, user_id: str, units: int, *, lots: list[ReportCreditLot]
) -> list[tuple[ReportCreditLot, int]]:
    """Move `units` out of `available` over the given lots, oldest first. The caller ensured they suffice."""
    taken: list[tuple[ReportCreditLot, int]] = []
    left = units
    for lot in lots:
        if left == 0:
            break
        take = min(lot.available, left)
        if take > 0:
            lot.available -= take
            taken.append((lot, take))
            left -= take
    if left:
        msg = f"lots of {user_id} cover {units - left} of {units} units"
        raise RuntimeError(msg)
    return taken


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
    """Insert one ledger row and move the balance in the same transaction; a repeated key does nothing.

    A positive grant of a lot-bearing reason (signup, admin, purchase) also creates its lot; a negative admin
    adjustment removes units from the oldest lots. A `release` only returns units, to the lots that held them
    (`settle`), so it creates no lot."""
    account = await lock_user(session, user_id)
    if account is not None:
        await _cover_balance(session, account)
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
    if delta > 0 and reason in LOT_SOURCE_OF:
        session.add(
            ReportCreditLot(
                user_id=user_id,
                source=LOT_SOURCE_OF[reason],
                grant_key=key,
                granted=delta,
                available=delta,
            )
        )
        await session.flush()
    elif delta < 0:
        for lot, take in await _take_from_lots(session, user_id, -delta, lots=await _lots(session, user_id)):
            lot.revoked += take
        await session.flush()
    return True


async def grant_paid_reports(
    session: AsyncSession, user_id: str, units: int, *, grant_ref: str, purchase_id: UUID
) -> tuple[bool, int]:
    """Credit a verified purchase (docs/PADDLE-INTEGRATION.md section 4): a `topup` ledger row, the balance
    and a lot linked to the purchase, in the caller's transaction. Idempotent by `grant_ref` (one grant per
    provider transaction): returns (granted now, ledger id)."""
    await session.execute(
        insert(CreditAccount)
        .values(user_id=user_id, balance=0)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    granted = await _grant(
        session, user_id, units, reason=CreditReason.topup, key=grant_ref, note=f"purchase {purchase_id}"
    )
    if granted:
        await session.execute(
            update(ReportCreditLot)
            .where(ReportCreditLot.grant_key == grant_ref)
            .values(purchase_id=purchase_id)
        )
    ledger_id = await session.scalar(select(CreditLedger.id).where(CreditLedger.idempotency_key == grant_ref))
    assert ledger_id is not None  # the row exists: inserted now or by the earlier grant  # noqa: S101
    return granted, ledger_id


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
    FOR UPDATE, user lock first."""
    cost = cost_of(feature)
    if ent.unlimited_reports:
        # RM-438: an explicit entitlement. Nothing is held or spent; the audit row (charge_source admin_free)
        # is the usage record and settles through the same idempotent claim as every other audit.
        return Reservation(audit_id, feature, ChargeSource.admin_free, None, 0)
    account = await lock_user(session, user_id)
    if ent.is_pro and ent.period is not None:  # 1) the expiring allowance first
        period = await session.scalar(
            select(UsagePeriod).where(UsagePeriod.id == ent.period.id).with_for_update()
        )
        if period is not None and period.used + cost <= period.allowance:
            period.used += cost
            return Reservation(audit_id, feature, ChargeSource.plan, period.id, cost)
    if account is None:
        return None
    if account.billing_hold is not None:
        raise BillingHoldError
    await _cover_balance(session, account)
    lots = await _lots(
        session, user_id, spendable=True
    )  # frozen lots count in the balance but cannot be spent
    if sum(lot.available for lot in lots) < cost:  # 2) then the non-expiring credits
        return None
    taken = await _take_from_lots(session, user_id, cost, lots=lots)
    for lot, units in taken:
        lot.reserved += units
    account.balance -= cost
    allocations = tuple((lot.id, units) for lot, units in taken)
    return Reservation(audit_id, feature, ChargeSource.credit, None, cost, allocations)


async def record_reservation(session: AsyncSession, res: Reservation, user_id: str) -> None:
    """Write the ledger row and the lot allocations of a credit reservation. Call after the audit row is
    flushed (foreign key)."""
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
        session.add_all(
            ReportCreditAllocation(audit_id=res.audit_id, lot_id=lot_id, units=units, state="reserved")
            for lot_id, units in res.allocations
        )


async def _settle_allocations(
    session: AsyncSession, user_id: str, audit_id: UUID, *, capture: bool, cost: int
) -> list[tuple[ReportCreditLot, int]]:
    """Move the audit's held units: reserved -> consumed on capture, reserved -> available (same lot) on
    release. An audit with no allocations (reserved before lots existed, or inserted outside the service) is
    healed: a release returns its units to a `migration` lot, a capture needs no lot change. Returns the
    units a release put back on a lot that a refund or chargeback has since reversed (the caller revokes
    them in the same transaction)."""
    held = (
        await session.scalars(
            select(ReportCreditAllocation)
            .where(ReportCreditAllocation.audit_id == audit_id, ReportCreditAllocation.state == "reserved")
            .order_by(ReportCreditAllocation.lot_id)
            .with_for_update()
        )
    ).all()
    if not held:
        if not capture:
            session.add(
                ReportCreditLot(
                    user_id=user_id,
                    source=LotSource.migration,
                    grant_key=f"release-heal:{audit_id}",
                    granted=cost,
                    available=cost,
                )
            )
            await session.flush()
        return []
    back_on_reversed: list[tuple[ReportCreditLot, int]] = []
    for allocation in held:
        lot = await session.get_one(ReportCreditLot, allocation.lot_id, with_for_update=True)
        lot.reserved -= allocation.units
        if capture:
            lot.consumed += allocation.units
            allocation.state = "captured"
            if lot.reversed_at is not None:  # a report was completed on units that were refunded meanwhile
                await _hold(session, user_id, "REFUND_CONSUMED")
        else:
            lot.available += allocation.units
            allocation.state = "released"
            if lot.reversed_at is not None:
                back_on_reversed.append((lot, allocation.units))
    await session.flush()
    return back_on_reversed


async def settle(session: AsyncSession, audit_id: UUID, *, capture: bool) -> bool:
    """End an audit's charge: capture it, or release it back. Idempotent and race-safe.

    The owner's credit lock is taken first (the fixed lock order), then the state change is an atomic claim
    (`UPDATE ... WHERE charge_state = 'reserved' RETURNING`), so when several workers or a reconciler settle
    the same audit at once exactly one proceeds. Returns True if this call did the settling.
    """
    await lock_owner(session, audit_id)
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
    user_id, source, period_id, analyst = claimed
    cost = FEATURE_COST["deal_audit_analyst" if analyst else "deal_audit"]
    reversed_back: list[tuple[ReportCreditLot, int]] = []
    if source is ChargeSource.credit:
        reversed_back = await _settle_allocations(session, user_id, audit_id, capture=capture, cost=cost)
    if capture:
        return True
    if source is ChargeSource.plan and period_id is not None:
        await session.execute(
            update(UsagePeriod).where(UsagePeriod.id == period_id).values(used=UsagePeriod.used - cost)
        )
    elif source is ChargeSource.credit:
        await _grant(
            session, user_id, cost, reason=CreditReason.release, key=f"release:{audit_id}", audit_id=audit_id
        )
        for lot, units in reversed_back:  # released and revoked together: the refund wins
            revoke_key = f"refund_revoke:{lot.purchase_id}:{lot.reversal_epoch}:{audit_id}"
            await _revoke(session, lot, units, ledger_ref=revoke_key)
    return True


async def _hold(session: AsyncSession, user_id: str, reason: str) -> None:
    await session.execute(
        update(CreditAccount)
        .where(CreditAccount.user_id == user_id, CreditAccount.billing_hold.is_(None))
        .values(billing_hold=reason)
    )


async def _entry(
    session: AsyncSession, user_id: str, delta: int, reason: CreditReason, *, ledger_ref: str, note: str
) -> bool:
    """One append-only ledger row and the matching balance move, idempotent by reference (no lot handling)."""
    inserted = await session.scalar(
        insert(CreditLedger)
        .values(user_id=user_id, delta=delta, reason=reason, idempotency_key=ledger_ref, note=note)
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


async def _revoke(session: AsyncSession, lot: ReportCreditLot, units: int, *, ledger_ref: str) -> None:
    """Take `units` of this lot's available units back: lot counters, the cached balance and an append-only
    negative ledger entry together. The balance cannot go negative: the units are part of it."""
    if units <= 0:
        return
    note = f"purchase {lot.purchase_id}"
    if await _entry(
        session, lot.user_id, -units, CreditReason.refund_revoke, ledger_ref=ledger_ref, note=note
    ):
        lot.available -= units
        lot.revoked += units
        await session.flush()


@dataclass(frozen=True)
class Reversal:
    revoked: int  # available units taken back now
    in_flight: int  # units held by running audits: revoked when each is released
    consumed: int  # units already spent on completed reports: a billing hold, not a debt


async def reverse_purchase(session: AsyncSession, purchase_id: UUID) -> Reversal | None:
    """A refund or chargeback of this purchase stands: freeze its lot, take its available units back with an
    append-only entry, leave in-flight audits to settle (their released units are revoked then), and put the
    account on billing hold if units were already consumed. Idempotent per reversal epoch. Needs the user
    lock (`lock_user`). None if the purchase has no lot (never granted)."""
    lot = await session.scalar(
        select(ReportCreditLot).where(ReportCreditLot.purchase_id == purchase_id).with_for_update()
    )
    if lot is None:
        return None
    if lot.reversed_at is not None:
        return Reversal(0, lot.reserved, 0)
    lot.reversed_at = func.now()
    lot.reversal_epoch += 1
    lot.frozen = True
    taken = lot.available
    await _revoke(
        session, lot, taken, ledger_ref=f"refund_revoke:{purchase_id}:{lot.reversal_epoch}:available"
    )
    if lot.consumed:
        await _hold(session, lot.user_id, "REFUND_CONSUMED")
    await session.flush()
    return Reversal(taken, lot.reserved, lot.consumed)


async def restore_purchase(session: AsyncSession, purchase_id: UUID) -> int:
    """A chargeback was reversed: give back exactly the units this reversal took, once, and unfreeze the
    lot. Never re-grants the original pack. Needs the user lock. Returns the units restored."""
    lot = await session.scalar(
        select(ReportCreditLot).where(ReportCreditLot.purchase_id == purchase_id).with_for_update()
    )
    if lot is None or lot.reversed_at is None:
        return 0
    taken = await session.scalar(
        select(func.coalesce(-func.sum(CreditLedger.delta), 0)).where(
            CreditLedger.reason == CreditReason.refund_revoke,
            CreditLedger.idempotency_key.like(f"refund_revoke:{purchase_id}:{lot.reversal_epoch}:%"),
        )
    )
    units = min(int(taken or 0), lot.revoked)
    restore_ref = f"refund_restore:{purchase_id}:{lot.reversal_epoch}"
    note = f"purchase {purchase_id}"
    if units and await _entry(
        session, lot.user_id, units, CreditReason.refund_restore, ledger_ref=restore_ref, note=note
    ):
        lot.revoked -= units
        lot.available += units
    lot.reversed_at = None
    lot.frozen = False
    await session.flush()
    return units


async def clear_billing_hold(session: AsyncSession, user_id: str) -> bool:
    """Staff resolved a billing review (the caller logs who and why). True if a hold was removed."""
    result = await session.execute(
        update(CreditAccount)
        .where(CreditAccount.user_id == user_id, CreditAccount.billing_hold.is_not(None))
        .values(billing_hold=None)
    )
    return bool(getattr(result, "rowcount", 0))


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


async def lot_mismatches(session: AsyncSession) -> list[str]:
    """Accounts whose lots disagree with the balance or with the allocations that hold units (nightly check).
    A row means the provenance layer drifted from the ledger; it never changes anything."""
    lots = (
        select(
            ReportCreditLot.user_id,
            func.sum(ReportCreditLot.available).label("available"),
        )
        .group_by(ReportCreditLot.user_id)
        .subquery()
    )
    balance_drift = (
        select(CreditAccount.user_id)
        .outerjoin(lots, lots.c.user_id == CreditAccount.user_id)
        .where(CreditAccount.balance != func.coalesce(lots.c.available, 0))
    )
    held = (
        select(ReportCreditAllocation.lot_id, func.sum(ReportCreditAllocation.units).label("units"))
        .where(ReportCreditAllocation.state == "reserved")
        .group_by(ReportCreditAllocation.lot_id)
        .subquery()
    )
    reserved_drift = (
        select(ReportCreditLot.user_id)
        .outerjoin(held, held.c.lot_id == ReportCreditLot.id)
        .where(ReportCreditLot.reserved != func.coalesce(held.c.units, 0))
    )
    return sorted(
        set((await session.scalars(balance_drift)).all()) | set((await session.scalars(reserved_drift)).all())
    )
