"""billing_event for durable Paddle webhook receipt, and the lot -> purchase foreign key (expand-only)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-14 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("notification_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("purchase_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','processed','ignored','review','failed')", name=op.f("ck_billing_event_status_vocab")
        ),
        sa.CheckConstraint("environment IN ('sandbox','live')", name=op.f("ck_billing_event_environment_vocab")),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["app.billing_purchase.id"],
            name=op.f("fk_billing_event_purchase_id_billing_purchase"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_event")),
        sa.UniqueConstraint("environment", "event_id", name="uq_billing_event_env_event"),
        schema="app",
    )
    op.create_index(
        "ix_billing_event_pending",
        "billing_event",
        ["lease_until"],
        unique=False,
        schema="app",
        postgresql_where=sa.text("status = 'pending'"),
    )
    # NOT VALID: enforced for every new or changed row; no existing row has a purchase link, and validating in the
    # same transaction would block reads (squawk). A later contract migration may VALIDATE it on its own.
    op.create_foreign_key(
        op.f("fk_report_credit_lot_purchase_id_billing_purchase"),
        "report_credit_lot",
        "billing_purchase",
        ["purchase_id"],
        ["id"],
        source_schema="app",
        referent_schema="app",
        postgresql_not_valid=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_report_credit_lot_purchase_id_billing_purchase"), "report_credit_lot", schema="app", type_="foreignkey"
    )
    op.drop_index("ix_billing_event_pending", table_name="billing_event", schema="app")
    op.drop_table("billing_event", schema="app")
