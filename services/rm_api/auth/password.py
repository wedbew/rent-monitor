"""Email and password registration and login (ADR 0013, docs/PASSWORD-AUTH-SPEC.md sections 1 to 5):
`register`, `register/verify`, `register/resend` (RM-203), `login` (RM-204), `password/forgot`,
`password/reset` and `password/change` (RM-205).

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
from rm_contracts.auth import (
    Accepted,
    ChangePasswordRequest,
    ForgotRequest,
    LoginRequest,
    MeOut,
    RegisterRequest,
    RegisterVerify,
    ResendRequest,
    ResetRequest,
)
from rm_contracts.problems import ProblemCode
from rm_core.db.models import AuthToken, User, UserCredential
from rm_core.ledger import ensure_credit_account
from rm_core.ratelimit import hit
from rm_core.settings import Settings
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_api.auth.accounts import new_verified_user
from rm_api.auth.passwords import PasswordHasher, check_policy
from rm_api.auth.router import HOUR_S, _ip, _me  # pyright: ignore[reportPrivateUsage]
from rm_api.auth.sessions import (
    clear_session_cookie,
    create_session,
    hash_token,
    revoke_all_sessions,
    set_session_cookie,
)
from rm_api.deps import PrincipalDep, SessionDep, SettingsDep
from rm_api.problems import Problem
from rm_api.queue import EmailQueue

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

PURPOSE_REGISTER = "register"
PURPOSE_RESET = "reset"
CHANGE_PER_USER = 10  # per 15 minutes
CHANGE_PER_IP = 50
FORGOT_PER_EMAIL = 5  # per hour
FORGOT_PER_IP = 20
RESET_PER_IP = 30
LOGIN_WINDOW_S = 900
LOGIN_PER_EMAIL = 10  # per 15 minutes (spec section 5)
LOGIN_PER_IP = 50
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
    db: AsyncSession,
    request: Request,
    scope: str,
    email: str | None,
    *,
    per_email: int,
    per_ip: int,
    window_s: int = HOUR_S,
) -> None:
    checks = [(f"{scope}:ip", _ip(request), per_ip)]
    if email is not None:
        checks.append((f"{scope}:email", email, per_email))
    for key, subject, limit in checks:
        decision = await hit(db, key, subject, limit=limit, window_s=window_s)
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


async def _send(queue: EmailQueue, *, kind: str, email: str, url: str | None) -> None:
    """Queue a mail without letting a queue outage change the answer: a 500 only for addresses that have
    something to send would reveal which addresses those are. The token is stored; one can ask again."""
    try:
        await queue.send_auth_mail(kind=kind, email=email, url=url)
    except Exception:
        log.exception("auth_mail_defer_failed", kind=kind)


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
        await _send(queue, kind="account_exists", email=email, url=None)
    else:
        token = await _issue_register_token(db, settings, email, password_hash)
        await db.commit()  # the token must exist before the mail can be opened
        await _send(queue, kind="register", email=email, url=_register_url(settings, token))
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
        await _send(queue, kind="register", email=email, url=_register_url(settings, token))
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


def _invalid_credentials() -> Problem:
    return Problem.unauthorized(ProblemCode.INVALID_CREDENTIALS, "Invalid email or password")


@router.post("/login", response_model=MeOut)
async def login(
    body: LoginRequest, request: Request, response: Response, db: SessionDep, settings: SettingsDep
) -> MeOut:
    """One generic failure for every cause (wrong password, unknown address, an account with no password), and
    a real hash check even for an unknown address, so neither the body nor the response time says which. A
    throttle is not a lockout: past the limit the answer is 429, and the right password works again once the
    window has passed."""
    email = body.email.strip().lower()
    await _throttle(
        db, request, "login", email, per_email=LOGIN_PER_EMAIL, per_ip=LOGIN_PER_IP, window_s=LOGIN_WINDOW_S
    )
    await db.commit()  # keep the attempt count whatever follows
    hasher = _hasher(request)
    found = (
        await db.execute(
            select(User, UserCredential.password_hash)
            .join(UserCredential, UserCredential.user_id == User.id)
            .where(User.email == email)
        )
    ).one_or_none()
    if found is None:
        await hasher.verify_dummy(body.password)
        raise _invalid_credentials()
    user, stored = found
    matches, replacement = await hasher.verify(body.password, stored)
    if not matches:
        raise _invalid_credentials()
    if replacement is not None:  # parameters were raised since this hash was made: store the stronger one
        await db.execute(
            update(UserCredential)
            .where(UserCredential.user_id == user.id, UserCredential.password_hash == stored)
            .values(password_hash=replacement, updated_at=func.now())
        )
    token = await create_session(
        db, user.id, user_agent=request.headers.get("user-agent"), ip=_ip(request), settings=settings
    )
    await ensure_credit_account(db, user.id, verified=True, signup_credits=settings.free_signup_credits)
    set_session_cookie(response, token, settings)
    log.info("sign_in", method="password", user_id=user.id)
    return _me(user)


# ------------------------------------------------------------------------------------------ recovery (RM-205)
async def _issue_reset_token(db: AsyncSession, settings: Settings, user_id: str, email: str) -> str:
    """One live reset token per address: the newest replaces the rest (serialised per address)."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"auth_token:{email}"})
    await db.execute(
        update(AuthToken)
        .where(AuthToken.email == email, AuthToken.purpose == PURPOSE_RESET, AuthToken.used_at.is_(None))
        .values(used_at=func.now())
    )
    token = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            token_hash=hash_token(token),
            purpose=PURPOSE_RESET,
            email=email,
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.reset_token_ttl_minutes),
        )
    )
    return token


@router.post("/password/forgot", status_code=202, response_model=Accepted)
async def password_forgot(
    body: ForgotRequest, request: Request, db: SessionDep, settings: SettingsDep
) -> Accepted:
    """Always 202. A reset link is mailed only when the address has an account, and nothing in the answer says
    whether it does. The link goes to the configured app origin, never to a host taken from the request."""
    email = body.email.strip().lower()
    await _throttle(db, request, "forgot", email, per_email=FORGOT_PER_EMAIL, per_ip=FORGOT_PER_IP)
    user_id = await db.scalar(select(User.id).where(User.email == email))
    token = None
    if user_id is not None:
        token = await _issue_reset_token(db, settings, user_id, email)
    await db.commit()
    if token is not None:
        url = f"{settings.public_origin}/password/reset#t={token}"
        await _send(request.app.state.email_queue, kind="reset", email=email, url=url)
    log.info("password_reset_requested")
    return Accepted()


@router.post("/password/reset", status_code=204)
async def password_reset(
    body: ResetRequest, request: Request, db: SessionDep, settings: SettingsDep
) -> Response:
    """Set the password (the first one, for an account made by Google or a magic link) and sign everyone out.
    Nobody is signed in by this: the person logs in again with the new password."""
    await _throttle(db, request, "resetp", None, per_email=0, per_ip=RESET_PER_IP)
    token_hash = hash_token(body.token)
    live = (
        await db.execute(
            select(AuthToken.email, AuthToken.user_id).where(
                AuthToken.token_hash == token_hash,
                AuthToken.purpose == PURPOSE_RESET,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > func.now(),
            )
        )
    ).one_or_none()
    if live is None or live.user_id is None:
        await db.commit()  # keeps the throttle count
        raise Problem.unauthorized(ProblemCode.AUTH_TOKEN_INVALID, "Link is invalid, used or expired")
    reason = check_policy(body.password, live.email)
    if reason is not None:  # a weak password does not spend the link
        await db.commit()
        raise Problem(422, ProblemCode.WEAK_PASSWORD, "Password does not meet the policy", reason=reason)
    new_hash = await _hasher(request).hash(body.password)
    claimed = await db.scalar(  # atomic single use: of several concurrent callers exactly one gets the row
        update(AuthToken)
        .where(
            AuthToken.token_hash == token_hash,
            AuthToken.purpose == PURPOSE_RESET,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > func.now(),
        )
        .values(used_at=func.now())
        .returning(AuthToken.user_id)
    )
    if claimed is None:
        await db.commit()
        raise Problem.unauthorized(ProblemCode.AUTH_TOKEN_INVALID, "Link is invalid, used or expired")
    await db.execute(
        insert(UserCredential)
        .values(user_id=claimed, password_hash=new_hash)
        .on_conflict_do_update(
            index_elements=[UserCredential.user_id],
            set_={"password_hash": new_hash, "updated_at": func.now()},
        )
    )
    await revoke_all_sessions(db, claimed)  # every browser, cached principals included
    log.info("password_reset", user_id=claimed)
    return Response(status_code=204)


@router.post("/password/change", status_code=204)
async def password_change(
    body: ChangePasswordRequest,
    request: Request,
    db: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
) -> Response:
    """Needs the current password. Signs out every session including this one: the person logs in again."""
    await _throttle(
        db,
        request,
        "change",
        principal.user_id,
        per_email=CHANGE_PER_USER,
        per_ip=CHANGE_PER_IP,
        window_s=LOGIN_WINDOW_S,
    )
    hasher = _hasher(request)
    stored = await db.scalar(
        select(UserCredential.password_hash).where(UserCredential.user_id == principal.user_id)
    )
    if stored is None:  # Google or magic-link account: recover (set a password) instead
        await hasher.verify_dummy(body.current_password)
        await db.commit()
        raise _invalid_credentials()
    matches, _ = await hasher.verify(body.current_password, stored)
    if not matches:
        await db.commit()
        raise _invalid_credentials()
    reason = check_policy(body.new_password, principal.email)
    if reason is not None:
        await db.commit()
        raise Problem(422, ProblemCode.WEAK_PASSWORD, "Password does not meet the policy", reason=reason)
    new_hash = await hasher.hash(body.new_password)
    await db.execute(
        update(UserCredential)
        .where(UserCredential.user_id == principal.user_id)
        .values(password_hash=new_hash, updated_at=func.now())
    )
    await revoke_all_sessions(db, principal.user_id)
    out = Response(status_code=204)
    clear_session_cookie(out, settings)
    log.info("password_changed", user_id=principal.user_id)
    return out
