"""`/api/auth/*`: Google ID-token sign-in, email magic link, sign-out, session list (blueprint §2 Route
map)."""

import secrets
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Request, Response
from rm_contracts.auth import EmailStart, EmailVerify, GoogleCredential, MeOut, SessionOut
from rm_contracts.problems import ProblemCode
from rm_core.db.models import LoginToken, User, UserSession
from rm_core.ledger import ensure_credit_account
from rm_core.ratelimit import hit
from sqlalchemy import func, select, update

from rm_api.auth.accounts import user_for_email, user_for_google
from rm_api.auth.google import (
    GoogleEmailUnverified,
    GoogleUnavailable,
    GoogleVerifier,
    InvalidGoogleToken,
)
from rm_api.auth.sessions import (
    clear_session_cookie,
    create_session,
    hash_token,
    revoke_all_sessions,
    revoke_session,
    set_session_cookie,
)
from rm_api.deps import OptionalPrincipalDep, PrincipalDep, SessionDep, SettingsDep
from rm_api.problems import Problem
from rm_api.queue import EmailQueue

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_LIMIT_PER_HOUR = 5
IP_LIMIT_PER_HOUR = 20
HOUR_S = 3600


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        role=user.role,
        email_verified=user.email_verified_at is not None,
    )


@router.post("/google", response_model=MeOut)
async def google_sign_in(
    body: GoogleCredential, request: Request, response: Response, db: SessionDep, settings: SettingsDep
) -> MeOut:
    # LEGAL/GDPR: see rm_api.auth.google (processor) and rm_api.auth.accounts (personal data).
    verifier: GoogleVerifier = request.app.state.google_verifier
    try:
        claims = await verifier.verify(body.credential)
    except InvalidGoogleToken:
        raise Problem.unauthorized(ProblemCode.INVALID_GOOGLE_TOKEN, "Invalid Google token") from None
    except GoogleEmailUnverified:
        # Hard call: no accounts from unverified Google emails; the SPA offers the magic link instead.
        raise Problem.unauthorized(
            ProblemCode.GOOGLE_EMAIL_UNVERIFIED, "Google email is not verified"
        ) from None
    except GoogleUnavailable:
        raise Problem(503, ProblemCode.NOT_READY, "Google sign-in is temporarily unavailable") from None
    user = await user_for_google(
        db, sub=claims.sub, email=claims.email, name=claims.name, picture=claims.picture
    )
    token = await create_session(
        db, user.id, user_agent=request.headers.get("user-agent"), ip=_ip(request), settings=settings
    )
    await ensure_credit_account(
        db, user.id, verified=user.email_verified_at is not None, signup_credits=settings.free_signup_credits
    )
    set_session_cookie(response, token, settings)
    log.info("sign_in", method="google", user_id=user.id)
    return _me(user)


@router.post("/email/start", status_code=204)
async def email_start(body: EmailStart, request: Request, db: SessionDep, settings: SettingsDep) -> Response:
    """Always 204: the response never reveals whether the address has an account."""
    email = body.email.strip().lower()
    for scope, subject, limit in (
        ("ml:email", email, EMAIL_LIMIT_PER_HOUR),
        ("ml:ip", _ip(request), IP_LIMIT_PER_HOUR),
    ):
        decision = await hit(db, scope, subject, limit=limit, window_s=HOUR_S)
        if not decision.allowed:
            raise Problem.rate_limited(decision.retry_after_s)
    token = secrets.token_urlsafe(32)
    db.add(
        LoginToken(
            token_hash=hash_token(token),
            email=email,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.magic_link_ttl_minutes),
        )
    )
    await (
        db.commit()
    )  # the token must exist before the mail can be opened; this is the blueprint's explicit commit
    queue: EmailQueue = request.app.state.email_queue
    # Fragment, not query string: never sent to servers, so proxies and mail scanners do not log it.
    await queue.send_magic_link(email=email, url=f"{settings.public_origin}/login/email#t={token}")
    log.info("magic_link_requested")
    return Response(status_code=204)


@router.post("/email/verify", response_model=MeOut)
async def email_verify(
    body: EmailVerify, request: Request, response: Response, db: SessionDep, settings: SettingsDep
) -> MeOut:
    email = (
        await db.execute(
            update(LoginToken)
            .where(
                LoginToken.token_hash == hash_token(body.token),
                LoginToken.used_at.is_(None),
                LoginToken.expires_at > func.now(),
            )
            .values(used_at=func.now())
            .returning(LoginToken.email)  # atomic single use: only one concurrent caller gets the row back
        )
    ).scalar_one_or_none()
    if email is None:
        raise Problem.unauthorized(ProblemCode.MAGIC_LINK_INVALID, "Link is invalid, used or expired")
    user = await user_for_email(db, email=email)
    token = await create_session(
        db, user.id, user_agent=request.headers.get("user-agent"), ip=_ip(request), settings=settings
    )
    await ensure_credit_account(db, user.id, verified=True, signup_credits=settings.free_signup_credits)
    set_session_cookie(response, token, settings)
    log.info("sign_in", method="email", user_id=user.id)
    return _me(user)


@router.post("/signout", status_code=204)
async def sign_out(
    response: Response, db: SessionDep, principal: OptionalPrincipalDep, settings: SettingsDep
) -> Response:
    """Idempotent: signing out without a valid session still clears the cookie."""
    if principal is not None:
        await revoke_session(db, principal)
    out = Response(status_code=204)
    clear_session_cookie(out, settings)
    return out


@router.post("/signout-all", status_code=204)
async def sign_out_everywhere(db: SessionDep, principal: PrincipalDep, settings: SettingsDep) -> Response:
    await revoke_all_sessions(db, principal.user_id)
    out = Response(status_code=204)
    clear_session_cookie(out, settings)
    return out


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: SessionDep, principal: PrincipalDep) -> list[SessionOut]:
    rows = (
        await db.execute(
            select(UserSession)
            .where(UserSession.user_id == principal.user_id, UserSession.expires_at > func.now())
            .order_by(UserSession.last_seen_at.desc())
            .limit(50)
        )
    ).scalars()
    return [
        SessionOut(
            id=row.id,
            current=row.token_hash == principal.token_hash,
            created_hint=row.last_seen_at,
            expires_at=row.expires_at,
            user_agent=row.user_agent,
            ip=row.ip,
        )
        for row in rows
    ]
