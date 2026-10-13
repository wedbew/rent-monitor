"""rent_comparable: asking rents owned by an otodom_rental sidecar (expand-only)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-13 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # LEGAL[third-party-data]: rents derived from Otodom rental listings; no seller data stored (RM-106)
    op.create_table(
        "rent_comparable",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("sidecar_id", sa.BigInteger(), nullable=False),
        sa.Column("monthly_rent_pln", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("area_m2", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.CheckConstraint("area_m2 > 0", name=op.f("ck_rent_comparable_area_positive")),
        sa.CheckConstraint("monthly_rent_pln > 0", name=op.f("ck_rent_comparable_rent_positive")),
        sa.ForeignKeyConstraint(
            ["sidecar_id"],
            ["app.market_sidecar.id"],
            name=op.f("fk_rent_comparable_sidecar_id_market_sidecar"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rent_comparable")),
        schema="app",
    )
    op.create_index(
        "ix_rent_comparable_sidecar", "rent_comparable", ["sidecar_id"], unique=False, schema="app"
    )


def downgrade() -> None:
    op.drop_index("ix_rent_comparable_sidecar", table_name="rent_comparable", schema="app")
    op.drop_table("rent_comparable", schema="app")
