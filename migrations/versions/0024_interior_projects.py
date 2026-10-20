"""Interior architect: projects, media, the person's own items, revisions, tombstones (expand-only, RM-448)

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-21 12:00:00.000000

New tables only, so the migration is expand-only. Image bytes are not here: `interior_media` holds identity,
digest and the object key in the private media store (ADR 0014); `interior_media_tombstone` queues objects whose
owning row was removed, so retention and erasure delete bytes with retries.
LEGAL[images]: owns the person's room photo and item photos (RM-448).
GDPR[personal-data]: names, notes, links are free text written by the person (RM-448).
GDPR[retention]: projects expire 30 days after creation; pending and failed uploads are swept after 7 days.
GDPR[erasure]: every table cascades on app_user; object keys are queued before the account row is deleted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "interior_project",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("room_type", sa.String(16), nullable=False),
        sa.Column("style", sa.String(80), nullable=True),
        sa.Column("budget_pln", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "keep",
            postgresql.JSONB(),
            server_default=sa.text("'{\"items\": []}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app.app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name=op.f("ck_interior_project_name_length")),
        sa.CheckConstraint(
            "room_type IN ('living_room','bedroom','kitchen','bathroom','hallway','office','other')",
            name=op.f("ck_interior_project_room_type_vocab"),
        ),
        sa.CheckConstraint(
            "budget_pln IS NULL OR budget_pln >= 0", name=op.f("ck_interior_project_budget_non_negative")
        ),
        schema="app",
    )
    op.create_index("ix_interior_project_user", "interior_project", ["user_id", "created_at"], schema="app")
    op.create_index("ix_interior_project_expires", "interior_project", ["expires_at"], schema="app")

    op.create_table(
        "interior_media",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(12), nullable=False),
        sa.Column("state", sa.String(8), server_default="pending", nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=True),
        sa.Column("mime", sa.String(32), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app.app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["app.interior_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name=op.f("uq_interior_media_object_key")),
        sa.CheckConstraint(
            "purpose IN ('source','custom_item','render')", name=op.f("ck_interior_media_purpose_vocab")
        ),
        sa.CheckConstraint(
            "state IN ('pending','stored','failed')", name=op.f("ck_interior_media_state_vocab")
        ),
        sa.CheckConstraint(
            "content_digest IS NULL OR content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_interior_media_digest_hex"),
        ),
        sa.CheckConstraint(
            "state <> 'stored' OR (content_digest IS NOT NULL AND width IS NOT NULL AND height IS NOT NULL)",
            name=op.f("ck_interior_media_stored_complete"),
        ),
        sa.CheckConstraint(
            "(width IS NULL) = (height IS NULL)", name=op.f("ck_interior_media_dimensions_together")
        ),
        schema="app",
    )
    op.create_index("ix_interior_media_project", "interior_media", ["project_id"], schema="app")
    op.create_index("ix_interior_media_expires", "interior_media", ["expires_at"], schema="app")

    op.create_table(
        "interior_custom_item",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("price_pln", sa.Numeric(12, 2), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("photo_media_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app.app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["app.interior_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["photo_media_id"], ["app.interior_media.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(name) BETWEEN 1 AND 120", name=op.f("ck_interior_custom_item_name_length")
        ),
        sa.CheckConstraint("quantity BETWEEN 1 AND 99", name=op.f("ck_interior_custom_item_quantity_range")),
        sa.CheckConstraint(
            "price_pln IS NULL OR price_pln >= 0", name=op.f("ck_interior_custom_item_price_non_negative")
        ),
        sa.CheckConstraint(
            "url IS NULL OR (length(url) <= 2048 AND url ~* '^https?://')",
            name=op.f("ck_interior_custom_item_url_shape"),
        ),
        schema="app",
    )
    op.create_index(
        "ix_interior_custom_item_project", "interior_custom_item", ["project_id", "created_at"], schema="app"
    )

    op.create_table(
        "interior_revision",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app.app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["app.interior_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "number", name="uq_interior_revision_project_number"),
        sa.CheckConstraint("number >= 1", name=op.f("ck_interior_revision_number_positive")),
        sa.CheckConstraint(
            "source_digest IS NULL OR source_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_interior_revision_digest_hex"),
        ),
        schema="app",
    )

    op.create_table(
        "interior_media_tombstone",
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("object_key"),
        schema="app",
    )
    op.create_index(
        "ix_interior_media_tombstone_created", "interior_media_tombstone", ["created_at"], schema="app"
    )


def downgrade() -> None:
    for table in (
        "interior_media_tombstone",
        "interior_revision",
        "interior_custom_item",
        "interior_media",
        "interior_project",
    ):
        op.drop_table(table, schema="app")
