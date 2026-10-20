"""Grant or revoke an explicit account entitlement (RM-438). Idempotent; never creates or alters an account.

The account is resolved by its stored (lower-cased) e-mail address once, by staff, at grant time; from then
on the entitlement belongs to the user id, so a changed address or a similar account gets nothing.

GDPR[personal-data]: reads the account's e-mail to resolve the user id; the row stores only the id.
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import AccountEntitlement, User
from rm_core.entitlements import UNLIMITED_REPORTS

Outcome = Literal["granted", "already_granted", "restored", "revoked", "already_revoked", "no_such_account"]


@dataclass(frozen=True)
class GrantResult:
    outcome: Outcome
    user_id: str | None


async def _user_id(session: AsyncSession, email: str) -> str | None:
    return await session.scalar(select(User.id).where(User.email == email.strip().lower()))


async def grant(
    session: AsyncSession, email: str, *, kind: str = UNLIMITED_REPORTS, note: str
) -> GrantResult:
    """Make the entitlement active for the existing account. A second call changes nothing."""
    user_id = await _user_id(session, email)
    if user_id is None:
        return GrantResult("no_such_account", None)
    existing = await session.get(AccountEntitlement, (user_id, kind), with_for_update=True)
    if existing is None:
        await session.execute(
            insert(AccountEntitlement)
            .values(user_id=user_id, kind=kind, note=note)
            .on_conflict_do_nothing(index_elements=["user_id", "kind"])
        )
        outcome: Outcome = "granted"
    elif existing.revoked_at is not None:
        existing.revoked_at = None
        existing.note = note
        existing.granted_at = func.now()
        outcome = "restored"
    else:
        outcome = "already_granted"
    await session.commit()
    return GrantResult(outcome, user_id)


async def revoke(session: AsyncSession, email: str, *, kind: str = UNLIMITED_REPORTS) -> GrantResult:
    user_id = await _user_id(session, email)
    if user_id is None:
        return GrantResult("no_such_account", None)
    row = await session.get(AccountEntitlement, (user_id, kind), with_for_update=True)
    if row is None or row.revoked_at is not None:
        await session.commit()
        return GrantResult("already_revoked", user_id)
    row.revoked_at = func.now()
    await session.commit()
    return GrantResult("revoked", user_id)
