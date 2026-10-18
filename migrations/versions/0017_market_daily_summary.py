"""Daily asking-rent summaries per location: additions and 90-day cohort (expand-only, RM-395)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-19 09:00:00.000000

LEGAL[third-party-data]: aggregates of Otodom asking rents; this migration fetches nothing (RM-395)
LEGAL[republication]: aggregates only, no listing content (RM-395)
GDPR[personal-data]: counts and quantiles, no personal data; retention: daily history kept (RM-395)
Invariant 2: price_basis is CHECKed to 'asking'; there is no deed variant.
Rows are immutable: reuses app.market_refuse_update() from migration 0015.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_daily_summary",
        sa.Column("location_id", sa.String(length=64), nullable=False),
        sa.Column("dataset", sa.String(length=32), nullable=False),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("series", sa.String(length=10), nullable=False),
        sa.Column("cohort_key", sa.String(length=16), nullable=False),
        sa.Column("calc_version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), server_default="otodom", nullable=False),
        sa.Column("price_basis", sa.String(length=8), server_default="asking", nullable=False),
        sa.Column("archive_days", sa.Integer(), server_default=sa.text("90"), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_count", sa.Integer(), nullable=False),
        sa.Column("priced_count", sa.Integer(), nullable=False),
        sa.Column("first_observed_count", sa.Integer(), nullable=True),
        sa.Column("median_rent_pln", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("median_ppm2", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("p25_ppm2", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("p75_ppm2", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("sufficient", sa.Boolean(), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("backfilled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gap_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("series IN ('additions','cohort')", name=op.f("ck_market_daily_summary_series_vocab")),
        sa.CheckConstraint("source = 'otodom'", name=op.f("ck_market_daily_summary_source_vocab")),
        sa.CheckConstraint("price_basis = 'asking'", name=op.f("ck_market_daily_summary_asking_only")),
        sa.CheckConstraint("archive_days = 90", name=op.f("ck_market_daily_summary_archive_policy")),
        sa.CheckConstraint("calc_version >= 1", name=op.f("ck_market_daily_summary_calc_version_positive")),
        sa.CheckConstraint(
            "cohort_key ~ '^[a-z0-9_]{1,16}$'", name=op.f("ck_market_daily_summary_cohort_key_shape")
        ),
        sa.CheckConstraint(
            "observed_count >= 0 AND priced_count >= 0 AND priced_count <= observed_count"
            " AND (first_observed_count IS NULL OR first_observed_count >= 0)",
            name=op.f("ck_market_daily_summary_counts_consistent"),
        ),
        sa.CheckConstraint(
            "series = 'additions' OR first_observed_count IS NULL",
            name=op.f("ck_market_daily_summary_first_observed_additions"),
        ),
        sa.CheckConstraint(
            "sufficient = (priced_count >= 10)", name=op.f("ck_market_daily_summary_sufficient_matches_sample")
        ),
        sa.CheckConstraint(
            "(priced_count = 0) = (median_ppm2 IS NULL AND median_rent_pln IS NULL"
            " AND p25_ppm2 IS NULL AND p75_ppm2 IS NULL)",
            name=op.f("ck_market_daily_summary_stats_iff_priced"),
        ),
        sa.CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_market_daily_summary_digest_hex")),
        sa.PrimaryKeyConstraint(
            "location_id",
            "dataset",
            "summary_date",
            "series",
            "cohort_key",
            "calc_version",
            name=op.f("pk_market_daily_summary"),
        ),
        schema="app",
    )
    op.execute(
        "CREATE TRIGGER market_daily_summary_immutable BEFORE UPDATE ON app.market_daily_summary "
        "FOR EACH ROW EXECUTE FUNCTION app.market_refuse_update()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER market_daily_summary_immutable ON app.market_daily_summary")
    op.drop_table("market_daily_summary", schema="app")
