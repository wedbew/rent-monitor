"""BDL location context: reference, observations, ingestion cursor, publication, quota (expand-only, RM-391)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-19 12:00:00.000000

LEGAL[third-party-data]: stores GUS BDL statistics and administrative identifiers; this migration fetches
nothing and activates no metric (B-023 open) (RM-391)
LEGAL[scraping]: location_ingest_run and location_quota_stamp record progress and rate of BDL API requests (RM-391)
GDPR[retention]: no personal data in any table; observations are annual public statistics kept as history,
quota stamps are deleted by the quota gate once older than its longest window (RM-391)
Invariant 2: observations carry no price basis; they cannot be read as asking or deed prices.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE = (
    "location_reference",
    "location_territory",
    "location_observation",
    "location_publication",
)


def upgrade() -> None:
    op.create_table(
        "location_reference",
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("source_ref", sa.String(length=300), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_location_reference_version_positive")),
        sa.CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name=op.f("ck_location_reference_checksum_hex")),
        sa.PrimaryKeyConstraint("version", name=op.f("pk_location_reference")),
        schema="app",
    )
    op.create_table(
        "location_territory",
        sa.Column("reference_version", sa.Integer(), nullable=False),
        sa.Column("territory_id", sa.String(length=32), nullable=False),
        sa.Column("teryt", sa.String(length=7), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("level", sa.String(length=12), nullable=False),
        sa.Column("parent_id", sa.String(length=32), nullable=True),
        sa.Column("has_powiat_rights", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "level IN ('gmina','powiat','wojewodztwo','country')",
            name=op.f("ck_location_territory_level_vocab"),
        ),
        sa.CheckConstraint("teryt ~ '^[0-9]{0,7}$'", name=op.f("ck_location_territory_teryt_digits")),
        sa.CheckConstraint(
            "(parent_id IS NULL) = (level = 'country')", name=op.f("ck_location_territory_only_country_is_root")
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> territory_id", name=op.f("ck_location_territory_not_own_parent")
        ),
        sa.CheckConstraint(
            "NOT has_powiat_rights OR level = 'gmina'",
            name=op.f("ck_location_territory_powiat_rights_are_gmina"),
        ),
        sa.ForeignKeyConstraint(
            ["reference_version"],
            ["app.location_reference.version"],
            name=op.f("fk_location_territory_reference_version_location_reference"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reference_version", "parent_id"],
            ["app.location_territory.reference_version", "app.location_territory.territory_id"],
            name=op.f("fk_location_territory_reference_version_location_territory"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("reference_version", "territory_id", name=op.f("pk_location_territory")),
        schema="app",
    )
    op.create_index(
        "ix_location_territory_level", "location_territory", ["reference_version", "level"], schema="app"
    )
    op.create_index(
        "uq_location_territory_teryt",
        "location_territory",
        ["reference_version", "level", "teryt"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("teryt <> ''"),
    )
    op.create_table(
        "location_observation",
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("metric_version", sa.Integer(), nullable=False),
        sa.Column("territory_id", sa.String(length=32), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=17), nullable=False),
        sa.Column("value", sa.Numeric(precision=30, scale=10), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('measured','suppressed','missing','invalid_attribute','withheld')",
            name=op.f("ck_location_observation_status_vocab"),
        ),
        sa.CheckConstraint("metric_version >= 1", name=op.f("ck_location_observation_version_positive")),
        sa.CheckConstraint("year BETWEEN 1990 AND 2100", name=op.f("ck_location_observation_year_range")),
        sa.CheckConstraint(
            "source_digest ~ '^[0-9a-f]{64}$'", name=op.f("ck_location_observation_digest_hex")
        ),
        sa.CheckConstraint(
            "(status IN ('measured','withheld')) = (value IS NOT NULL)",
            name=op.f("ck_location_observation_value_matches_status"),
        ),
        sa.CheckConstraint(
            "status = 'measured' OR reason IS NOT NULL", name=op.f("ck_location_observation_gap_has_reason")
        ),
        sa.PrimaryKeyConstraint(
            "metric_key", "metric_version", "territory_id", "year", name=op.f("pk_location_observation")
        ),
        schema="app",
    )
    op.create_index(
        "ix_location_observation_metric_year",
        "location_observation",
        ["metric_key", "metric_version", "year"],
        schema="app",
    )
    op.create_table(
        "location_ingest_run",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("variable_id", sa.String(length=16), nullable=False),
        sa.Column("unit_level", sa.Integer(), nullable=False),
        sa.Column("years", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("reference_version", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("metric_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=10), server_default="planned", nullable=False),
        sa.Column("next_page", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("observed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("inserted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicates", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("conflicts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('planned','running','incomplete','complete','failed')",
            name=op.f("ck_location_ingest_run_state_vocab"),
        ),
        sa.CheckConstraint("unit_level BETWEEN 0 AND 7", name=op.f("ck_location_ingest_run_unit_level_range")),
        sa.CheckConstraint("next_page BETWEEN 0 AND 10000", name=op.f("ck_location_ingest_run_next_page_range")),
        sa.CheckConstraint(
            "observed >= 0 AND inserted >= 0 AND duplicates >= 0 AND conflicts >= 0",
            name=op.f("ck_location_ingest_run_counts_nonneg"),
        ),
        sa.CheckConstraint("cardinality(years) BETWEEN 1 AND 40", name=op.f("ck_location_ingest_run_years_count")),
        sa.CheckConstraint(
            "state NOT IN ('complete','failed') OR lease_owner IS NULL",
            name=op.f("ck_location_ingest_run_done_has_no_lease"),
        ),
        sa.ForeignKeyConstraint(
            ["reference_version"],
            ["app.location_reference.version"],
            name=op.f("fk_location_ingest_run_reference_version_location_reference"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_location_ingest_run")),
        schema="app",
    )
    op.create_index("ix_location_ingest_run_state", "location_ingest_run", ["state"], schema="app")
    op.create_table(
        "location_publication",
        sa.Column("release_id", sa.String(length=64), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("metric_version", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("reference_version", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("expected", sa.Integer(), nullable=False),
        sa.Column("eligible", sa.Integer(), nullable=False),
        sa.Column("policy_min_coverage", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("policy_min_cohort_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "expected >= 0 AND eligible >= 0 AND eligible <= expected",
            name=op.f("ck_location_publication_counts_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["reference_version"],
            ["app.location_reference.version"],
            name=op.f("fk_location_publication_reference_version_location_reference"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["app.location_ingest_run.run_id"],
            name=op.f("fk_location_publication_run_id_location_ingest_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("release_id", name=op.f("pk_location_publication")),
        schema="app",
    )
    op.create_index(
        "ix_location_publication_metric",
        "location_publication",
        ["metric_key", "metric_version", "year"],
        schema="app",
    )
    op.create_table(
        "location_publication_pointer",
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("metric_version", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["app.location_publication.release_id"],
            name=op.f("fk_location_publication_pointer_release_id_location_publication"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "metric_key", "metric_version", "year", name=op.f("pk_location_publication_pointer")
        ),
        schema="app",
    )
    op.create_table(
        "location_quota_stamp",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_location_quota_stamp")),
        schema="app",
    )
    op.create_index(
        "ix_location_quota_stamp_source_at", "location_quota_stamp", ["source", "at"], schema="app"
    )
    # Facts are immutable at the database level (references, territories, observations, releases).
    op.execute(
        "CREATE FUNCTION app.location_refuse_update() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation'; "
        "END $$"
    )
    for table in _IMMUTABLE:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE ON app.{table} "
            "FOR EACH ROW EXECUTE FUNCTION app.location_refuse_update()"
        )


def downgrade() -> None:
    for table in _IMMUTABLE:
        op.execute(f"DROP TRIGGER {table}_immutable ON app.{table}")
    op.execute("DROP FUNCTION app.location_refuse_update()")
    op.drop_index("ix_location_quota_stamp_source_at", table_name="location_quota_stamp", schema="app")
    op.drop_table("location_quota_stamp", schema="app")
    op.drop_table("location_publication_pointer", schema="app")
    op.drop_index("ix_location_publication_metric", table_name="location_publication", schema="app")
    op.drop_table("location_publication", schema="app")
    op.drop_index("ix_location_ingest_run_state", table_name="location_ingest_run", schema="app")
    op.drop_table("location_ingest_run", schema="app")
    op.drop_index("ix_location_observation_metric_year", table_name="location_observation", schema="app")
    op.drop_table("location_observation", schema="app")
    op.drop_index("uq_location_territory_teryt", table_name="location_territory", schema="app")
    op.drop_index("ix_location_territory_level", table_name="location_territory", schema="app")
    op.drop_table("location_territory", schema="app")
    op.drop_table("location_reference", schema="app")
