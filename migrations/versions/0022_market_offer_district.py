"""District of a stored rental offer, beside the immutable offer (expand-only, RM-439)

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-20 15:00:00.000000

`market_offer` rows are immutable (a trigger refuses UPDATE), so the district an advert is listed in lives in
two new tables: `market_district` (the district identities the site named under a place, with the first time
each was seen) and `market_offer_district` (one row per offer that carried a district). Both fill from search
tiles; an offer without a district simply has no row, which is how "no district at the source" is told from
"district known but too few offers".
LEGAL[scraping]: district ids and names come from Otodom search results (RM-439).
LEGAL[third-party-data]: place names and counts only; no seller data (RM-439).
GDPR[personal-data]: none; public place identifiers and an advert id. Removed with the place's offers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_district",
        sa.Column("location_id", sa.String(64), nullable=False),
        sa.Column("district_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("location_id", "district_id"),
        schema="app",
    )
    op.create_table(
        "market_offer_district",
        sa.Column("source", sa.String(16), server_default="otodom", nullable=False),
        sa.Column("source_offer_id", sa.Numeric(20, 0), nullable=False),
        sa.Column("location_id", sa.String(64), nullable=False),
        sa.Column("district_id", sa.String(200), nullable=False),
        sa.ForeignKeyConstraint(
            ["source", "source_offer_id"],
            ["app.market_offer.source", "app.market_offer.source_offer_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "district_id"],
            ["app.market_district.location_id", "app.market_district.district_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source", "source_offer_id"),
        schema="app",
    )
    op.create_index(
        "ix_market_offer_district_place",
        "market_offer_district",
        ["location_id", "district_id"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index("ix_market_offer_district_place", table_name="market_offer_district", schema="app")
    op.drop_table("market_offer_district", schema="app")
    op.drop_table("market_district", schema="app")
