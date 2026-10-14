"""report_credit_lot and report_credit_allocation: provenance of credits (expand-only, docs/PADDLE-INTEGRATION.md s.4)

Existing balances become explicit `migration` lots (no fabricated purchase provenance): granted = balance now
+ units reserved by in-flight audits + units consumed by captured audits + units an operator removed. In-flight
credit reservations get allocations on that lot so a later release returns the units to it.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-14 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COST = "CASE WHEN a.analyst THEN 2 ELSE 1 END"  # ledger.FEATURE_COST: deal_audit 1, deal_audit_analyst 2


def upgrade() -> None:
    op.create_table(
        "report_credit_lot",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("grant_key", sa.String(length=120), nullable=False, comment="the grant's ledger idempotency key"),
        sa.Column("purchase_id", sa.Uuid(), nullable=True),
        sa.Column("granted", sa.Integer(), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revoked", sa.Integer(), server_default="0", nullable=False),
        sa.Column("frozen", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("granted > 0", name=op.f("ck_report_credit_lot_granted_positive")),
        sa.CheckConstraint(
            "available >= 0 AND reserved >= 0 AND consumed >= 0 AND revoked >= 0",
            name=op.f("ck_report_credit_lot_counters_non_negative"),
        ),
        sa.CheckConstraint(
            "granted = available + reserved + consumed + revoked", name=op.f("ck_report_credit_lot_counters_add_up")
        ),
        sa.CheckConstraint(
            "source IN ('signup','admin','purchase','migration')", name=op.f("ck_report_credit_lot_source_vocab")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.app_user.id"],
            name=op.f("fk_report_credit_lot_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_credit_lot")),
        sa.UniqueConstraint("grant_key", name=op.f("uq_report_credit_lot_grant_key")),
        sa.UniqueConstraint("purchase_id", name=op.f("uq_report_credit_lot_purchase_id")),
        schema="app",
    )
    op.create_index(
        "ix_lot_spend_order",
        "report_credit_lot",
        ["user_id", "created_at", "id"],
        unique=False,
        schema="app",
        postgresql_where=sa.text("available > 0"),
    )
    op.create_table(
        "report_credit_allocation",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.BigInteger(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.CheckConstraint("units > 0", name=op.f("ck_report_credit_allocation_units_positive")),
        sa.CheckConstraint(
            "state IN ('reserved','captured','released','revoked')",
            name=op.f("ck_report_credit_allocation_state_vocab"),
        ),
        sa.ForeignKeyConstraint(
            ["audit_id"],
            ["app.audit.id"],
            name=op.f("fk_report_credit_allocation_audit_id_audit"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["app.report_credit_lot.id"],
            name=op.f("fk_report_credit_allocation_lot_id_report_credit_lot"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_credit_allocation")),
        sa.UniqueConstraint("audit_id", "lot_id", name="uq_allocation_audit_lot"),
        schema="app",
    )
    op.create_index(
        "ix_allocation_lot_state", "report_credit_allocation", ["lot_id", "state"], unique=False, schema="app"
    )

    # Backfill: one migration lot per account that ever held units (the ledger sum equals the cached balance).
    op.execute(
        f"""
        INSERT INTO app.report_credit_lot
            (user_id, source, grant_key, granted, available, reserved, consumed, revoked)
        SELECT c.user_id, 'migration', 'migration:' || c.user_id,
               c.balance + COALESCE(r.units, 0) + COALESCE(k.units, 0) + COALESCE(v.units, 0),
               c.balance, COALESCE(r.units, 0), COALESCE(k.units, 0), COALESCE(v.units, 0)
        FROM app.credit_account c
        LEFT JOIN (SELECT a.user_id, SUM({COST}) AS units FROM app.audit a
                   WHERE a.charge_source = 'credit' AND a.charge_state = 'reserved' GROUP BY a.user_id) r
               ON r.user_id = c.user_id
        LEFT JOIN (SELECT a.user_id, SUM({COST}) AS units FROM app.audit a
                   WHERE a.charge_source = 'credit' AND a.charge_state = 'captured' GROUP BY a.user_id) k
               ON k.user_id = c.user_id
        LEFT JOIN (SELECT l.user_id, -SUM(l.delta) AS units FROM app.credit_ledger l
                   WHERE l.reason = 'admin_adjust' AND l.delta < 0 GROUP BY l.user_id) v
               ON v.user_id = c.user_id
        WHERE c.balance + COALESCE(r.units, 0) + COALESCE(k.units, 0) + COALESCE(v.units, 0) > 0
        """
    )
    op.execute(
        f"""
        INSERT INTO app.report_credit_allocation (audit_id, lot_id, units, state)
        SELECT a.id, l.id, {COST}, 'reserved'
        FROM app.audit a
        JOIN app.report_credit_lot l ON l.grant_key = 'migration:' || a.user_id
        WHERE a.charge_source = 'credit' AND a.charge_state = 'reserved'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_allocation_lot_state", table_name="report_credit_allocation", schema="app")
    op.drop_table("report_credit_allocation", schema="app")
    op.drop_index("ix_lot_spend_order", table_name="report_credit_lot", schema="app")
    op.drop_table("report_credit_lot", schema="app")
