"""Billing events and the grant (docs/PADDLE-INTEGRATION.md section 5, RM-218).

Receipt is durable and cheap: a verified notification becomes one `billing_event` row (unique per
environment and event id). Processing happens later, by a worker or the sweeper, and always starts from
a fresh read of the transaction from Paddle, never from the notification body or the browser. A grant
needs the purchase's own snapshot to match the completed transaction exactly (price id, quantity one,
PLN total, no discount, no subscription, our binding token); anything else grants nothing and goes to
`review`. The units come from the pack snapshot, never from provider `custom_data`. One transaction, one
grant: the ledger key `paddle:{env}:{txn}:grant`, the purchase's unique `grant_ledger_id` and the lot's
unique `purchase_id` make a duplicate delivery, a parallel worker and the reconciler converge on one
credit.

GDPR[personal-data]: only ids and statuses are stored from notifications; buyer details stay at Paddle.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

import sentry_sdk
import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.billing import BINDING_KEY, RECOVERY_KEY, expire_stale_claims, hash_binding, recover_creation
from rm_core.db.models import (
    BillingAdjustment,
    BillingEvent,
    BillingPurchase,
    PurchaseState,
    ReportCreditLot,
)
from rm_core.ledger import grant_paid_reports, lock_user, restore_purchase, reverse_purchase
from rm_core.paddle import Adjustment, PaddleClient, PaddleError, Transaction

log = structlog.get_logger(__name__)
LEASE = timedelta(seconds=60)
MAX_ATTEMPTS = 8
MAX_BACKOFF_S = 900
REVERSAL_WATCH = timedelta(
    days=60
)  # how long after a grant a missed refund or chargeback is still looked for
REVERSAL_RECHECK = timedelta(minutes=15)
TRANSACTION_EVENTS = frozenset(
    {"transaction.completed", "transaction.updated", "transaction.payment_failed", "transaction.canceled"}
)
ADJUSTMENT_EVENTS = frozenset({"adjustment.created", "adjustment.updated"})
REVERSING_ACTIONS = frozenset({"refund", "chargeback", "chargeback_warning", "credit"})
CASH_REVERSALS = frozenset({"refund", "chargeback"})  # they take money back and count toward a full reversal
REVERSAL_UNDONE = frozenset({"chargeback_reverse"})
WARNINGS = frozenset({"chargeback_warning"})
OPEN_STATUSES = frozenset({"pending_approval", "pending"})


@dataclass(frozen=True)
class Received:
    event_pk: int | None  # None for a duplicate
    duplicate: bool


async def record_event(session: AsyncSession, *, environment: str, event: dict[str, Any]) -> Received:
    """Insert one notification (already signature-verified) or recognise a duplicate. Keeps only what
    processing needs. The caller commits."""
    raw = event.get("data")
    data = cast("dict[str, object]", raw) if isinstance(raw, dict) else {}
    payload = {
        "transaction_id": str(data.get("transaction_id") or data.get("id") or "")[:64],
        "status": str(data.get("status") or "")[:32],
    }
    inserted = await session.scalar(
        insert(BillingEvent)
        .values(
            environment=environment,
            event_id=str(event["event_id"])[:64],
            notification_id=str(event["notification_id"])[:64] if event.get("notification_id") else None,
            event_type=str(event["event_type"])[:64],
            occurred_at=event.get("occurred_at"),
            payload=payload,
        )
        .on_conflict_do_nothing(constraint="uq_billing_event_env_event")
        .returning(BillingEvent.id)
    )
    return Received(inserted, inserted is None)


async def claim_pending(sm: async_sessionmaker[AsyncSession], limit: int = 20) -> list[int]:
    """Lease the next pending events; safe under many workers (`SKIP LOCKED`). A lease that ran out (worker
    death) makes the event claimable again."""
    async with sm() as session, session.begin():
        ids = list(
            (
                await session.scalars(
                    select(BillingEvent.id)
                    .where(
                        BillingEvent.status == "pending",
                        (BillingEvent.lease_until.is_(None)) | (BillingEvent.lease_until < func.now()),
                    )
                    .order_by(BillingEvent.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        if ids:
            await session.execute(
                update(BillingEvent)
                .where(BillingEvent.id.in_(ids))
                .values(lease_until=func.now() + LEASE, attempts=BillingEvent.attempts + 1)
            )
        return ids


async def _finish_event(
    sm: async_sessionmaker[AsyncSession],
    event_pk: int,
    status: str,
    *,
    error_code: str | None = None,
    purchase_id: UUID | None = None,
) -> None:
    async with sm() as session, session.begin():
        await session.execute(
            update(BillingEvent)
            .where(BillingEvent.id == event_pk)
            .values(status=status, lease_until=None, error_code=error_code, purchase_id=purchase_id)
        )


def mismatch(txn: Transaction, purchase: BillingPurchase) -> str | None:
    """Why this completed transaction must not be granted against this purchase, or None if it matches the
    purchase's own snapshot exactly."""
    data = txn.custom_data or {}
    token = data.get(BINDING_KEY)
    item = txn.items[0] if len(txn.items) == 1 else None
    checks = (
        ("NOT_OUR_REFERENCE", data.get(RECOVERY_KEY) == str(purchase.id) and isinstance(token, str)),
        ("BINDING_MISMATCH", isinstance(token, str) and hash_binding(token) == purchase.binding_hash),
        ("SECOND_TRANSACTION", purchase.provider_txn_id in (None, txn.id)),
        ("ITEM_COUNT", item is not None),
        (
            "WRONG_PRICE_OR_QUANTITY",
            item is not None and item.price_id == purchase.price_id and item.quantity == 1,
        ),
        ("WRONG_TOTAL", txn.currency_code == purchase.currency and txn.total_minor == purchase.amount_minor),
        ("DISCOUNT", txn.discount_id is None),
        ("SUBSCRIPTION", txn.subscription_id is None),
    )
    return next((code for code, ok in checks if not ok), None)


def reversed_minor(adjustments: list[Adjustment]) -> tuple[int, bool]:
    """(approved reversal total in grosze, whether any non-approved reversal is still open)."""
    approved = sum(
        a.total_minor or 0 for a in adjustments if a.action in REVERSING_ACTIONS and a.status == "approved"
    )
    open_ = any(
        a.action in REVERSING_ACTIONS and a.status not in {"approved", "rejected"} for a in adjustments
    )
    return approved, open_


async def _mark(sm: async_sessionmaker[AsyncSession], purchase_id: UUID, **values: object) -> None:
    async with sm() as session, session.begin():
        await session.execute(
            update(BillingPurchase)
            .where(BillingPurchase.id == purchase_id)
            .values(updated_at=func.now(), **values)
        )


async def _grant(sm: async_sessionmaker[AsyncSession], purchase_id: UUID, txn: Transaction) -> str:
    """The atomic application: lock order user -> account -> lots -> purchase, one transaction."""
    async with sm() as session, session.begin():
        owner = await session.scalar(select(BillingPurchase.user_id).where(BillingPurchase.id == purchase_id))
        if owner is None:  # the account was deleted before payment completed: pay-back, not a new account
            await session.execute(
                update(BillingPurchase)
                .where(BillingPurchase.id == purchase_id)
                .values(state=PurchaseState.review, error_code="ACCOUNT_DELETED", provider_txn_id=txn.id)
            )
            return "review"
        await lock_user(session, owner)
        purchase = await session.scalar(
            select(BillingPurchase).where(BillingPurchase.id == purchase_id).with_for_update()
        )
        assert purchase is not None  # noqa: S101
        if purchase.state in (PurchaseState.granted, PurchaseState.refunded):
            return "already"  # a duplicate delivery or the reconciler: converges on the single grant
        grant_ref = f"paddle:{purchase.environment}:{txn.id}:grant"
        _, ledger_id = await grant_paid_reports(
            session, owner, purchase.reports, grant_ref=grant_ref, purchase_id=purchase.id
        )
        await session.execute(
            update(BillingPurchase)
            .where(BillingPurchase.id == purchase.id)
            .values(
                state=PurchaseState.granted,
                provider_txn_id=txn.id,
                provider_status=txn.status,
                customer_id=txn.customer_id,
                grant_ledger_id=ledger_id,
                paid_at=func.coalesce(BillingPurchase.paid_at, func.now()),
                granted_at=func.now(),
                error_code=None,
                lease_until=None,
                updated_at=func.now(),
            )
        )
    return "granted"


async def _find_purchase(
    sm: async_sessionmaker[AsyncSession], txn: Transaction, environment: str
) -> BillingPurchase | None:
    """Our purchase for this transaction: by the reference we put in `custom_data`, else by the linked id."""
    raw_id = (txn.custom_data or {}).get(RECOVERY_KEY)
    purchase_id: UUID | None = None
    if isinstance(raw_id, str):
        try:
            purchase_id = UUID(raw_id)
        except ValueError:
            purchase_id = None
    async with sm() as session:
        if purchase_id is not None:
            found = await session.scalar(
                select(BillingPurchase).where(
                    BillingPurchase.id == purchase_id, BillingPurchase.environment == environment
                )
            )
            if found is not None:
                return found
        return await session.scalar(
            select(BillingPurchase).where(
                BillingPurchase.provider_txn_id == txn.id, BillingPurchase.environment == environment
            )
        )


async def _settle_completed(
    sm: async_sessionmaker[AsyncSession], client: PaddleClient, purchase: BillingPurchase, txn: Transaction
) -> str:
    reason = mismatch(txn, purchase)
    if reason is not None:
        await _mark(sm, purchase.id, state=PurchaseState.review, error_code=reason, provider_txn_id=txn.id)
        return "review"
    reversed_total, open_reversal = reversed_minor(await client.list_adjustments(txn.id))
    if reversed_total >= purchase.amount_minor:  # refunded or charged back before we granted: net zero
        await _mark(
            sm,
            purchase.id,
            state=PurchaseState.refunded,
            provider_txn_id=txn.id,
            paid_at=func.now(),
            refunded_at=func.now(),
        )
        return "refunded"
    if reversed_total or open_reversal:
        await _mark(
            sm, purchase.id, state=PurchaseState.review, error_code="PARTIAL_REVERSAL", provider_txn_id=txn.id
        )
        return "review"
    return await _grant(sm, purchase.id, txn)


async def apply_transaction(
    sm: async_sessionmaker[AsyncSession], client: PaddleClient, transaction_id: str, *, environment: str
) -> tuple[str, UUID | None]:
    """Bring our purchase in line with the transaction as Paddle reports it **now**. Returns
    (outcome, purchase id): `granted`, `already`, `pending` (not completed yet), `refunded`, `review` or
    `unknown` (no purchase of ours)."""
    txn = await client.get_transaction(transaction_id)
    purchase = await _find_purchase(sm, txn, environment)
    if purchase is None:
        return "unknown", None
    if txn.status != "completed":
        # Never regress: a later failed attempt can be followed by a successful payment, and a granted
        # purchase stays granted. Only record what Paddle says while we are still waiting.
        if purchase.state in (PurchaseState.created, PurchaseState.creation_unknown, PurchaseState.creating):
            await _mark(sm, purchase.id, provider_status=txn.status)
        return "pending", purchase.id
    if purchase.state in (PurchaseState.granted, PurchaseState.refunded):
        return "already", purchase.id
    return await _settle_completed(sm, client, purchase, txn), purchase.id


async def _record_adjustments(
    sm: async_sessionmaker[AsyncSession], purchase_id: UUID, environment: str, adjustments: list[Adjustment]
) -> None:
    async with sm() as session, session.begin():
        for a in adjustments:
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
                .on_conflict_do_update(
                    constraint="uq_billing_adjustment_env_id",
                    set_={"status": a.status, "total_minor": a.total_minor, "updated_at": func.now()},
                )
            )


def net_reversed(adjustments: list[Adjustment]) -> tuple[int, bool, bool]:
    """(approved cash reversed minus approved reversals-of-reversals, any open request, any chargeback
    warning). Recomputed from the whole current set each time, so replays and ordering cannot double count."""
    taken = sum(
        a.total_minor or 0 for a in adjustments if a.action in CASH_REVERSALS and a.status == "approved"
    )
    undone = sum(
        a.total_minor or 0 for a in adjustments if a.action in REVERSAL_UNDONE and a.status == "approved"
    )
    is_open = any(a.action in CASH_REVERSALS and a.status in OPEN_STATUSES for a in adjustments)
    warned = any(a.action in WARNINGS and a.status != "rejected" for a in adjustments)
    return max(0, taken - undone), is_open, warned


def decide_effect(
    state: str, error_code: str | None, amount: int, net: int, *, is_open: bool, warned: bool, has_owner: bool
) -> str:
    """The pure rule from the current net state: `reverse`, `freeze:<code>`, `restore`, `clear`, or `none`."""
    refunded = state == PurchaseState.refunded
    in_scope = state in (PurchaseState.granted, PurchaseState.refunded, PurchaseState.review)
    contested = net > 0 or is_open or warned
    code = "PARTIAL_REVERSAL" if net > 0 else "CHARGEBACK_WARNING" if warned else "REFUND_PENDING"
    rules = (
        (not in_scope, "none"),  # not granted yet: the grant itself looks at adjustments
        (net >= amount and has_owner, "none" if refunded else "reverse"),
        (
            contested,
            "none" if refunded else f"freeze:{code}",
        ),  # part of a full reversal undone: wait for zero
        (refunded and has_owner, "restore"),
        (state == PurchaseState.review and error_code in FROZEN_CODES, "clear"),
    )
    return next((effect for applies, effect in rules if applies), "none")


FROZEN_CODES = frozenset({"PARTIAL_REVERSAL", "CHARGEBACK_WARNING", "REFUND_PENDING"})


async def _apply_net_effect(
    sm: async_sessionmaker[AsyncSession], purchase_id: UUID, net: int, *, is_open: bool, warned: bool
) -> str:
    """One transaction under the fixed lock order: reverse, restore, freeze or clear, from the net state."""
    async with sm() as session, session.begin():
        owner = await session.scalar(select(BillingPurchase.user_id).where(BillingPurchase.id == purchase_id))
        if owner is not None:
            await lock_user(session, owner)
        purchase = await session.scalar(
            select(BillingPurchase).where(BillingPurchase.id == purchase_id).with_for_update()
        )
        assert purchase is not None  # noqa: S101
        effect = decide_effect(
            purchase.state,
            purchase.error_code,
            purchase.amount_minor,
            net,
            is_open=is_open,
            warned=warned,
            has_owner=owner is not None,
        )
        lot = await session.scalar(select(ReportCreditLot).where(ReportCreditLot.purchase_id == purchase_id))
        if effect == "reverse":
            await reverse_purchase(session, purchase_id)
            purchase.state, purchase.refunded_at, purchase.error_code = (
                PurchaseState.refunded,
                func.now(),
                None,
            )
        elif effect.startswith("freeze:"):
            if lot is not None:
                lot.frozen = True
            purchase.state, purchase.error_code = PurchaseState.review, effect.split(":", 1)[1]
        elif effect == "restore":
            await restore_purchase(session, purchase_id)
            purchase.state, purchase.refunded_at, purchase.error_code = PurchaseState.granted, None, None
        elif effect == "clear":
            if lot is not None and lot.reversed_at is None:
                lot.frozen = False
            purchase.state, purchase.error_code = PurchaseState.granted, None
        return {"reverse": "reversed", "restore": "restored", "clear": "cleared", "none": "unchanged"}.get(
            effect, "review"
        )


async def apply_reversals(
    sm: async_sessionmaker[AsyncSession], client: PaddleClient, transaction_id: str, *, environment: str
) -> tuple[str, UUID | None]:
    """Apply refunds, chargebacks and their reversals as Paddle reports them now (docs/PADDLE-INTEGRATION.md
    section 6). Returns (outcome, purchase id)."""
    async with sm() as session:
        purchase = await session.scalar(
            select(BillingPurchase).where(
                BillingPurchase.provider_txn_id == transaction_id, BillingPurchase.environment == environment
            )
        )
    if purchase is None:
        return "unknown", None
    adjustments = await client.list_adjustments(transaction_id)
    await _record_adjustments(sm, purchase.id, environment, adjustments)
    net, is_open, warned = net_reversed(adjustments)
    outcome = await _apply_net_effect(sm, purchase.id, net, is_open=is_open, warned=warned)
    if outcome in {"review", "reversed"} and (warned or outcome == "review"):
        sentry_sdk.capture_message(
            f"billing reversal needs attention: purchase {purchase.id} -> {outcome}", level="warning"
        )
    return outcome, purchase.id


async def process_event(sm: async_sessionmaker[AsyncSession], client: PaddleClient, event_pk: int) -> str:
    """Process one leased event. Transient failures keep it pending with a backoff; exhausting the attempts
    fails it loudly. Never raises for an expected business outcome."""
    async with sm() as session:
        event = await session.get(BillingEvent, event_pk)
    if event is None or event.status != "pending":
        return "skipped"
    known = event.event_type in TRANSACTION_EVENTS or event.event_type in ADJUSTMENT_EVENTS
    if not known or not event.payload.get("transaction_id"):
        await _finish_event(sm, event_pk, "ignored")
        return "ignored"
    transaction_id = str(event.payload["transaction_id"])
    try:
        if event.event_type in ADJUSTMENT_EVENTS:
            outcome, purchase_id = await apply_reversals(
                sm, client, transaction_id, environment=event.environment
            )
        else:
            outcome, purchase_id = await apply_transaction(
                sm, client, transaction_id, environment=event.environment
            )
    except PaddleError:
        if event.attempts >= MAX_ATTEMPTS:
            sentry_sdk.capture_message(
                f"billing event {event_pk} failed after {event.attempts} attempts", level="error"
            )
            await _finish_event(sm, event_pk, "failed", error_code="RETRIES_EXHAUSTED")
            return "failed"
        delay = min(MAX_BACKOFF_S, 2**event.attempts * 5)
        async with sm() as session, session.begin():
            await session.execute(
                update(BillingEvent)
                .where(BillingEvent.id == event_pk)
                .values(lease_until=func.now() + timedelta(seconds=delay))
            )
        return "retry"
    status = {"review": "review", "unknown": "ignored"}.get(outcome, "processed")
    await _finish_event(
        sm,
        event_pk,
        status,
        error_code="NO_PURCHASE" if outcome == "unknown" else None,
        purchase_id=purchase_id,
    )
    return outcome


async def reconcile_purchases(
    sm: async_sessionmaker[AsyncSession],
    client: PaddleClient,
    *,
    settle_after: timedelta = timedelta(minutes=2),
) -> dict[str, int]:
    """Recover what a missed webhook or a dead worker left behind, without any notification: ambiguous
    creations are looked up by reference, and purchases that have a transaction but no grant are read from
    Paddle. Safe to run concurrently with event processing."""

    done: dict[str, int] = {}
    async with sm() as session, session.begin():
        await expire_stale_claims(session)
    async with sm() as session:
        unknown = (
            await session.scalars(
                select(BillingPurchase).where(BillingPurchase.state == PurchaseState.creation_unknown)
            )
        ).all()
        waiting = (
            await session.scalars(
                select(BillingPurchase).where(
                    BillingPurchase.state == PurchaseState.created,
                    BillingPurchase.provider_txn_id.is_not(None),
                    BillingPurchase.updated_at < func.now() - settle_after,
                )
            )
        ).all()
    async with sm() as session:
        settled = (
            await session.scalars(
                select(BillingPurchase).where(
                    BillingPurchase.state.in_(
                        (PurchaseState.granted, PurchaseState.refunded, PurchaseState.review)
                    ),
                    BillingPurchase.provider_txn_id.is_not(None),
                    BillingPurchase.granted_at > func.now() - REVERSAL_WATCH,
                    BillingPurchase.updated_at < func.now() - REVERSAL_RECHECK,
                )
            )
        ).all()
    for purchase in settled:  # a reversal whose notification never came; rechecked every REVERSAL_RECHECK
        if purchase.provider_txn_id is None:
            continue
        try:
            outcome, _ = await apply_reversals(
                sm, client, purchase.provider_txn_id, environment=purchase.environment
            )
        except PaddleError:
            outcome = "error"
        await _mark(sm, purchase.id)  # bumps updated_at: the next check is one interval away
        done[f"reversal:{outcome}"] = done.get(f"reversal:{outcome}", 0) + 1
    for purchase in unknown:
        await recover_creation(sm, client, purchase)
    for purchase in waiting:
        if purchase.provider_txn_id is None:
            continue
        try:
            outcome, _ = await apply_transaction(
                sm, client, purchase.provider_txn_id, environment=purchase.environment
            )
        except PaddleError:
            outcome = "error"
        done[outcome] = done.get(outcome, 0) + 1
    return done
