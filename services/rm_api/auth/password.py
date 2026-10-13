"""Email and password registration (ADR 0013, docs/PASSWORD-AUTH-SPEC.md sections 1 to 5): `register`,
`register/verify`, `register/resend`. Login is #204, recovery and change are #205.

No account exists until the mailed link is used. Registration stores a pending, single-use, purpose-bound
token (SHA-256 at rest) with the Argon2id hash of the chosen password; the link creates the verified account,
its credential and the signup credits in one transaction. Every answer to an unauthenticated request is the
same 202 whatever the address is.

GDPR[personal-data]: email address and a password hash held in `auth_token` until used or expired, then
purged by the retention job; `user_credential` cascades with the account (RM-203).
"""

import secrets
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Request, Response
from rm_contracts.auth import Accepted, MeOut, RegisterRequest, RegisterVerify, ResendRequest
from rm_contracts.problems import ProblemCode
from rm_core.db.models import AuthToken, User, UserCredential
from rm_core.ledger import ensure_credit_account
from rm_core.ratelimit import hit
from rm_core.settings import Settings
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from rm_api.auth.accounts import new_verified_user
from rm_api.auth.passwords import PasswordHasher, check_policy
from rm_api.auth.router import HOUR_S, _ip, _me  # pyright: ignore[reportPrivateUsage]
from rm_api.auth.sessions import create_session, hash_token, set_session_cookie
from rm_api.deps import SessionDep, SettingsDep
from rm_api.problems import Problem
from rm_api.queue import EmailQueue

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

PURPOSE_REGISTER = "register"
REGISTER_PER_EMAIL = 5  # per hour (spec section 5)
REGISTER_PER_IP = 20
VERIFY_PER_IP = 30


def _hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher | None = getattr(request.app.state, "password_hasher", None)
    if hasher is None:
        hasher = PasswordHasher(request.app.state.settings)
        request.app.state.password_hasher = hasher
    return hasher


async def _throttle(
    db: AsyncSession, request: Request, scope: str, email: str | None, *, per_email: int, per_ip: int
) -> None:
    checks = [(f"{scope}:ip", _ip(request), per_ip)]
    if email is not None:
        checks.append((f"{scope}:email", email, per_email))
    for key, subject, limit in checks:
        decision = await hit(db, key, subject, limit=limit, window_s=HOUR_S)
        if not decision.allowed:
            await db.commit()  # the count must survive the refusal
            raise Problem.rate_limited(decision.retry_after_s)


async def _issue_register_token(db: AsyncSession, settings: Settings, email: str, password_hash: str) -> str:
    """Replace any live registration for the address (last one wins) and store the new one. Serialised per
    address by an advisory lock so concurrent registrations cannot collide on the live-token index."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"auth_token:{email}"})
    await db.execute(
        update(AuthToken)
        .where(AuthToken.email == email, AuthToken.purpose == PURPOSE_REGISTER, AuthToken.used_at.is_(None))
        .values(used_at=func.now())
    )
    token = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            token_hash=hash_token(token),
            purpose=PURPOSE_REGISTER,
            email=email,
            password_hash=password_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=settings.register_token_ttl_hours),
        )
    )
    return token


def _register_url(settings: Settings, token: str) -> str:
    # Fragment, not query string: never sent to servers, so proxies and mail scanners do not log it.
    return f"{settings.public_origin}/signup/verify#t={token}"


@router.post("/register", status_code=202, response_model=Accepted)
async def register(
    body: RegisterRequest, request: Request, db: SessionDep, settings: SettingsDep
) -> Accepted:
    email = body.email.strip().lower()
    await _throttle(db, request, "reg", email, per_email=REGISTER_PER_EMAIL, per_ip=REGISTER_PER_IP)
    reason = check_policy(body.password, email)
    if reason is not None:
        await db.commit()
        raise Problem(422, ProblemCode.WEAK_PASSWORD, "Password does not meet the policy", reason=reason)
    password_hash = await _hasher(request).hash(
        body.password
    )  # always, so timing does not reveal the address
    queue: EmailQueue = request.app.state.email_queue
    exists = await db.scalar(select(User.id).where(User.email == email))
    if exists is not None:
        await db.commit()
        await queue.send_auth_mail(kind="account_exists", email=email, url=None)
    else:
        token = await _issue_register_token(db, settings, email, password_hash)
        await db.commit()  # the token must exist before the mail can be opened
        await queue.send_auth_mail(kind="register", email=email, url=_register_url(settings, token))
    log.info("register_requested")
    return Accepted()


@router.post("/register/resend", status_code=202, response_model=Accepted)
async def register_resend(
    body: ResendRequest, request: Request, db: SessionDep, settings: SettingsDep
) -> Accepted:
    """Re-mail a pending registration with a fresh token (the old link stops working). The password hash
    stays the one chosen at registration; an address with no pending registration gets nothing."""
    email = body.email.strip().lower()
    await _throttle(db, request, "reg", email, per_email=REGISTER_PER_EMAIL, per_ip=REGISTER_PER_IP)
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"auth_token:{email}"})
    pending = await db.scalar(
        select(AuthToken.password_hash).where(
            AuthToken.email == email,
            AuthToken.purpose == PURPOSE_REGISTER,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > func.now(),
        )
    )
    token = None
    if pending is not None:
        token = await _issue_register_token(db, settings, email, pending)
    await db.commit()
    if token is not None:
        queue: EmailQueue = request.app.state.email_queue
        await queue.send_auth_mail(kind="register", email=email, url=_register_url(settings, token))
    return Accepted()


@router.post("/register/verify", response_model=MeOut)
async def register_verify(
    body: RegisterVerify, request: Request, response: Response, db: SessionDep, settings: SettingsDep
) -> MeOut:
    await _throttle(db, request, "regv", None, per_email=0, per_ip=VERIFY_PER_IP)
    claimed = (
        await db.execute(
            update(AuthToken)
            .where(
                AuthToken.token_hash == hash_token(body.token),
                AuthToken.purpose == PURPOSE_REGISTER,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > func.now(),
            )
            .values(used_at=func.now())
            .returning(AuthToken.email, AuthToken.password_hash)  # atomic single use
        )
    ).one_or_none()
    if claimed is None:
        await db.commit()  # keeps the throttle count
        raise Problem.unauthorized(ProblemCode.AUTH_TOKEN_INVALID, "Link is invalid, used or expired")
    email, password_hash = claimed
    assert password_hash is not None  # CHECK register_carries_hash  # noqa: S101
    user = await new_verified_user(db, email=email)
    if user is None:
        await db.commit()  # the token is spent; nothing is attached to the existing account
        raise Problem(
            409,
            ProblemCode.ACCOUNT_EXISTS,
            "An account for this address already exists; sign in or reset the password",
        )
    db.add(UserCredential(user_id=user.id, password_hash=password_hash))
    token = await create_session(
        db, user.id, user_agent=request.headers.get("user-agent"), ip=_ip(request), settings=settings
    )
    await ensure_credit_account(db, user.id, verified=True, signup_credits=settings.free_signup_credits)
    set_session_cookie(response, token, settings)
    log.info("sign_in", method="password_register", user_id=user.id)
    return _me(user)
