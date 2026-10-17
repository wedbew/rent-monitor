"""Media manifest repository: tenant-scoped reads, owner-verified atomic replace (RM-376, G-01a).

A foreign or unknown audit is `AuditNotFoundError` (the route maps it to 404, never 403). Expiry is derived
on read: a stored item past `expires_at` is reported `expired`, so old reports stay readable with an explicit
"media unavailable" state instead of a missing row.

LEGAL[images]: persists identity and digest of listing photos and floor plans (RM-376)
GDPR[retention]: rows are removed with the audit or the account (cascade) (RM-376)
"""

from datetime import UTC, datetime
from uuid import UUID

from rm_contracts.media import (
    AnalysisState,
    MediaItem,
    MediaKind,
    MediaManifest,
    MediaMime,
    MediaSource,
    MediaState,
    check_cardinality,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.media_models import MediaEvidence
from rm_core.db.models import Audit
from rm_core.principal import Principal


class AuditNotFoundError(Exception):
    """The audit does not exist or belongs to someone else (indistinguishable on purpose)."""


async def _owned(db: AsyncSession, audit_id: UUID, user_id: str) -> bool:
    found = await db.scalar(select(Audit.id).where(Audit.id == audit_id, Audit.user_id == user_id))
    return found is not None


def _item(row: MediaEvidence, now: datetime) -> MediaItem:
    state = MediaState(row.state)
    expired = state is MediaState.stored and row.expires_at is not None and row.expires_at <= now
    return MediaItem(
        media_id=row.media_id,
        ordinal=row.ordinal,
        kind=MediaKind(row.kind),
        source_type=MediaSource(row.source_type),
        state=MediaState.expired if expired else state,
        analysis_state=AnalysisState(row.analysis_state),
        content_digest=row.content_digest,
        width=row.width,
        height=row.height,
        mime=MediaMime(row.mime) if row.mime else None,
        failure_code=row.failure_code,
        expires_at=row.expires_at,
    )


async def persist_manifest(
    db: AsyncSession, *, user_id: str, audit_id: UUID, items: list[MediaItem]
) -> MediaManifest:
    """Replace the audit's manifest atomically. `user_id` must own the audit. Never commits (caller does)."""
    check_cardinality(items)
    if any(i.state is MediaState.expired for i in items):
        raise ValueError("expired is derived on read, not stored")
    if not await _owned(db, audit_id, user_id):
        raise AuditNotFoundError
    await db.execute(delete(MediaEvidence).where(MediaEvidence.audit_id == audit_id))
    db.add_all(
        MediaEvidence(
            media_id=i.media_id,
            audit_id=audit_id,
            user_id=user_id,
            ordinal=i.ordinal,
            kind=i.kind.value,
            source_type=i.source_type.value,
            state=i.state.value,
            analysis_state=i.analysis_state.value,
            content_digest=i.content_digest,
            width=i.width,
            height=i.height,
            mime=i.mime.value if i.mime else None,
            failure_code=i.failure_code,
            expires_at=i.expires_at,
        )
        for i in items
    )
    await db.flush()
    return await _read(db, audit_id, user_id)


async def _read(db: AsyncSession, audit_id: UUID, user_id: str) -> MediaManifest:
    if not await _owned(db, audit_id, user_id):
        raise AuditNotFoundError
    rows = (
        await db.scalars(
            select(MediaEvidence).where(MediaEvidence.audit_id == audit_id).order_by(MediaEvidence.ordinal)
        )
    ).all()
    now = datetime.now(UTC)
    return MediaManifest(
        audit_id=audit_id,
        items=[_item(r, now) for r in rows],
        created_at=min((r.created_at for r in rows), default=None),
    )


async def get_manifest(db: AsyncSession, audit_id: UUID, principal: Principal) -> MediaManifest:
    """The caller's manifest (empty when the audit has no media). Foreign audit: `AuditNotFoundError`."""
    return await _read(db, audit_id, principal.user_id)
