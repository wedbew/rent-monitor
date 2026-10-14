"""Checkout intents for report packs (docs/PADDLE-INTEGRATION.md section 3): the durable purchase record,
the creation lease and recovery of an ambiguous creation. The grant, webhook and refunds are later slices.

Rules: the intent is committed before any network call; no database row is locked across HTTP; a creation
that may or may not have reached Paddle is never repeated blindly. Matching a transaction to a purchase uses
our own server-generated reference and binding token, never the buyer's email.

GDPR[personal-data]: `billing_purchase` rows reference the user (SET NULL on erasure), keep a pseudonymous
owner hash for accounting and the provider's customer id (RM-217).
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.billing_catalog import Catalog
from rm_core.db.models import BillingPack, BillingPurchase, PurchaseState
from rm_core.paddle import PaddleAmbiguousError, PaddleClient, PaddleError, Transaction

log = structlog.get_logger(__name__)
CREATION_LEASE = timedelta(seconds=30)
RECOVERY_KEY = "purchase_id"
BINDING_KEY = "binding"
MINOR_PER_UNIT = 100


class IdempotencyConflictError(Exception):
    """The same request key was used for a different pack."""


def hash_binding(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def owner_ref(user_id: str) -> str:
    return hashlib.sha256(f"owner:{user_id}".encode()).hexdigest()


def gross_pln(amount_minor: int) -> Decimal:
    return Decimal(amount_minor) / MINOR_PER_UNIT


async def sync_catalog(session: AsyncSession, catalog: Catalog) -> list[BillingPack]:
    """Mirror the configured, owner-approved catalog into `billing_pack`. An unchanged pack keeps its
    version; a changed price or id becomes a new version and the old one is deactivated but kept (sold
    versions are immutable). Returns the active rows."""
    active: list[BillingPack] = []
    for pack in catalog.packs:
        current = await session.scalar(
            select(BillingPack).where(
                BillingPack.code == pack.code,
                BillingPack.environment == catalog.environment,
                BillingPack.active.is_(True),
            )
        )
        if current is not None and (current.price_id, current.amount_minor) == (
            pack.price_id,
            pack.amount_minor,
        ):
            active.append(current)
            continue
        next_version = (
            await session.scalar(
                select(func.coalesce(func.max(BillingPack.catalog_version), 0)).where(
                    BillingPack.code == pack.code, BillingPack.environment == catalog.environment
                )
            )
            or 0
        ) + 1
        if current is not None:
            current.active = False
            await session.flush()
        row = BillingPack(
            code=pack.code,
            catalog_version=next_version,
            environment=catalog.environment,
            reports=pack.reports,
            price_id=pack.price_id,
            amount_minor=pack.amount_minor,
            active=True,
        )
        session.add(row)
        await session.flush()
        active.append(row)
    return active


@dataclass(frozen=True)
class Intent:
    purchase: BillingPurchase
    created: bool  # False when the same request key already existed


async def create_intent(
    session: AsyncSession, *, user_id: str, request_key: UUID, pack: BillingPack
) -> Intent:
    """Insert the durable intent (unique per user and request key), or return the existing one. Raises
    `IdempotencyConflictError` if that key was used for another pack."""
    inserted = await session.scalar(
        insert(BillingPurchase)
        .values(
            id=uuid4(),
            user_id=user_id,
            owner_ref=owner_ref(user_id),
            request_key=request_key,
            environment=pack.environment,
            pack_code=pack.code,
            catalog_version=pack.catalog_version,
            reports=pack.reports,
            amount_minor=pack.amount_minor,
            price_id=pack.price_id,
            binding_hash=hash_binding(secrets.token_urlsafe(32)),  # placeholder, replaced at claim time
        )
        .on_conflict_do_nothing(constraint="uq_purchase_user_request")
        .returning(BillingPurchase.id)
    )
    if inserted is not None:
        row = await session.get_one(BillingPurchase, inserted, populate_existing=True)
        return Intent(row, True)
    existing = await session.scalar(
        select(BillingPurchase).where(
            BillingPurchase.user_id == user_id, BillingPurchase.request_key == request_key
        )
    )
    assert existing is not None  # the conflict proves it exists  # noqa: S101
    if (existing.pack_code, existing.catalog_version) != (pack.code, pack.catalog_version):
        raise IdempotencyConflictError
    return Intent(existing, False)


async def claim_creation(session: AsyncSession, purchase_id: UUID) -> str | None:
    """Short lease so concurrent requests cannot create two transactions. Returns the binding token the
    caller must put in the Paddle request (only its hash is stored, replaced here because nothing has been
    sent yet), or None if another caller already holds or finished the claim."""
    binding = secrets.token_urlsafe(32)
    claimed = await session.scalar(
        update(BillingPurchase)
        .where(BillingPurchase.id == purchase_id, BillingPurchase.state == PurchaseState.intent)
        .values(
            state=PurchaseState.creating,
            lease_until=func.now() + CREATION_LEASE,
            binding_hash=hash_binding(binding),
            updated_at=func.now(),
        )
        .returning(BillingPurchase.id)
    )
    return binding if claimed is not None else None


async def expire_stale_claims(session: AsyncSession) -> int:
    """A claim whose lease ran out may have reached Paddle before its holder died: it becomes
    `creation_unknown` (recover, never recreate)."""
    result = await session.execute(
        update(BillingPurchase)
        .where(BillingPurchase.state == PurchaseState.creating, BillingPurchase.lease_until < func.now())
        .values(state=PurchaseState.creation_unknown, error_code="LEASE_EXPIRED", updated_at=func.now())
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def _finish(sm: async_sessionmaker[AsyncSession], purchase_id: UUID, **values: object) -> None:
    async with sm() as session, session.begin():
        await session.execute(
            update(BillingPurchase)
            .where(BillingPurchase.id == purchase_id)
            .values(lease_until=None, updated_at=func.now(), **values)
        )


async def create_transaction(
    sm: async_sessionmaker[AsyncSession], client: PaddleClient, purchase: BillingPurchase, binding: str
) -> PurchaseState:
    """Call Paddle (no row locked, no transaction open) and record the outcome in its own short transaction.
    A definite failure is `failed`; an ambiguous one is `creation_unknown`, never replaced automatically."""
    custom = {RECOVERY_KEY: str(purchase.id), BINDING_KEY: binding}
    try:
        txn = await client.create_transaction(price_id=purchase.price_id, custom_data=custom)
    except PaddleAmbiguousError:
        await _finish(sm, purchase.id, state=PurchaseState.creation_unknown, error_code="CREATE_UNKNOWN")
        return PurchaseState.creation_unknown
    except PaddleError:
        log.warning("billing.create_failed", purchase_id=str(purchase.id))
        await _finish(sm, purchase.id, state=PurchaseState.failed, error_code="CREATE_FAILED")
        return PurchaseState.failed
    await _finish(
        sm,
        purchase.id,
        state=PurchaseState.created,
        provider_txn_id=txn.id,
        checkout_url=txn.checkout_url,
        provider_status=txn.status,
        error_code=None,
    )
    return PurchaseState.created


def _matches(txn: Transaction, purchase: BillingPurchase) -> bool:
    data = txn.custom_data or {}
    token = data.get(BINDING_KEY)
    return (
        data.get(RECOVERY_KEY) == str(purchase.id)
        and isinstance(token, str)
        and hash_binding(token) == purchase.binding_hash
    )


async def recover_creation(
    sm: async_sessionmaker[AsyncSession], client: PaddleClient, purchase: BillingPurchase
) -> PurchaseState:
    """After an ambiguous creation: look for a transaction that carries this purchase's reference **and**
    binding token among recent ones (one page; Paddle is not assumed to filter by custom data). Exactly one
    match is adopted, none leaves the purchase unknown (the person is told to wait, never to pay again),
    several go to manual review."""
    try:
        recent = await client.list_transactions(
            custom_data_key=RECOVERY_KEY, created_after=purchase.created_at.isoformat()
        )
    except PaddleError:
        return PurchaseState.creation_unknown
    found = [t for t in recent if _matches(t, purchase)]
    if not found:
        return PurchaseState.creation_unknown
    if len(found) > 1:
        await _finish(sm, purchase.id, state=PurchaseState.review, error_code="MULTIPLE_TRANSACTIONS")
        return PurchaseState.review
    txn = found[0]
    await _finish(
        sm,
        purchase.id,
        state=PurchaseState.created,
        provider_txn_id=txn.id,
        checkout_url=txn.checkout_url,
        provider_status=txn.status,
        error_code=None,
    )
    return PurchaseState.created
