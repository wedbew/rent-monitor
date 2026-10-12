"""Sessions: a random 32-byte cookie token, only its SHA-256 in Postgres (blueprint §2 Auth decision, rules
1-4).

GDPR[personal-data]: session rows hold ip and user agent; retention is `expires_at` plus the purge job
(RM-30).
"""

import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Response
from rm_core.db.models import User, UserSession
from rm_core.principal import Principal
from rm_core.settings import Settings
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

PRINCIPAL_CACHE_TTL_S = 30.0  # the stated bound on how long a revoked session can still be accepted
PRINCIPAL_CACHE_MAX = 10_000
EXTEND_AFTER = timedelta(days=1)  # slide the expiry at most once a day
REVOKED_CHANNEL = "session_revoked"
MAX_UA = 300


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.app_env
        != "development",  # `__Host-` in production needs Secure; local http is development
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.cookie_name,
        path="/",
        secure=settings.app_env != "development",
        httponly=True,
        samesite="lax",
    )


async def create_session(
    session: AsyncSession, user_id: str, *, user_agent: str | None, ip: str | None, settings: Settings
) -> str:
    """Insert a session row and return the raw token (shown to the browser once, never stored)."""
    token = new_token()
    session.add(
        UserSession(
            token_hash=hash_token(token),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.session_ttl_days),
            user_agent=(user_agent or "")[:MAX_UA] or None,
            ip=(ip or "")[:45] or None,
        )
    )
    await session.flush()
    return token


@dataclass
class _Entry:
    principal: Principal
    expires: float


class PrincipalCache:
    """In-process cache of resolved principals; evicted at once by NOTIFY, otherwise after `ttl` seconds."""

    def __init__(
        self,
        ttl: float = PRINCIPAL_CACHE_TTL_S,
        maxsize: int = PRINCIPAL_CACHE_MAX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl
        self._max = maxsize
        self._clock = clock
        self._items: dict[str, _Entry] = {}

    def get(self, token_hash: str) -> Principal | None:
        entry = self._items.get(token_hash)
        if entry is None:
            return None
        if entry.expires <= self._clock():
            del self._items[token_hash]
            return None
        return entry.principal

    def put(self, principal: Principal) -> None:
        if len(self._items) >= self._max:
            self._items.pop(next(iter(self._items)))  # oldest insertion first
        self._items[principal.token_hash] = _Entry(principal, self._clock() + self._ttl)

    def evict_user(self, user_id: str) -> None:
        for key in [k for k, e in self._items.items() if e.principal.user_id == user_id]:
            del self._items[key]

    def evict_token(self, token_hash: str) -> None:
        self._items.pop(token_hash, None)

    def clear(self) -> None:
        self._items.clear()

    def on_notify(self, payload: str) -> None:
        """Payloads are `user:<id>` or `token:<sha256>` (see `revoke_*`)."""
        kind, _, value = payload.partition(":")
        if kind == "user":
            self.evict_user(value)
        elif kind == "token":
            self.evict_token(value)

    def __len__(self) -> int:
        return len(self._items)


async def resolve_principal(
    session: AsyncSession, token: str, cache: PrincipalCache, settings: Settings
) -> Principal | None:
    """Cookie value to principal: the cache first, then Postgres (unexpired session joined to its user)."""
    token_hash = hash_token(token)
    cached = cache.get(token_hash)
    if cached is not None:
        return cached
    row = (
        await session.execute(
            select(
                UserSession.id,
                UserSession.last_seen_at,
                User.id,
                User.email,
                User.role,
                User.email_verified_at,
            )
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.token_hash == token_hash, UserSession.expires_at > func.now())
        )
    ).one_or_none()
    if row is None:
        return None
    session_id, last_seen, user_id, email, role, verified_at = row
    if last_seen < datetime.now(UTC) - EXTEND_AFTER:
        await session.execute(
            update(UserSession)
            .where(UserSession.id == session_id)
            .values(
                last_seen_at=func.now(), expires_at=func.now() + timedelta(days=settings.session_ttl_days)
            )
        )
    principal = Principal(
        user_id=user_id,
        email=email,
        role=role,
        email_verified=verified_at is not None,
        session_id=session_id,
        token_hash=token_hash,
    )
    cache.put(principal)
    return principal


async def _notify(session: AsyncSession, payload: str) -> None:
    await session.execute(select(func.pg_notify(REVOKED_CHANNEL, payload)))


async def revoke_session(session: AsyncSession, principal: Principal) -> None:
    """Sign out this browser. NOTIFY is delivered when the transaction commits."""
    await session.execute(delete(UserSession).where(UserSession.token_hash == principal.token_hash))
    await _notify(session, f"token:{principal.token_hash}")


async def revoke_all_sessions(session: AsyncSession, user_id: str) -> int:
    """Sign out everywhere; every API process drops the user's cached principals within the NOTIFY latency."""
    result = await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
    await _notify(session, f"user:{user_id}")
    return int(getattr(result, "rowcount", 0) or 0)
