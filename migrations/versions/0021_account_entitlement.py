"""Explicit per-account entitlements (expand-only, RM-438)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-20 12:00:00.000000

One row per (account, kind). `unlimited_reports` is the designated test account's entitlement: analyses are not
charged against credit and the whole Rynek catalogue opens. Granted by staff through
`scripts/grant_entitlement.py`, never derived from an email address. A new table only, so it is expand-only.
GDPR[personal-data]: keyed by the user id, staff note holds no personal data; erased with the account (FK cascade).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_entitlement",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app.app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "kind"),
        sa.CheckConstraint("kind IN ('unlimited_reports')", name=op.f("ck_account_entitlement_kind_known")),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("account_entitlement", schema="app")
