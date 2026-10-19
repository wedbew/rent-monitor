"""Mapping of Otodom catalogue places to GUS BDL territories (expand-only, RM-282)

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-20 03:00:00.000000

One derived row per catalogue place: the gmina, powiat and voivodeship it maps to (or why it does not), the
relation (the whole gmina or a place inside it) and the candidates when a name fits several. Recomputable from the
catalogue and the territorial reference, so it can be replaced wholesale; it never feeds a financial number.
LEGAL[third-party-data]: relates public Otodom place paths to public GUS administrative units (RM-282).
GDPR[retention]: public territorial identifiers, no personal data; removed with its catalogue version.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_location_territory",
        sa.Column("catalogue_version", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.String(64), nullable=False),
        sa.Column("reference_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("relation", sa.String(14), nullable=True),
        sa.Column("gmina_id", sa.String(32), nullable=True),
        sa.Column("powiat_id", sa.String(32), nullable=True),
        sa.Column("wojewodztwo_id", sa.String(32), nullable=True),
        sa.Column(
            "candidates",
            postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("mapped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("catalogue_version", "location_id"),
        sa.ForeignKeyConstraint(
            ["catalogue_version", "location_id"],
            ["app.market_location.catalogue_version", "app.market_location.location_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("status IN ('mapped','ambiguous','unmatched')", name="status_vocab"),
        sa.CheckConstraint("relation IS NULL OR relation IN ('gmina','within_gmina')", name="relation_vocab"),
        sa.CheckConstraint(
            "status <> 'mapped' OR (gmina_id IS NOT NULL AND relation IS NOT NULL)", name="mapped_is_complete"
        ),
        schema="app",
    )
    op.create_index(
        "ix_market_location_territory_gmina",
        "market_location_territory",
        ["gmina_id"],
        schema="app",
        postgresql_where=sa.text("gmina_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_market_location_territory_gmina", table_name="market_location_territory", schema="app")
    op.drop_table("market_location_territory", schema="app")
