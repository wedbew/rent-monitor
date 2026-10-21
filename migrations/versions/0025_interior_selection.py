"""Interior architect: the product variants a person picked, with their observed offers (expand-only, RM-449)

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-21 18:00:00.000000

A new table only, so the migration is expand-only. The offer is stored as the snapshot that was observed
(provider, ids, price, delivery, stock, observed and expiry times, photo rights), never as an estimate.
LEGAL[third-party-data]: merchant data for the person's own project.
LEGAL[republication]: shown only to the project's owner.
GDPR[retention]: removed with the project at its 30-day expiry (cascade).
GDPR[erasure]: cascade on project and app_user.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interior_selection",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("variant_id", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("offer", postgresql.JSONB(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("gone_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app.app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["app.interior_project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "provider", "product_id", "variant_id", name="uq_interior_selection_variant"
        ),
        sa.CheckConstraint("quantity BETWEEN 1 AND 99", name=op.f("ck_interior_selection_quantity_range")),
        schema="app",
    )
    op.create_index(
        "ix_interior_selection_project", "interior_selection", ["project_id", "created_at"], schema="app"
    )


def downgrade() -> None:
    op.drop_table("interior_selection", schema="app")
