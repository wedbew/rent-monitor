"""Interior architect: generation operations (expand-only, RM-450)

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-21 20:00:00.000000

A new table only, so the migration is expand-only. One active operation per project is enforced by a partial
unique index; a repeated `Idempotency-Key` per project by a unique constraint. `request_sent_at` records that
the provider may have been called, which decides whether crash recovery releases or keeps the reservation.
LEGAL[images]: room and reference images are sent to an image model.
GDPR[processor]: OpenRouter and its model provider.
GDPR[erasure]: cascade on project and app_user.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interior_generation",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(10), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("estimate_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("cost_estimated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("references_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("references_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_media_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.Column("request_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app.app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["app.interior_project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["app.interior_revision.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["output_media_id"], ["app.interior_media.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_interior_generation_idempotency"),
        sa.CheckConstraint(
            "state IN ('queued','running','succeeded','failed','cancelled')",
            name=op.f("ck_interior_generation_state_vocab"),
        ),
        sa.CheckConstraint("estimate_usd > 0", name=op.f("ck_interior_generation_estimate_positive")),
        sa.CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0", name=op.f("ck_interior_generation_cost_non_negative")
        ),
        schema="app",
    )
    op.create_index(
        "uq_interior_generation_one_active",
        "interior_generation",
        ["project_id"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("state IN ('queued','running')"),
    )
    op.create_index(
        "ix_interior_generation_project", "interior_generation", ["project_id", "created_at"], schema="app"
    )


def downgrade() -> None:
    op.drop_table("interior_generation", schema="app")
