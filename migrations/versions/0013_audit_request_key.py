"""Audit request key: `Idempotency-Key` of the creating POST, unique per user (expand-only, RM-304)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-15 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit",
        sa.Column(
            "request_key",
            sa.Uuid(),
            nullable=True,
            comment="client Idempotency-Key of the POST that created it; random, not personal data",
        ),
        schema="app",
    )
    # Built concurrently (no write lock on `audit` while it builds), so outside the migration's transaction.
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_audit_user_request_key",
            "audit",
            ["user_id", "request_key"],
            unique=True,
            schema="app",
            postgresql_where=sa.text("request_key IS NOT NULL"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "uq_audit_user_request_key",
            table_name="audit",
            schema="app",
            postgresql_concurrently=True,
            if_exists=True,
        )
    op.drop_column("audit", "request_key", schema="app")
