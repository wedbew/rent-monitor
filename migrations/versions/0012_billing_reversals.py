"""Provider reversals: credit reasons, account billing hold, lot reversal markers, billing_adjustment (expand-only)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-14 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New enum values cannot be used in the transaction that adds them, hence the autocommit block; nothing here
    # uses them. A removed value cannot be dropped again, so the downgrade leaves them (harmless).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE app.credit_reason ADD VALUE IF NOT EXISTS 'refund_revoke' AFTER 'release'")
        op.execute("ALTER TYPE app.credit_reason ADD VALUE IF NOT EXISTS 'refund_restore' AFTER 'refund_revoke'")
    op.add_column("credit_account", sa.Column("billing_hold", sa.String(length=40), nullable=True), schema="app")
    op.add_column(
        "report_credit_lot",
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True, comment="set while a refund or chargeback stands"),
        schema="app",
    )
    op.add_column(
        "report_credit_lot",
        sa.Column("reversal_epoch", sa.Integer(), server_default="0", nullable=False),
        schema="app",
    )
    op.create_table(
        "billing_adjustment",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("adjustment_id", sa.String(length=64), nullable=False),
        sa.Column("purchase_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("total_minor", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["purchase_id"], ["app.billing_purchase.id"], name=op.f("fk_billing_adjustment_purchase_id_billing_purchase")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_adjustment")),
        sa.UniqueConstraint("environment", "adjustment_id", name="uq_billing_adjustment_env_id"),
        schema="app",
    )
    op.create_index("ix_billing_adjustment_purchase", "billing_adjustment", ["purchase_id"], unique=False, schema="app")


def downgrade() -> None:
    op.drop_index("ix_billing_adjustment_purchase", table_name="billing_adjustment", schema="app")
    op.drop_table("billing_adjustment", schema="app")
    op.drop_column("report_credit_lot", "reversal_epoch", schema="app")
    op.drop_column("report_credit_lot", "reversed_at", schema="app")
    op.drop_column("credit_account", "billing_hold", schema="app")
