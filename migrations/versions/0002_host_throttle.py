"""host_throttle: per-host request slots and circuit breaker (expand-only)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 22:23:09.504694
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('host_throttle',
    sa.Column('host', sa.String(length=64), nullable=False),
    sa.Column('next_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('breaker_open_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('breaker_reason', sa.String(length=40), nullable=True),
    sa.PrimaryKeyConstraint('host', name=op.f('pk_host_throttle')),
    schema='app'
    )


def downgrade() -> None:
    op.drop_table('host_throttle', schema='app')
