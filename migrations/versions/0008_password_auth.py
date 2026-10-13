"""user_credential and auth_token for email/password sign-in (expand-only, ADR 0013)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-14 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # GDPR[personal-data]: Argon2id hash only; cascades with the account (erasure), RM-203
    op.create_table(
        "user_credential",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False, comment="GDPR[personal-data]: Argon2id PHC string"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app.app_user.id"], name=op.f("fk_user_credential_user_id_app_user"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_credential")),
        schema="app",
    )
    # GDPR[personal-data]: email and, for registrations, the Argon2id hash; purged after expiry or use (RM-203)
    op.create_table(
        "auth_token",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("email", sa.Text(), nullable=False, comment="GDPR[personal-data]"),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True, comment="GDPR[personal-data]: Argon2id PHC string"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("purpose IN ('register','reset')", name=op.f("ck_auth_token_purpose_vocab")),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_auth_token_email_lowercase")),
        sa.CheckConstraint(
            "(purpose = 'register') = (password_hash IS NOT NULL)", name=op.f("ck_auth_token_register_carries_hash")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app.app_user.id"], name=op.f("fk_auth_token_user_id_app_user"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_auth_token")),
        schema="app",
    )
    op.create_index(
        "uq_auth_token_live",
        "auth_token",
        ["email", "purpose"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("used_at IS NULL"),
    )
    op.create_index("ix_auth_token_expires", "auth_token", ["expires_at"], unique=False, schema="app")


def downgrade() -> None:
    op.drop_index("ix_auth_token_expires", table_name="auth_token", schema="app")
    op.drop_index("uq_auth_token_live", table_name="auth_token", schema="app")
    op.drop_table("auth_token", schema="app")
    op.drop_table("user_credential", schema="app")
