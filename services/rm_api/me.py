"""`/api/me/*`: the data-subject rights endpoints (blueprint §2 Route map; docs/RUNBOOK-GDPR.md).

GDPR[erasure]: `DELETE /api/me` removes every tenant-owned row (FK cascade) and the processor's customer.
GDPR[personal-data]: `GET /api/me/export` returns everything held about the caller, to the caller only.
"""

import structlog
from fastapi import APIRouter, Request, Response
from rm_contracts.auth import AccountDelete
from rm_contracts.problems import ProblemCode
from rm_core.db.models import StripeCustomer
from rm_core.privacy import UserDataExport, delete_account, export_user_data, user_hash
from rm_core.ratelimit import hit
from sqlalchemy import select

from rm_api.auth.sessions import clear_session_cookie, revoke_all_sessions
from rm_api.billing_erasure import BillingEraser, BillingUnavailable
from rm_api.deps import PrincipalDep, SessionDep, SettingsDep
from rm_api.problems import Problem

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/me", tags=["me"])
EXPORTS_PER_HOUR = 5
HOUR_S = 3600


@router.get("/export", response_model=UserDataExport)
async def export_my_data(response: Response, db: SessionDep, principal: PrincipalDep) -> UserDataExport:
    """Everything we hold about the caller as one JSON document (access request). Limited to 5 per hour."""
    decision = await hit(db, "export", principal.user_id, limit=EXPORTS_PER_HOUR, window_s=HOUR_S)
    if not decision.allowed:
        raise Problem.rate_limited(decision.retry_after_s)
    data = await export_user_data(db, principal.user_id)
    if data is None:  # the user vanished between authentication and now
        raise Problem.unauthorized(ProblemCode.UNAUTHENTICATED, "Sign in required")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = 'attachment; filename="rentmonitor-export.json"'
    return data


@router.delete("", status_code=204)
async def delete_my_account(
    body: AccountDelete, request: Request, db: SessionDep, principal: PrincipalDep, settings: SettingsDep
) -> Response:
    """Erase the account. Idempotent and retryable: the processor is erased first, so a failure at either
    step leaves
    the request safe to repeat (deleting an already deleted Stripe customer succeeds)."""
    if body.confirm_email.strip().lower() != principal.email:
        raise Problem(422, ProblemCode.CONFIRMATION_MISMATCH, "Type your account email address to confirm")
    customer_id = await db.scalar(
        select(StripeCustomer.stripe_customer_id).where(StripeCustomer.user_id == principal.user_id)
    )
    if customer_id is not None:
        eraser: BillingEraser | None = request.app.state.billing_eraser
        if eraser is None:
            log.error("account_erasure_blocked_no_billing_eraser", user_hash=user_hash(principal.user_id))
            raise Problem(
                503, ProblemCode.NOT_READY, "Billing erasure is not available yet; nothing was deleted"
            )
        try:
            await eraser.delete_customer(customer_id)
        except BillingUnavailable:
            raise Problem(
                503, ProblemCode.NOT_READY, "Payment provider unavailable; nothing was deleted"
            ) from None
    await revoke_all_sessions(
        db, principal.user_id
    )  # NOTIFY first so every process drops the cached principal
    report = await delete_account(db, principal.user_id)
    log.info("account_erased", user_hash=user_hash(principal.user_id), deleted=report.deleted)
    out = Response(status_code=204)
    clear_session_cookie(out, settings)
    return out
