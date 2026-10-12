"""geo_cache: cached geocoding and points of interest (expand-only)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12 09:58:36.163289
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('geo_cache',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("kind IN ('geocode','poi')", name=op.f('ck_geo_cache_kind_vocab')),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_geo_cache')),
    schema='app'
    )
    op.create_index(op.f('ix_app_geo_cache_expires_at'), 'geo_cache', ['expires_at'], unique=False, schema='app')


def downgrade() -> None:
    op.drop_index(op.f('ix_app_geo_cache_expires_at'), table_name='geo_cache', schema='app')
    op.drop_table('geo_cache', schema='app')
