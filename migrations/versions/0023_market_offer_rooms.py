"""Rooms of a stored rental offer that was stored without them, beside the immutable offer (expand-only, RM-439)

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-20 16:00:00.000000

The importer stored no rooms for offers read before 2026-10-20 because the site sends the count as a word ("TWO");
`market_offer` is immutable, so the count is attached here by the same sweep that attaches districts and read as
`COALESCE(market_offer.rooms, market_offer_rooms.rooms)`. One row per offer, insert-once.
LEGAL[scraping]: from Otodom search results (RM-439).
LEGAL[third-party-data]: a room count of an advert; no seller data (RM-439).
GDPR[personal-data]: none. Removed with the offer (cascade).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_offer_rooms",
        sa.Column("source", sa.String(16), server_default="otodom", nullable=False),
        sa.Column("source_offer_id", sa.Numeric(20, 0), nullable=False),
        sa.Column("rooms", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source", "source_offer_id"],
            ["app.market_offer.source", "app.market_offer.source_offer_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source", "source_offer_id"),
        sa.CheckConstraint("rooms >= 1 AND rooms <= 50", name=op.f("ck_market_offer_rooms_rooms_range")),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("market_offer_rooms", schema="app")
