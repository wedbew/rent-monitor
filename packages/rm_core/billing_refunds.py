"""Support-initiated refunds of an unused pack (docs/PADDLE-INTEGRATION.md section 6, RM-229).

The order is the safety: freeze the pack's lot under the user lock, then write a durable refund
**intent**, then (with no transaction open) ask Paddle. A pack with consumed or reserved units never
reaches Paddle from here: it goes to manual review. A refund request is not a refund: the units are
taken back only when a later, verified approved adjustment arrives
(`rm_core.billing_events.apply_reversals`); a rejected one unfreezes the lot. An ambiguous result is
reconciled by listing the transaction's adjustments before any second creation.

GDPR[personal-data]: nothing new is stored beyond ids, status and amounts; the support reason goes to
Paddle only."""

from dataclasses import dataclass
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import BillingAdjustment, BillingPurchase, PurchaseState, ReportCreditLot
from rm_core.ledger import lock_user
from rm_core.paddle import PaddleAmbiguousError, PaddleClient, PaddleError

log = structlog.get_logger(__name__)
INTENT_PREFIX = "intent-"
OPEN_INTENT = ("intent", "unknown")


class NotRefundableError(Exception):
    """The purchase cannot be refunded from here (not granted, no lot, or no owner)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class RefundOutcome:
    status: str  # requested | review | exists | failed | unknown
    adjustment_id: str | None = None


async def _open_refund(session: AsyncSession, purchase_id: UUID) -> BillingAdjustment | None:
    return await session.scalar(
        select(BillingAdjustment)
        .where(
            BillingAdjustment.purchase_id == purchase_id,
            BillingAdjustment.action == "refund",
            BillingAdjustment.status.in_(("intent", "unknown", "pending_approval", "pending", "approved")),
        )
        .order_by(BillingAdjustment.id)
        .limit(1)
    )


async def _prepare(
    sm: async_sessionmaker[AsyncSession], purchase_id: UUID
) -> tuple[RefundOutcome | None, str, str]:
    """Freeze the lot and write the intent in one transaction: (early outcome or None, txn id, env)."""
    async with sm() as session, session.begin():
        owner = await session.scalar(select(BillingPurchase.user_id).where(BillingPurchase.id == purchase_id))
        if owner is None:
            raise NotRefundableError("NO_OWNER")
        await lock_user(session, owner)
        purchase = await session.scalar(
            select(BillingPurchase).where(BillingPurchase.id == purchase_id).with_for_update()
        )
        if purchase is None or purchase.state != PurchaseState.granted or purchase.provider_txn_id is None:
            raise NotRefundableError("STATE")
        open_refund = await _open_refund(session, purchase_id)
        if open_refund is not None and open_refund.status not in OPEN_INTENT:
            return RefundOutcome("exists", open_refund.adjustment_id), "", ""
        lot = await session.scalar(
            select(ReportCreditLot).where(ReportCreditLot.purchase_id == purchase_id).with_for_update()
        )
        if lot is None:
            raise NotRefundableError("NO_LOT")
        if lot.consumed or lot.reserved:  # used packs are a support decision, not an automatic refund
            purchase.state, purchase.error_code = PurchaseState.review, "USED_PACK"
            return RefundOutcome("review"), "", ""
        lot.frozen = True
        if open_refund is None:
            session.add(
                BillingAdjustment(
                    environment=purchase.environment,
                    adjustment_id=f"{INTENT_PREFIX}{uuid4().hex}",
                    purchase_id=purchase_id,
                    action="refund",
                    type="full",
                    status="intent",
                    total_minor=purchase.amount_minor,
                )
            )
        return None, purchase.provider_txn_id, purchase.environment


async def _settle_intent(
    sm: async_sessionmaker[AsyncSession],
    purchase_id: UUID,
    *,
    status: str,
    adjustment_id: str | None = None,
    unfreeze: bool = False,
) -> None:
    async with sm() as session, session.begin():
        owner = await session.scalar(select(BillingPurchase.user_id).where(BillingPurchase.id == purchase_id))
        if owner is not None:
            await lock_user(session, owner)
        values: dict[str, object] = {"status": status, "updated_at": func.now()}
        if adjustment_id is not None:
            values["adjustment_id"] = adjustment_id
        await session.execute(
            update(BillingAdjustment)
            .where(
                BillingAdjustment.purchase_id == purchase_id,
                BillingAdjustment.action == "refund",
                BillingAdjustment.status.in_(OPEN_INTENT),
            )
            .values(**values)
        )
        if unfreeze:
            await session.execute(
                update(ReportCreditLot)
                .where(ReportCreditLot.purchase_id == purchase_id, ReportCreditLot.reversed_at.is_(None))
                .values(frozen=False)
            )


async def _adopt_existing(
    sm: async_sessionmaker[AsyncSession],
    client: PaddleClient,
    purchase_id: UUID,
    txn_id: str,
    environment: str,
) -> str | None:
    """Did an earlier, ambiguous creation reach Paddle? Adopt its adjustment id instead of creating again."""
    for a in await client.list_adjustments(txn_id):
        if a.action == "refund" and a.status != "rejected":
            async with sm() as session, session.begin():
                await session.execute(
                    delete(BillingAdjustment).where(
                        BillingAdjustment.purchase_id == purchase_id,
                        BillingAdjustment.status.in_(OPEN_INTENT),
                    )
                )
                await session.execute(
                    insert(BillingAdjustment)
                    .values(
                        environment=environment,
                        adjustment_id=a.id,
                        purchase_id=purchase_id,
                        action=a.action,
                        type=a.type,
                        status=a.status,
                        total_minor=a.total_minor,
                    )
                    .on_conflict_do_nothing(constraint="uq_billing_adjustment_env_id")
                )
            return a.id
    return None


async def request_refund(
    sm: async_sessionmaker[AsyncSession], client: PaddleClient, purchase_id: UUID, *, reason: str
) -> RefundOutcome:
    early, txn_id, environment = await _prepare(sm, purchase_id)
    if early is not None:
        return early
    try:
        adopted = await _adopt_existing(sm, client, purchase_id, txn_id, environment)
    except PaddleError:
        return RefundOutcome("unknown")  # cannot tell whether one exists: do not create a second blindly
    if adopted is not None:
        return RefundOutcome("requested", adopted)
    try:
        adjustment = await client.create_full_refund(transaction_id=txn_id, reason=reason)
    except PaddleAmbiguousError:
        await _settle_intent(sm, purchase_id, status="unknown")
        return RefundOutcome("unknown")
    except PaddleError:
        log.warning("billing.refund_failed", purchase_id=str(purchase_id))
        await _settle_intent(sm, purchase_id, status="failed", unfreeze=True)
        return RefundOutcome("failed")
    await _settle_intent(sm, purchase_id, status=adjustment.status, adjustment_id=adjustment.id)
    return RefundOutcome("requested", adjustment.id)
