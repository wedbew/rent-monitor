"""Find or create users and their login identities, race-free (blueprint §2, rules 6; §3 models).

GDPR[personal-data]: creates `app_user` (email, name, avatar_url) and `auth_identity` (Google sub or email)
rows.
Retention: until account deletion (cascade, `rm_core.privacy.delete_account`). Erasure path: RUNBOOK-GDPR.

Linking happens only on a *verified* email: callers guarantee it (Google `email_verified`, or a used magic
link), so a
Google identity can never claim an address it does not own. Identity keys are `(provider, subject)`; Google
users are
keyed by `sub`, never by email.
"""

from rm_core.db.models import AuthIdentity, User
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

MAX_AVATAR_URL = 500


class EmailConfirmationRequired(Exception):
    """Google cannot vouch for this address (not @gmail.com, no matching `hd`): confirm it with a magic link
    first."""


def safe_avatar(url: str | None) -> str | None:
    """Only keep an https picture URL; anything else (data:, javascript:, http:) is dropped."""
    if url and url.startswith("https://") and len(url) <= MAX_AVATAR_URL and " " not in url:
        return url
    return None


async def _upsert_verified_user(
    session: AsyncSession, *, email: str, name: str | None, avatar: str | None
) -> User:
    """One atomic statement: two concurrent first sign-ins for one address meet on the unique email."""
    stmt = insert(User).values(email=email, name=name, avatar_url=avatar, email_verified_at=func.now())
    stmt = stmt.on_conflict_do_update(
        index_elements=[User.email],
        set_={
            "email_verified_at": func.coalesce(User.email_verified_at, func.now()),
            "name": func.coalesce(User.name, stmt.excluded.name),
            "avatar_url": func.coalesce(User.avatar_url, stmt.excluded.avatar_url),
        },
    ).returning(User.id)
    user_id = (await session.execute(stmt)).scalar_one()
    return await session.get_one(User, user_id, populate_existing=True)


async def _link_identity(session: AsyncSession, user_id: str, provider: str, subject: str) -> str:
    """Attach `(provider, subject)` to a user; if it already belongs to someone, that user wins (identity is
    truth)."""
    inserted = await session.scalar(
        insert(AuthIdentity)
        .values(user_id=user_id, provider=provider, subject=subject)
        .on_conflict_do_nothing(index_elements=[AuthIdentity.provider, AuthIdentity.subject])
        .returning(AuthIdentity.id)
    )
    if inserted is not None:
        return user_id
    owner = await session.scalar(
        select(AuthIdentity.user_id).where(AuthIdentity.provider == provider, AuthIdentity.subject == subject)
    )
    return owner if owner is not None else user_id


async def user_for_google(
    session: AsyncSession,
    *,
    sub: str,
    email: str,
    name: str | None,
    picture: str | None,
    authoritative: bool,
) -> User:
    """Returning Google user by `sub`; otherwise join an existing user with the same verified email, or
    create one.

    The join or creation happens only when Google is authoritative for the address (D-13, ADR 0010). A
    returning `sub`
    is always let in: identity is the `sub`, never the address.
    """
    owner = await session.scalar(
        select(AuthIdentity.user_id).where(AuthIdentity.provider == "google", AuthIdentity.subject == sub)
    )
    if owner is not None:
        return await session.get_one(User, owner)
    if not authoritative:
        raise EmailConfirmationRequired
    user = await _upsert_verified_user(session, email=email, name=name, avatar=safe_avatar(picture))
    owner = await _link_identity(session, user.id, "google", sub)
    return user if owner == user.id else await session.get_one(User, owner)


async def user_for_email(session: AsyncSession, *, email: str) -> User:
    """A used magic link proves the address: create or reuse the user and make sure the email identity
    exists."""
    user = await _upsert_verified_user(session, email=email, name=None, avatar=None)
    await _link_identity(session, user.id, "email", email)
    return user
