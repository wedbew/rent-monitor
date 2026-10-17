"""`media_evidence`: one row per photo or floor plan of an audit (RM-376, G-01a).

No Alembic migration yet: the coordinator owns the migration slot and moves this class into `models.py`
(handoff RM-376). Until then it lives on its own metadata and the table exists only where a test creates it.

LEGAL[images]: metadata and digest of listing photos and plans (RM-376)
GDPR[retention]: deleted with the audit (ON DELETE CASCADE) and with the account via `user_id`; no binary
bytes are stored here. Binary retention is an open owner decision (RM-376).
GDPR[erasure]: cascade on `audit` and `app_user` (RM-376)
"""

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from rm_core.db.base import NAMING, SCHEMA


class PendingBase(DeclarativeBase):
    """A separate metadata on purpose: the table has no migration, and the migration drift test compares
    `Base.metadata` with the migrated database. The coordinator re-bases the class on `Base` with the
    migration (handoff RM-376), which deletes this base and the two stubs below."""

    metadata = MetaData(naming_convention=NAMING, schema=SCHEMA)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


# Stubs so the foreign keys resolve inside this metadata. Never created: tests create `media_evidence` only.
Table("audit", PendingBase.metadata, Column[UUID]("id", Uuid, primary_key=True))
Table("app_user", PendingBase.metadata, Column[str]("id", Text, primary_key=True))


class MediaEvidence(PendingBase):
    __tablename__ = "media_evidence"
    __table_args__ = (
        UniqueConstraint("audit_id", "ordinal", name="uq_media_evidence_audit_ordinal"),
        Index("ix_media_evidence_user", "user_id"),
        CheckConstraint("kind IN ('photo','plan')", name="kind_vocab"),
        CheckConstraint("source_type IN ('url','manual','upload')", name="source_vocab"),
        CheckConstraint("state IN ('pending','stored','rejected','failed')", name="state_vocab"),
        CheckConstraint("analysis_state IN ('not_requested','classified','failed')", name="analysis_vocab"),
        CheckConstraint("mime IS NULL OR mime IN ('image/jpeg','image/png','image/webp')", name="mime_vocab"),
        CheckConstraint("content_digest IS NULL OR content_digest ~ '^[0-9a-f]{64}$'", name="digest_hex"),
        CheckConstraint("ordinal >= 0 AND ordinal < 27", name="ordinal_range"),
        CheckConstraint("(width IS NULL) = (height IS NULL)", name="dimensions_together"),
        CheckConstraint(
            "state <> 'stored' OR (content_digest IS NOT NULL AND mime IS NOT NULL)", name="stored_complete"
        ),
        CheckConstraint(
            "state NOT IN ('rejected','failed') OR failure_code IS NOT NULL", name="failure_explained"
        ),
    )

    media_id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    audit_id: Mapped[UUID] = mapped_column(ForeignKey("audit.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("app_user.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str] = mapped_column(String(8))
    source_type: Mapped[str] = mapped_column(String(8))
    state: Mapped[str] = mapped_column(String(8), default="pending", server_default="pending")
    analysis_state: Mapped[str] = mapped_column(
        String(14), default="not_requested", server_default="not_requested"
    )
    content_digest: Mapped[str | None] = mapped_column(String(64))
    width: Mapped[int | None]
    height: Mapped[int | None]
    mime: Mapped[str | None] = mapped_column(String(16))
    failure_code: Mapped[str | None] = mapped_column(String(40))
    expires_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
