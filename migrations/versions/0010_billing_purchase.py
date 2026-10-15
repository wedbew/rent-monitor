"""billing_pack and billing_purchase for the Paddle report-pack pilot (expand-only, docs/PADDLE-INTEGRATION.md s.4)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-14 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_pack",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("reports", sa.Integer(), nullable=False),
        sa.Column("price_id", sa.String(length=64), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False, comment="approved gross price in grosze"),
        sa.Column("currency", sa.String(length=3), server_default="PLN", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("code IN ('reports_1','reports_5','reports_10')", name=op.f("ck_billing_pack_code_vocab")),
        sa.CheckConstraint(
            "reports = CASE code WHEN 'reports_1' THEN 1 WHEN 'reports_5' THEN 5 ELSE 10 END",
            name=op.f("ck_billing_pack_reports_match_code"),
        ),
        sa.CheckConstraint("amount_minor > 0 AND currency = 'PLN'", name=op.f("ck_billing_pack_price_positive_pln")),
        sa.CheckConstraint("environment IN ('sandbox','live')", name=op.f("ck_billing_pack_environment_vocab")),
        sa.PrimaryKeyConstraint("code", "catalog_version", "environment", name=op.f("pk_billing_pack")),
        sa.UniqueConstraint("environment", "price_id", name="uq_billing_pack_env_price"),
        schema="app",
    )
    op.create_index(
        "uq_billing_pack_active",
        "billing_pack",
        ["code", "environment"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("active"),
    )
    # GDPR[personal-data]: user_id (SET NULL on erasure), owner_ref (hash) and the provider customer id (RM-217)
    op.create_table(
        "billing_purchase",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True, comment="GDPR[personal-data]"),
        sa.Column("owner_ref", sa.String(length=64), nullable=False, comment="GDPR[personal-data]: sha256 of the user id"),
        sa.Column("request_key", sa.Uuid(), nullable=False),
        sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("pack_code", sa.String(length=16), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("reports", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="PLN", nullable=False),
        sa.Column("price_id", sa.String(length=64), nullable=False),
        sa.Column("binding_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="intent", nullable=False),
        sa.Column("provider_txn_id", sa.String(length=64), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.String(length=64), nullable=True, comment="GDPR[personal-data]"),
        sa.Column("provider_status", sa.String(length=32), nullable=True),
        sa.Column("grant_ledger_id", sa.BigInteger(), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('intent','creating','created','creation_unknown','failed','paid','granted','review',"
            "'refunded')",
            name=op.f("ck_billing_purchase_state_vocab"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app.app_user.id"], name=op.f("fk_billing_purchase_user_id_app_user"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["grant_ledger_id"], ["app.credit_ledger.id"], name=op.f("fk_billing_purchase_grant_ledger_id_credit_ledger")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_purchase")),
        sa.UniqueConstraint("grant_ledger_id", name=op.f("uq_billing_purchase_grant_ledger_id")),
        sa.UniqueConstraint("user_id", "request_key", name="uq_purchase_user_request"),
        sa.UniqueConstraint("environment", "provider_txn_id", name="uq_purchase_env_txn"),
        schema="app",
    )
    op.create_index(
        "ix_purchase_user_created",
        "billing_purchase",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
        schema="app",
    )
    op.create_index("ix_purchase_pending", "billing_purchase", ["state", "lease_until"], unique=False, schema="app")


def downgrade() -> None:
    op.drop_index("ix_purchase_pending", table_name="billing_purchase", schema="app")
    op.drop_index("ix_purchase_user_created", table_name="billing_purchase", schema="app")
    op.drop_table("billing_purchase", schema="app")
    op.drop_index("uq_billing_pack_active", table_name="billing_pack", schema="app")
    op.drop_table("billing_pack", schema="app")
