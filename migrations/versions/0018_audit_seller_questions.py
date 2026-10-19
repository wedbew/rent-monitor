"""Audit seller questions: a nullable versioned JSONB block beside `result` (expand-only, RM-404)

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-19 12:00:00.000000

Nullable and unconstrained by design: audits made before RM-404 keep NULL and show no questions. The block is
derived by `deal_analyzer.seller_questions` from the stored result and written once, in the same transaction that
ends the audit; a repeated write is refused by the `status = 'running'` guard, so no row is ever duplicated.
LEGAL[republication]: the block echoes listing facts and equipment named from listing photos (RM-404).
GDPR[retention]: deleted with its audit row (30-day audit retention, account erasure cascade) (RM-404).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit",
        sa.Column(
            "seller_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="versioned seller-question block derived from result (RM-404); NULL = none stored",
        ),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("audit", "seller_questions", schema="app")
