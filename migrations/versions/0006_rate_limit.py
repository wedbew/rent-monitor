"""rate_limit: atomic fixed-window counters for abuse limits (expand-only)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-12 21:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # GDPR[personal-data]: `key` is a SHA-256 of the limited subject (email or IP); purged one day after the window (RM-12)
    op.create_table('rate_limit',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('n', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint('n >= 0', name=op.f('ck_rate_limit_n_non_negative')),
    sa.PrimaryKeyConstraint('key', 'window_start', name=op.f('pk_rate_limit')),
    schema='app'
    )
    op.create_index(op.f('ix_app_rate_limit_window_start'), 'rate_limit', ['window_start'], unique=False, schema='app')


def downgrade() -> None:
    op.drop_index(op.f('ix_app_rate_limit_window_start'), table_name='rate_limit', schema='app')
    op.drop_table('rate_limit', schema='app')
