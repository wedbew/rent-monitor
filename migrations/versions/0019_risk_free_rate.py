"""Risk-free rate store and the audit's record of the rate used (expand-only, RM-210)

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-19 13:00:00.000000

One row per macro series holds the latest accepted observation (ECB IRS, Poland 10Y). Nullable provenance
columns on `audit` record the rate the engine used, its source and its observed month; NULL for audits made
before RM-210 and for audits that used the RISK_FREE_RATE setting only in old code paths.
LEGAL[third-party-data]: ECB statistic, source cited in the stored `source` column (RM-210).
GDPR[retention]: public macro statistic; no personal data. The audit columns are deleted with their audit row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_free_rate",
        sa.Column("series_key", sa.String(64), primary_key=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("observation_period", sa.Date(), nullable=True, comment="first day of the observed month"),
        sa.Column("rate", sa.Numeric(8, 6), nullable=True, comment="annual yield as a fraction"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failure_code", sa.String(40), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("rate IS NULL OR (rate >= 0.001 AND rate <= 0.20)", name="rate_plausible"),
        sa.CheckConstraint(
            "(rate IS NULL) = (observation_period IS NULL) AND (rate IS NULL) = (fetched_at IS NULL)",
            name="value_complete",
        ),
        sa.CheckConstraint("(last_failure_code IS NULL) = (last_failed_at IS NULL)", name="failure_complete"),
        schema="app",
    )
    op.add_column("audit", sa.Column("risk_free_rate", sa.Numeric(8, 6), nullable=True), schema="app")
    op.add_column(
        "audit",
        sa.Column(
            "risk_free_source",
            sa.Text(),
            nullable=True,
            comment="ecb:<series> or setting:RISK_FREE_RATE",
        ),
        schema="app",
    )
    op.add_column(
        "audit",
        sa.Column("risk_free_as_of", sa.Date(), nullable=True, comment="first day of the observed month"),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("audit", "risk_free_as_of", schema="app")
    op.drop_column("audit", "risk_free_source", schema="app")
    op.drop_column("audit", "risk_free_rate", schema="app")
    op.drop_table("risk_free_rate", schema="app")
