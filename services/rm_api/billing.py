"""`/api/billing`: report packs and checkout (docs/PADDLE-INTEGRATION.md section 3, RM-217).

The only things a browser chooses are a pack code and an idempotency key. Amounts, report counts, price ids
and users come from the server. The purchase intent is committed before Paddle is called; no row is locked
across HTTP; a creation that may or may not have reached Paddle is recovered, never repeated blindly. Browser
success means "payment processing": nothing is granted here (the signed webhook does that, #218).

GDPR[processor]: Paddle receives only our price id, quantity and opaque purchase references.
GDPR[personal-data]: purchases are returned to their owner only; another user's id is a 404.
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, Path, Query, Request, Response
from rm_contracts.billing import CheckoutRequest, InvoiceOut, PackOut, PacksOut, PurchaseOut, PurchasesOut
from rm_contracts.problems import ProblemCode
from rm_core.billing import (
    IdempotencyConflictError,
    claim_creation,
    create_intent,
    create_transaction,
    expire_stale_claims,
    gross_pln,
    recover_creation,
)
from rm_core.db.models import BillingPack, BillingPurchase, CreditAccount, PurchaseState
from rm_core.paddle import PaddleClient, PaddleError
from rm_core.ratelimit import hit
from sqlalchemy import select

from rm_api.deps import PrincipalDep, SessionDep
from rm_api.problems import Problem

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])
PER_MINUTE = 5
PER_HOUR = 20
PROCESSING = {PurchaseState.intent, PurchaseState.creating, PurchaseState.creation_unknown}


def _out(p: BillingPurchase) -> PurchaseOut:
    return PurchaseOut.model_validate(
        {
            "purchase_id": p.id,
            "pack_code": p.pack_code,
            "reports": p.reports,
            "gross_pln": gross_pln(p.amount_minor),
            "state": p.state,
            "transaction_id": p.provider_txn_id,
            "checkout_url": p.checkout_url,
            "created_at": p.created_at,
            "granted_at": p.granted_at,
            "refunded_at": p.refunded_at,
        }
    )  # validated: a code or state outside the contract would fail loudly here, not leak to the client


def _enabled(request: Request) -> tuple[PaddleClient, str]:
    client: PaddleClient | None = request.app.state.paddle
    catalog = request.app.state.catalog
    if client is None or catalog is None:
        raise Problem(503, ProblemCode.BILLING_UNAVAILABLE, "Purchases are not available yet")
    return client, str(catalog.environment)


@router.get("/packs", response_model=PacksOut)
async def list_packs(request: Request, db: SessionDep, principal: PrincipalDep) -> PacksOut:
    catalog = request.app.state.catalog
    if catalog is None or request.app.state.paddle is None:
        return PacksOut(enabled=False, packs=[])
    rows = (
        await db.scalars(
            select(BillingPack)
            .where(BillingPack.environment == catalog.environment, BillingPack.active.is_(True))
            .order_by(BillingPack.reports)
        )
    ).all()
    return PacksOut(
        enabled=bool(rows),
        packs=[
            PackOut.model_validate(
                {
                    "code": r.code,
                    "reports": r.reports,
                    "gross_pln": gross_pln(r.amount_minor),
                    "catalog_version": r.catalog_version,
                }
            )
            for r in rows
        ],
    )


@router.post("/checkout", response_model=PurchaseOut, responses={202: {"model": PurchaseOut}})
async def checkout(
    body: CheckoutRequest,
    request: Request,
    response: Response,
    *,
    db: SessionDep,
    principal: PrincipalDep,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> PurchaseOut:
    client, environment = _enabled(request)
    if not principal.email_verified:
        raise Problem(403, ProblemCode.EMAIL_NOT_VERIFIED, "Verify your email address first")
    for scope, limit, window in (("checkout:min", PER_MINUTE, 60), ("checkout:hour", PER_HOUR, 3600)):
        decision = await hit(db, scope, principal.user_id, limit=limit, window_s=window)
        if not decision.allowed:
            await db.commit()  # the count must survive the refusal
            raise Problem.rate_limited(decision.retry_after_s)
    if await db.scalar(select(CreditAccount.billing_hold).where(CreditAccount.user_id == principal.user_id)):
        raise Problem(  # no payments for units the account cannot use while a billing review is open
            403, ProblemCode.BILLING_HOLD, "Your account is on a billing review; contact support"
        )
    pack = await db.scalar(
        select(BillingPack).where(
            BillingPack.code == body.pack_code,
            BillingPack.environment == environment,
            BillingPack.active.is_(True),
        )
    )
    if pack is None:
        raise Problem(503, ProblemCode.BILLING_UNAVAILABLE, "This pack is not available")
    try:
        intent = await create_intent(db, user_id=principal.user_id, request_key=idempotency_key, pack=pack)
    except IdempotencyConflictError:
        await db.rollback()
        raise Problem(
            409, ProblemCode.IDEMPOTENCY_CONFLICT, "This Idempotency-Key was used for a different pack"
        ) from None
    purchase_id = intent.purchase.id
    await expire_stale_claims(db)  # a dead claimant's creation becomes "unknown": recover, never recreate
    await db.commit()  # the intent is durable before any network call

    sm = request.app.state.sessionmaker
    async with sm() as session, session.begin():
        binding = await claim_creation(session, purchase_id)
    async with sm() as session:
        purchase = await session.get_one(BillingPurchase, purchase_id, populate_existing=True)
    if binding is not None:
        await create_transaction(sm, client, purchase, binding)
    elif purchase.state == PurchaseState.creation_unknown:
        await recover_creation(sm, client, purchase)
    async with sm() as session:
        purchase = await session.get_one(BillingPurchase, purchase_id, populate_existing=True)
    if purchase.state == PurchaseState.failed:
        raise Problem(
            502,
            ProblemCode.BILLING_PROVIDER_ERROR,
            "The payment provider could not start this purchase",
            purchase_id=str(purchase.id),
        )
    if purchase.state in PROCESSING:
        response.status_code = 202  # processing: ask again with the same key, never pay twice
    return _out(purchase)


@router.get("/purchases", response_model=PurchasesOut)
async def list_purchases(
    db: SessionDep, principal: PrincipalDep, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> PurchasesOut:
    rows = (
        await db.scalars(
            select(BillingPurchase)
            .where(BillingPurchase.user_id == principal.user_id)
            .order_by(BillingPurchase.created_at.desc(), BillingPurchase.id)
            .limit(limit)
        )
    ).all()
    return PurchasesOut(purchases=[_out(p) for p in rows])


@router.get("/purchases/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(
    purchase_id: Annotated[UUID, Path()], db: SessionDep, principal: PrincipalDep
) -> PurchaseOut:
    purchase = await db.scalar(
        select(BillingPurchase).where(
            BillingPurchase.id == purchase_id, BillingPurchase.user_id == principal.user_id
        )
    )
    if purchase is None:
        raise Problem.not_found("Purchase")  # unknown and foreign look the same
    return _out(purchase)


@router.get("/purchases/{purchase_id}/invoice", response_model=InvoiceOut)
async def get_invoice(
    purchase_id: Annotated[UUID, Path()],
    request: Request,
    response: Response,
    db: SessionDep,
    principal: PrincipalDep,
) -> InvoiceOut:
    """The seller's document for this sale, obtained from Paddle on demand after the ownership check.
    Paddle is the seller and issues it; the product issues no second customer invoice for the same sale."""
    client, _ = _enabled(request)
    purchase = await db.scalar(
        select(BillingPurchase).where(
            BillingPurchase.id == purchase_id, BillingPurchase.user_id == principal.user_id
        )
    )
    if purchase is None:
        raise Problem.not_found("Purchase")
    if purchase.provider_txn_id is None or purchase.state not in {
        PurchaseState.granted,
        PurchaseState.refunded,
    }:
        raise Problem(409, ProblemCode.PURCHASE_NOT_REFUNDABLE, "There is no invoice for this purchase yet")
    decision = await hit(db, "invoice", principal.user_id, limit=10, window_s=60)
    if not decision.allowed:
        await db.commit()
        raise Problem.rate_limited(decision.retry_after_s)
    await db.commit()  # release the connection before the network call
    try:
        url = await client.get_invoice_url(purchase.provider_txn_id)
    except PaddleError:
        raise Problem(
            502, ProblemCode.BILLING_PROVIDER_ERROR, "The invoice is not available right now"
        ) from None
    response.headers["Cache-Control"] = "no-store"  # the link is short-lived and personal
    return InvoiceOut(url=url)
