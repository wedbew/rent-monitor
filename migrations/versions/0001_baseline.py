"""baseline: every table of blueprint §3 (expand-only, schema `app`)

Revision ID: 0001
Revises: 
Create Date: 2026-10-11 22:00:30.609973
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('app_user',
    sa.Column('id', sa.Text(), server_default=sa.text('gen_random_uuid()::text'), nullable=False),
    sa.Column('email', sa.Text(), nullable=False, comment='GDPR[personal-data]: stored lower-cased'),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('name', sa.Text(), nullable=True, comment='GDPR[personal-data]'),
    sa.Column('avatar_url', sa.Text(), nullable=True, comment='GDPR[personal-data]'),
    sa.Column('role', sa.String(length=16), server_default='user', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('user','admin')", name=op.f('ck_app_user_role_vocab')),
    sa.CheckConstraint('email = lower(email)', name=op.f('ck_app_user_email_lowercase')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_app_user')),
    sa.UniqueConstraint('email', name=op.f('uq_app_user_email')),
    schema='app'
    )
    op.create_table('listing',
    sa.Column('otodom_id', sa.String(length=16), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('transaction', sa.String(length=8), nullable=True),
    sa.Column('city_slug', sa.String(length=80), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("transaction IN ('SALE','RENT')", name=op.f('ck_listing_transaction_vocab')),
    sa.PrimaryKeyConstraint('otodom_id', name=op.f('pk_listing')),
    schema='app'
    )
    op.create_index(op.f('ix_app_listing_city_slug'), 'listing', ['city_slug'], unique=False, schema='app')
    op.create_table('login_token',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('email', sa.Text(), nullable=False, comment='GDPR[personal-data]'),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('token_hash', name=op.f('pk_login_token')),
    schema='app'
    )
    op.create_index(op.f('ix_app_login_token_email'), 'login_token', ['email'], unique=False, schema='app')
    op.create_index(op.f('ix_app_login_token_expires_at'), 'login_token', ['expires_at'], unique=False, schema='app')
    op.create_table('market_sidecar',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('kind', sa.Enum('otodom_rental', 'otodom_sale', 'bdl_deed', 'cenogram_deed', 'moniter_asking', 'yield_ranking', name='sidecar_kind', schema='app'), nullable=False),
    sa.Column('price_basis', sa.String(length=8), nullable=False),
    sa.Column('city_slug', sa.String(length=80), nullable=False),
    sa.Column('teryt', sa.String(length=12), nullable=True),
    sa.Column('period', sa.Date(), nullable=False),
    sa.Column('size_bucket', sa.String(length=8), nullable=True),
    sa.Column('source_stem', sa.Text(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("(kind IN ('bdl_deed','cenogram_deed') AND price_basis = 'deed') OR (kind IN ('moniter_asking','otodom_sale','yield_ranking') AND price_basis = 'asking') OR (kind = 'otodom_rental' AND price_basis = 'rent')", name=op.f('ck_market_sidecar_asking_is_not_deed')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_market_sidecar')),
    sa.UniqueConstraint('kind', 'city_slug', 'period', 'size_bucket', name='uq_sidecar_grain', postgresql_nulls_not_distinct=True),
    schema='app'
    )
    op.create_index('ix_sidecar_city_kind_period', 'market_sidecar', ['city_slug', 'kind', sa.literal_column('period DESC')], unique=False, schema='app')
    op.create_table('plan',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('stripe_price_id', sa.String(length=64), nullable=True),
    sa.Column('monthly_audit_allowance', sa.Integer(), server_default='0', nullable=False),
    sa.Column('features', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.CheckConstraint('monthly_audit_allowance >= 0', name=op.f('ck_plan_allowance_non_negative')),
    sa.PrimaryKeyConstraint('code', name=op.f('pk_plan')),
    sa.UniqueConstraint('stripe_price_id', name=op.f('uq_plan_stripe_price_id')),
    schema='app'
    )
    op.create_table('stripe_event',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('type', sa.String(length=80), nullable=False),
    sa.Column('api_version', sa.String(length=40), nullable=True),
    sa.Column('stripe_created', sa.DateTime(timezone=True), nullable=False),
    sa.Column('outcome', sa.String(length=16), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("outcome IN ('processed','ignored')", name=op.f('ck_stripe_event_outcome_vocab')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stripe_event')),
    schema='app'
    )
    op.create_index(op.f('ix_app_stripe_event_type'), 'stripe_event', ['type'], unique=False, schema='app')
    op.create_table('auth_identity',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('provider', sa.String(length=16), nullable=False),
    sa.Column('subject', sa.Text(), nullable=False, comment='GDPR[personal-data]: Google sub or email address'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("provider IN ('google','email')", name=op.f('ck_auth_identity_provider_vocab')),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_auth_identity_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_identity')),
    sa.UniqueConstraint('provider', 'subject', name=op.f('uq_auth_identity_provider')),
    schema='app'
    )
    op.create_index(op.f('ix_app_auth_identity_user_id'), 'auth_identity', ['user_id'], unique=False, schema='app')
    op.create_table('credit_account',
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('balance', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint('balance >= 0', name=op.f('ck_credit_account_non_negative')),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_credit_account_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_credit_account')),
    schema='app'
    )
    op.create_table('feature_flag',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('enabled_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('min_plan', sa.String(length=32), nullable=True),
    sa.Column('rollout_pct', sa.Integer(), server_default='0', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('rollout_pct >= 0 AND rollout_pct <= 100', name=op.f('ck_feature_flag_rollout_range')),
    sa.ForeignKeyConstraint(['min_plan'], ['app.plan.code'], name=op.f('fk_feature_flag_min_plan_plan')),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_feature_flag')),
    schema='app'
    )
    op.create_table('listing_snapshot',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('otodom_id', sa.String(length=16), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='GDPR[personal-data]: raw _next/data pageProps.ad'),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['otodom_id'], ['app.listing.otodom_id'], name=op.f('fk_listing_snapshot_otodom_id_listing')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_listing_snapshot')),
    sa.UniqueConstraint('otodom_id', 'content_sha256', name=op.f('uq_listing_snapshot_otodom_id')),
    schema='app'
    )
    op.create_index(op.f('ix_app_listing_snapshot_fetched_at'), 'listing_snapshot', ['fetched_at'], unique=False, schema='app')
    op.create_index(op.f('ix_app_listing_snapshot_otodom_id'), 'listing_snapshot', ['otodom_id'], unique=False, schema='app')
    op.create_table('stripe_customer',
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('stripe_customer_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_stripe_customer_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_stripe_customer')),
    sa.UniqueConstraint('stripe_customer_id', name=op.f('uq_stripe_customer_stripe_customer_id')),
    schema='app'
    )
    op.create_table('subscription',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('plan_code', sa.String(length=32), nullable=False),
    sa.Column('status', sa.Enum('incomplete', 'incomplete_expired', 'trialing', 'active', 'past_due', 'canceled', 'unpaid', 'paused', name='sub_status', schema='app'), nullable=False),
    sa.Column('price_id', sa.String(length=64), nullable=False),
    sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('cancel_at_period_end', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('grace_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('stripe_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('current_period_end > current_period_start', name=op.f('ck_subscription_period_ordered')),
    sa.ForeignKeyConstraint(['plan_code'], ['app.plan.code'], name=op.f('fk_subscription_plan_code_plan')),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_subscription_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subscription')),
    schema='app'
    )
    op.create_index(op.f('ix_app_subscription_user_id'), 'subscription', ['user_id'], unique=False, schema='app')
    op.create_index('uq_subscription_one_live_per_user', 'subscription', ['user_id'], unique=True, schema='app', postgresql_where=sa.text("status IN ('trialing','active','past_due')"))
    op.create_table('user_session',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False, comment='sha256 of the cookie value; raw token is never stored'),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('user_agent', sa.Text(), nullable=True, comment='GDPR[personal-data]'),
    sa.Column('ip', sa.String(length=45), nullable=True, comment='GDPR[personal-data]'),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_user_session_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_session')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_user_session_token_hash')),
    schema='app'
    )
    op.create_index(op.f('ix_app_user_session_expires_at'), 'user_session', ['expires_at'], unique=False, schema='app')
    op.create_index(op.f('ix_app_user_session_user_id'), 'user_session', ['user_id'], unique=False, schema='app')
    op.create_table('feature_override',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('flag_key', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['flag_key'], ['app.feature_flag.key'], name=op.f('fk_feature_override_flag_key_feature_flag'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_feature_override_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_feature_override')),
    sa.UniqueConstraint('flag_key', 'user_id', name=op.f('uq_feature_override_flag_key')),
    schema='app'
    )
    op.create_table('usage_period',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('kind', sa.String(length=12), server_default='subscription', nullable=False),
    sa.Column('subscription_id', sa.String(length=64), nullable=True),
    sa.Column('source_invoice_id', sa.String(length=64), nullable=False, comment='idempotency key for the grant'),
    sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('allowance', sa.Integer(), nullable=False),
    sa.Column('used', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint("(kind = 'subscription') = (subscription_id IS NOT NULL)", name=op.f('ck_usage_period_subscription_matches_kind')),
    sa.CheckConstraint("kind IN ('subscription','pass')", name=op.f('ck_usage_period_kind_vocab')),
    sa.CheckConstraint('period_end > period_start', name=op.f('ck_usage_period_period_ordered')),
    sa.CheckConstraint('used >= 0 AND used <= allowance', name=op.f('ck_usage_period_used_within_allowance')),
    sa.ForeignKeyConstraint(['subscription_id'], ['app.subscription.id'], name=op.f('fk_usage_period_subscription_id_subscription')),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_usage_period_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usage_period')),
    sa.UniqueConstraint('source_invoice_id', name=op.f('uq_usage_period_source_invoice_id')),
    schema='app'
    )
    op.create_index('ix_usage_period_user_window', 'usage_period', ['user_id', 'period_end'], unique=False, schema='app')
    op.create_table('audit',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('otodom_id', sa.String(length=16), nullable=False),
    sa.Column('snapshot_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('queued', 'running', 'succeeded', 'succeeded_degraded', 'rejected', 'failed_input', 'failed_upstream', 'failed_internal', 'cancelled', name='audit_status', schema='app'), nullable=False),
    sa.Column('error_code', sa.String(length=40), nullable=True),
    sa.Column('charge_source', sa.Enum('plan', 'credit', 'admin_free', name='charge_source', schema='app'), nullable=False),
    sa.Column('charge_state', sa.Enum('reserved', 'captured', 'released', name='charge_state', schema='app'), nullable=False),
    sa.Column('usage_period_id', sa.BigInteger(), nullable=True),
    sa.Column('lang', sa.String(length=2), server_default='pl', nullable=False),
    sa.Column('analyst', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('engine_version', sa.String(length=40), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='canonical DealAnalysis JSON'),
    sa.Column('grade', sa.String(length=2), nullable=True),
    sa.Column('asking_price_pln', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('max_bid_pln', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('irr_10y', sa.Numeric(precision=7, scale=4), nullable=True),
    sa.Column('capex_pln', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(charge_source = 'plan') = (usage_period_id IS NOT NULL)", name=op.f('ck_audit_plan_has_period')),
    sa.CheckConstraint("lang IN ('pl','en')", name=op.f('ck_audit_lang_vocab')),
    sa.ForeignKeyConstraint(['otodom_id'], ['app.listing.otodom_id'], name=op.f('fk_audit_otodom_id_listing')),
    sa.ForeignKeyConstraint(['snapshot_id'], ['app.listing_snapshot.id'], name=op.f('fk_audit_snapshot_id_listing_snapshot')),
    sa.ForeignKeyConstraint(['usage_period_id'], ['app.usage_period.id'], name=op.f('fk_audit_usage_period_id_usage_period')),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_audit_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit')),
    schema='app'
    )
    op.create_index('ix_audit_user_created', 'audit', ['user_id', sa.literal_column('created_at DESC')], unique=False, schema='app')
    op.create_index('uq_audit_one_active_per_listing', 'audit', ['user_id', 'otodom_id'], unique=True, schema='app', postgresql_where=sa.text("status IN ('queued','running')"))
    op.create_table('audit_event',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('audit_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('stage', sa.String(length=16), nullable=True),
    sa.Column('pct', sa.Integer(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('progress','done','error')", name=op.f('ck_audit_event_kind_vocab')),
    sa.CheckConstraint('pct IS NULL OR (pct >= 0 AND pct <= 100)', name=op.f('ck_audit_event_pct_range')),
    sa.ForeignKeyConstraint(['audit_id'], ['app.audit.id'], name=op.f('fk_audit_event_audit_id_audit'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_event')),
    schema='app'
    )
    op.create_index('ix_audit_event_audit_id', 'audit_event', ['audit_id', 'id'], unique=False, schema='app')
    op.create_table('credit_ledger',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('delta', sa.Integer(), nullable=False),
    sa.Column('reason', sa.Enum('signup_grant', 'admin_adjust', 'topup', 'reserve', 'release', name='credit_reason', schema='app'), nullable=False),
    sa.Column('idempotency_key', sa.String(length=120), nullable=False),
    sa.Column('audit_id', sa.Uuid(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('delta <> 0', name=op.f('ck_credit_ledger_non_zero')),
    sa.ForeignKeyConstraint(['audit_id'], ['app.audit.id'], name=op.f('fk_credit_ledger_audit_id_audit')),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_credit_ledger_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_credit_ledger')),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_credit_ledger_idempotency_key')),
    schema='app'
    )
    op.create_index(op.f('ix_app_credit_ledger_user_id'), 'credit_ledger', ['user_id'], unique=False, schema='app')
    op.create_table('saved_listing',
    sa.Column('user_id', sa.Text(), nullable=False),
    sa.Column('otodom_id', sa.String(length=16), nullable=False),
    sa.Column('latest_audit_id', sa.Uuid(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True, comment='GDPR[personal-data]: free text written by the user'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['latest_audit_id'], ['app.audit.id'], name=op.f('fk_saved_listing_latest_audit_id_audit'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['otodom_id'], ['app.listing.otodom_id'], name=op.f('fk_saved_listing_otodom_id_listing')),
    sa.ForeignKeyConstraint(['user_id'], ['app.app_user.id'], name=op.f('fk_saved_listing_user_id_app_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'otodom_id', name=op.f('pk_saved_listing')),
    schema='app'
    )


def downgrade() -> None:
    op.drop_table('saved_listing', schema='app')
    op.drop_index(op.f('ix_app_credit_ledger_user_id'), table_name='credit_ledger', schema='app')
    op.drop_table('credit_ledger', schema='app')
    op.drop_index('ix_audit_event_audit_id', table_name='audit_event', schema='app')
    op.drop_table('audit_event', schema='app')
    op.drop_index('uq_audit_one_active_per_listing', table_name='audit', schema='app', postgresql_where=sa.text("status IN ('queued','running')"))
    op.drop_index('ix_audit_user_created', table_name='audit', schema='app')
    op.drop_table('audit', schema='app')
    op.drop_index('ix_usage_period_user_window', table_name='usage_period', schema='app')
    op.drop_table('usage_period', schema='app')
    op.drop_table('feature_override', schema='app')
    op.drop_index(op.f('ix_app_user_session_user_id'), table_name='user_session', schema='app')
    op.drop_index(op.f('ix_app_user_session_expires_at'), table_name='user_session', schema='app')
    op.drop_table('user_session', schema='app')
    op.drop_index('uq_subscription_one_live_per_user', table_name='subscription', schema='app', postgresql_where=sa.text("status IN ('trialing','active','past_due')"))
    op.drop_index(op.f('ix_app_subscription_user_id'), table_name='subscription', schema='app')
    op.drop_table('subscription', schema='app')
    op.drop_table('stripe_customer', schema='app')
    op.drop_index(op.f('ix_app_listing_snapshot_otodom_id'), table_name='listing_snapshot', schema='app')
    op.drop_index(op.f('ix_app_listing_snapshot_fetched_at'), table_name='listing_snapshot', schema='app')
    op.drop_table('listing_snapshot', schema='app')
    op.drop_table('feature_flag', schema='app')
    op.drop_table('credit_account', schema='app')
    op.drop_index(op.f('ix_app_auth_identity_user_id'), table_name='auth_identity', schema='app')
    op.drop_table('auth_identity', schema='app')
    op.drop_index(op.f('ix_app_stripe_event_type'), table_name='stripe_event', schema='app')
    op.drop_table('stripe_event', schema='app')
    op.drop_table('plan', schema='app')
    op.drop_index('ix_sidecar_city_kind_period', table_name='market_sidecar', schema='app')
    op.drop_table('market_sidecar', schema='app')
    op.drop_index(op.f('ix_app_login_token_expires_at'), table_name='login_token', schema='app')
    op.drop_index(op.f('ix_app_login_token_email'), table_name='login_token', schema='app')
    op.drop_table('login_token', schema='app')
    op.drop_index(op.f('ix_app_listing_city_slug'), table_name='listing', schema='app')
    op.drop_table('listing', schema='app')
    op.drop_table('app_user', schema='app')
    op.execute("DROP TYPE IF EXISTS app.sidecar_kind")
    op.execute("DROP TYPE IF EXISTS app.sub_status")
    op.execute("DROP TYPE IF EXISTS app.audit_status")
    op.execute("DROP TYPE IF EXISTS app.charge_source")
    op.execute("DROP TYPE IF EXISTS app.charge_state")
    op.execute("DROP TYPE IF EXISTS app.credit_reason")
