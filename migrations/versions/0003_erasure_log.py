"""erasure_log: pseudonymous record of erased accounts (expand-only)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11 22:38:44.280854
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('erasure_log',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_hash', sa.String(length=64), nullable=False),
    sa.Column('erased_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_length(user_hash) = 64', name=op.f('ck_erasure_log_hash_length')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_erasure_log')),
    sa.UniqueConstraint('user_hash', name=op.f('uq_erasure_log_user_hash')),
    schema='app'
    )
    op.create_index(op.f('ix_app_erasure_log_erased_at'), 'erasure_log', ['erased_at'], unique=False, schema='app')


def downgrade() -> None:
    op.drop_index(op.f('ix_app_erasure_log_erased_at'), table_name='erasure_log', schema='app')
    op.drop_table('erasure_log', schema='app')
