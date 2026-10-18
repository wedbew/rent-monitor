"""Otodom rental corpus: catalogue, offers, import runs, checkpoints (expand-only, RM-385)

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-18 12:00:00.000000

LEGAL[scraping]: stores the results of fetching Otodom search pages; this migration fetches nothing (RM-385)
LEGAL[third-party-data]: asking rent, area and rooms of third-party adverts, never re-published (RM-385)
GDPR[personal-data]: whitelisted analytical fields only, no seller data; retention is the 90-day archive rule
(derived from expires_at); erasure is not per person because no personal data is held (RM-385)
Invariant 2: market_offer.price_basis is CHECKed to 'asking'.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE = ("market_catalogue", "market_location", "market_offer")


def upgrade() -> None:
    op.create_table(
        "market_catalogue",
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("source_ref", sa.String(length=300), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_market_catalogue_version_positive")),
        sa.CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name=op.f("ck_market_catalogue_checksum_hex")),
        sa.PrimaryKeyConstraint("version", name=op.f("pk_market_catalogue")),
        schema="app",
    )
    op.create_table(
        "market_location",
        sa.Column("catalogue_version", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("otodom_path", sa.String(length=160), nullable=False),
        sa.Column("launch_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalogue_version"],
            ["app.market_catalogue.version"],
            name=op.f("fk_market_location_catalogue_version_market_catalogue"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("catalogue_version", "location_id", name=op.f("pk_market_location")),
        sa.UniqueConstraint("catalogue_version", "otodom_path", name="uq_market_location_version_path"),
        sa.UniqueConstraint("catalogue_version", "position", name="uq_market_location_version_position"),
        schema="app",
    )
    op.create_index("ix_market_location_location", "market_location", ["location_id"], schema="app")
    op.create_table(
        "market_import_run",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("location_id", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=10), server_default="planned", nullable=False),
        sa.Column("pages_expected", sa.Integer(), nullable=True),
        sa.Column("pages_fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("observed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("inserted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicates", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("location_conflicts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "mode IN ('bootstrap','incremental','recovery')", name=op.f("ck_market_import_run_mode_vocab")
        ),
        sa.CheckConstraint(
            "state IN ('planned','running','published','incomplete','failed')",
            name=op.f("ck_market_import_run_state_vocab"),
        ),
        sa.CheckConstraint("window_end >= window_start", name=op.f("ck_market_import_run_window_ordered")),
        sa.CheckConstraint(
            "pages_fetched >= 0 AND pages_fetched <= 10000"
            " AND (pages_expected IS NULL OR (pages_expected >= 0 AND pages_expected <= 10000))",
            name=op.f("ck_market_import_run_pages_range"),
        ),
        sa.CheckConstraint(
            "observed >= 0 AND inserted >= 0 AND duplicates >= 0 AND location_conflicts >= 0",
            name=op.f("ck_market_import_run_counts_nonneg"),
        ),
        sa.CheckConstraint(
            "state <> 'published' OR (NOT truncated AND pages_expected IS NOT NULL"
            " AND pages_fetched = pages_expected)",
            name=op.f("ck_market_import_run_published_has_coverage"),
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_market_import_run")),
        schema="app",
    )
    op.create_index(
        "ix_market_import_run_location_state", "market_import_run", ["location_id", "state"], schema="app"
    )
    op.create_table(
        "market_import_checkpoint",
        sa.Column("location_id", sa.String(length=64), nullable=False),
        sa.Column("dataset", sa.String(length=32), nullable=False),
        sa.Column("bootstrap_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("covered_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unresolved_gap_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_published_run_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("location_id", "dataset", name=op.f("pk_market_import_checkpoint")),
        schema="app",
    )
    op.create_table(
        "market_offer",
        sa.Column("source", sa.String(length=16), server_default="otodom", nullable=False),
        sa.Column("source_offer_id", sa.Numeric(precision=20, scale=0), nullable=False),
        sa.Column("price_basis", sa.String(length=8), server_default="asking", nullable=False),
        sa.Column("location_id", sa.String(length=64), nullable=False),
        sa.Column("asking_rent_pln", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("area_m2", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("rooms", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("age_basis", sa.String(length=12), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_date_issue", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.CheckConstraint("source = 'otodom'", name=op.f("ck_market_offer_source_vocab")),
        sa.CheckConstraint("price_basis = 'asking'", name=op.f("ck_market_offer_asking_only")),
        sa.CheckConstraint(
            "age_basis IN ('publication','first_seen')", name=op.f("ck_market_offer_age_basis_vocab")
        ),
        sa.CheckConstraint(
            "asking_rent_pln IS NULL OR asking_rent_pln > 0", name=op.f("ck_market_offer_rent_positive")
        ),
        sa.CheckConstraint("area_m2 IS NULL OR area_m2 > 0", name=op.f("ck_market_offer_area_positive")),
        sa.CheckConstraint(
            "rooms IS NULL OR (rooms >= 1 AND rooms <= 50)", name=op.f("ck_market_offer_rooms_range")
        ),
        sa.CheckConstraint(
            "(age_basis = 'publication' AND published_at IS NOT NULL"
            " AND expires_at = published_at + interval '2160 hours')"
            " OR (age_basis = 'first_seen' AND expires_at = first_seen_at + interval '2160 hours')",
            name=op.f("ck_market_offer_expiry_matches_anchor"),
        ),
        sa.PrimaryKeyConstraint("source", "source_offer_id", name=op.f("pk_market_offer")),
        schema="app",
    )
    # New, empty tables: plain indexes take no lock that matters.
    op.create_index(
        "ix_market_offer_location_expires", "market_offer", ["location_id", "expires_at"], schema="app"
    )
    # Content is immutable at the database level (catalogue versions, their locations, offers).
    op.execute(
        "CREATE FUNCTION app.market_refuse_update() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation'; "
        "END $$"
    )
    for table in _IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE ON app.{table} "
            "FOR EACH ROW EXECUTE FUNCTION app.market_refuse_update()"
        )


def downgrade() -> None:
    for table in _IMMUTABLE:
        op.execute(f"DROP TRIGGER {table}_immutable ON app.{table}")
    op.execute("DROP FUNCTION app.market_refuse_update()")
    op.drop_index("ix_market_offer_location_expires", table_name="market_offer", schema="app")
    op.drop_table("market_offer", schema="app")
    op.drop_table("market_import_checkpoint", schema="app")
    op.drop_index("ix_market_import_run_location_state", table_name="market_import_run", schema="app")
    op.drop_table("market_import_run", schema="app")
    op.drop_index("ix_market_location_location", table_name="market_location", schema="app")
    op.drop_table("market_location", schema="app")
    op.drop_table("market_catalogue", schema="app")
