"""`media_evidence`: photo and floor-plan manifest rows per audit (expand-only, RM-376)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-18 10:00:00.000000

LEGAL[images]: metadata and SHA-256 digest of listing photos and plans; no binary bytes (RM-376)
GDPR[retention]: removed with the audit or the account (ON DELETE CASCADE); binary retention is undecided
GDPR[erasure]: cascade on `audit` and `app_user`
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_evidence",
        sa.Column("media_id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("source_type", sa.String(length=8), nullable=False),
        sa.Column("state", sa.String(length=8), server_default="pending", nullable=False),
        sa.Column("analysis_state", sa.String(length=14), server_default="not_requested", nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("mime", sa.String(length=16), nullable=True),
        sa.Column("failure_code", sa.String(length=40), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('photo','plan')", name=op.f("ck_media_evidence_kind_vocab")),
        sa.CheckConstraint("source_type IN ('url','manual','upload')", name=op.f("ck_media_evidence_source_vocab")),
        sa.CheckConstraint(
            "state IN ('pending','stored','rejected','failed')", name=op.f("ck_media_evidence_state_vocab")
        ),
        sa.CheckConstraint(
            "analysis_state IN ('not_requested','classified','failed')",
            name=op.f("ck_media_evidence_analysis_vocab"),
        ),
        sa.CheckConstraint(
            "mime IS NULL OR mime IN ('image/jpeg','image/png','image/webp')",
            name=op.f("ck_media_evidence_mime_vocab"),
        ),
        sa.CheckConstraint(
            "content_digest IS NULL OR content_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_media_evidence_digest_hex")
        ),
        sa.CheckConstraint("ordinal >= 0 AND ordinal < 27", name=op.f("ck_media_evidence_ordinal_range")),
        sa.CheckConstraint("(width IS NULL) = (height IS NULL)", name=op.f("ck_media_evidence_dimensions_together")),
        sa.CheckConstraint(
            "state <> 'stored' OR (content_digest IS NOT NULL AND mime IS NOT NULL)",
            name=op.f("ck_media_evidence_stored_complete"),
        ),
        sa.CheckConstraint(
            "state NOT IN ('rejected','failed') OR failure_code IS NOT NULL",
            name=op.f("ck_media_evidence_failure_explained"),
        ),
        sa.ForeignKeyConstraint(
            ["audit_id"], ["app.audit.id"], name=op.f("fk_media_evidence_audit_id_audit"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app.app_user.id"], name=op.f("fk_media_evidence_user_id_app_user"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("media_id", name=op.f("pk_media_evidence")),
        sa.UniqueConstraint("audit_id", "ordinal", name="uq_media_evidence_audit_ordinal"),
        schema="app",
    )
    # A new, empty table: a plain index takes no lock that matters.
    op.create_index("ix_media_evidence_user", "media_evidence", ["user_id"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_media_evidence_user", table_name="media_evidence", schema="app")
    op.drop_table("media_evidence", schema="app")
