"""ai_budget, ai_reservation, ai_usage: monthly AI spend control (expand-only)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12 10:35:43.860446
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ai_budget',
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('cap_usd', sa.Numeric(precision=14, scale=6), nullable=False),
    sa.Column('reserved_usd', sa.Numeric(precision=14, scale=6), server_default='0', nullable=False),
    sa.Column('spent_usd', sa.Numeric(precision=14, scale=6), server_default='0', nullable=False),
    sa.Column('warned_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('cap_usd >= 0 AND reserved_usd >= 0 AND spent_usd >= 0', name=op.f('ck_ai_budget_non_negative')),
    sa.PrimaryKeyConstraint('month', name=op.f('pk_ai_budget')),
    schema='app'
    )
    op.create_table('ai_reservation',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('amount_usd', sa.Numeric(precision=14, scale=6), nullable=False),
    sa.Column('state', sa.String(length=10), server_default='reserved', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("state IN ('reserved','settled','released','swept')", name=op.f('ck_ai_reservation_state_vocab')),
    sa.CheckConstraint('amount_usd >= 0', name=op.f('ck_ai_reservation_amount_non_negative')),
    sa.ForeignKeyConstraint(['month'], ['app.ai_budget.month'], name=op.f('fk_ai_reservation_month_ai_budget')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_reservation')),
    schema='app'
    )
    op.create_index('ix_ai_reservation_open', 'ai_reservation', ['created_at'], unique=False, schema='app', postgresql_where=sa.text("state = 'reserved'"))
    op.create_table('ai_usage',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('audit_id', sa.Uuid(), nullable=True),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('prompt_tokens', sa.Integer(), server_default='0', nullable=False),
    sa.Column('completion_tokens', sa.Integer(), server_default='0', nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=14, scale=6), nullable=False),
    sa.Column('cost_estimated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_usage')),
    schema='app'
    )
    op.create_index(op.f('ix_app_ai_usage_audit_id'), 'ai_usage', ['audit_id'], unique=False, schema='app')
    op.create_index(op.f('ix_app_ai_usage_month'), 'ai_usage', ['month'], unique=False, schema='app')


def downgrade() -> None:
    op.drop_index(op.f('ix_app_ai_usage_month'), table_name='ai_usage', schema='app')
    op.drop_index(op.f('ix_app_ai_usage_audit_id'), table_name='ai_usage', schema='app')
    op.drop_table('ai_usage', schema='app')
    op.drop_index('ix_ai_reservation_open', table_name='ai_reservation', schema='app', postgresql_where=sa.text("state = 'reserved'"))
    op.drop_table('ai_reservation', schema='app')
    op.drop_table('ai_budget', schema='app')
