"""SQLAlchemy 2 models for schema `app` (blueprint §3).

Alembic owns the schema; Procrastinate owns its own tables.

Beyond the blueprint sketch: every constraint is named, ranges and vocabularies are CHECKed in the database,
JSONB columns are typed `dict[str, Any]`, ids default server-side too, and money is NUMERIC.
Tenant = user: every tenant-owned row carries `user_id`; access goes through a `Principal`-scoped repository.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from rm_core.db.base import Base, pg_enum


def user_fk() -> ForeignKey:
    return ForeignKey("app_user.id", ondelete="CASCADE")


_UUID_DEFAULT = text("gen_random_uuid()")


# ---------- Identity and sessions (owned by this app) ----------
class User(Base):
    """GDPR[personal-data]: email, name, avatar_url.

    Retention: until account deletion (cascade). Erasure: DELETE the row (RM-30).
    """

    __tablename__ = "app_user"  # 'user' is reserved in Postgres
    __table_args__ = (
        CheckConstraint("role IN ('user','admin')", name="role_vocab"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid4()), server_default=text("gen_random_uuid()::text")
    )
    email: Mapped[str] = mapped_column(Text, unique=True, comment="GDPR[personal-data]: stored lower-cased")
    email_verified_at: Mapped[datetime | None]
    name: Mapped[str | None] = mapped_column(Text, comment="GDPR[personal-data]")
    avatar_url: Mapped[str | None] = mapped_column(Text, comment="GDPR[personal-data]")
    role: Mapped[str] = mapped_column(String(16), default="user", server_default="user")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuthIdentity(Base):
    """One row per login method: ('google', sub) or ('email', address). Key on `sub`, never on email."""

    __tablename__ = "auth_identity"
    __table_args__ = (
        UniqueConstraint("provider", "subject"),
        CheckConstraint("provider IN ('google','email')", name="provider_vocab"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, user_fk(), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(Text, comment="GDPR[personal-data]: Google sub or email address")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class UserSession(Base):
    """GDPR[personal-data]: ip, user_agent. Retention: until `expires_at` plus purge job (RM-30)."""

    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, comment="sha256 of the cookie value; raw token is never stored"
    )
    user_id: Mapped[str] = mapped_column(Text, user_fk(), index=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_agent: Mapped[str | None] = mapped_column(Text, comment="GDPR[personal-data]")
    ip: Mapped[str | None] = mapped_column(String(45), comment="GDPR[personal-data]")


class LoginToken(Base):
    """Email magic link: single use, 30 minutes.

    GDPR[personal-data]: email. Retention: purged after expiry (RM-30).
    """

    __tablename__ = "login_token"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(Text, index=True, comment="GDPR[personal-data]")
    expires_at: Mapped[datetime] = mapped_column(index=True)
    used_at: Mapped[datetime | None]


# ---------- Plans, Stripe, subscriptions ----------
class SubStatus(StrEnum):
    incomplete = "incomplete"
    incomplete_expired = "incomplete_expired"
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    unpaid = "unpaid"
    paused = "paused"


class Plan(Base):
    __tablename__ = "plan"
    __table_args__ = (CheckConstraint("monthly_audit_allowance >= 0", name="allowance_non_negative"),)

    code: Mapped[str] = mapped_column(String(32), primary_key=True)  # free | pro
    stripe_price_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    monthly_audit_allowance: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    features: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class StripeCustomer(Base):
    """GDPR[processor]: Stripe holds the customer record. Erased with the user."""

    __tablename__ = "stripe_customer"

    user_id: Mapped[str] = mapped_column(Text, user_fk(), primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscription"
    __table_args__ = (
        Index(
            "uq_subscription_one_live_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('trialing','active','past_due')"),
        ),
        CheckConstraint("current_period_end > current_period_start", name="period_ordered"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sub_...
    user_id: Mapped[str] = mapped_column(Text, user_fk(), index=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plan.code"))
    status: Mapped[SubStatus] = mapped_column(pg_enum(SubStatus, "sub_status"))
    price_id: Mapped[str] = mapped_column(String(64))
    current_period_start: Mapped[datetime]  # from items.data[0] (API >= 2025-03-31.basil)
    current_period_end: Mapped[datetime]
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    grace_until: Mapped[datetime | None]
    stripe_seen_at: Mapped[datetime]  # newest event.created applied
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class StripeEvent(Base):
    """Idempotency log, inserted in the same transaction as the side effects.

    GDPR[processor]: the payload comes from Stripe.
    """

    __tablename__ = "stripe_event"
    __table_args__ = (CheckConstraint("outcome IN ('processed','ignored')", name="outcome_vocab"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # evt_...
    type: Mapped[str] = mapped_column(String(80), index=True)
    api_version: Mapped[str | None] = mapped_column(String(40))
    stripe_created: Mapped[datetime]
    outcome: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]]
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ---------- Quota: plan allowance per period + discrete credit ledger ----------
class UsagePeriod(Base):
    __tablename__ = "usage_period"
    __table_args__ = (
        CheckConstraint("used >= 0 AND used <= allowance", name="used_within_allowance"),
        CheckConstraint("period_end > period_start", name="period_ordered"),
        CheckConstraint("kind IN ('subscription','pass')", name="kind_vocab"),
        CheckConstraint(
            "(kind = 'subscription') = (subscription_id IS NOT NULL)", name="subscription_matches_kind"
        ),
        Index("ix_usage_period_user_window", "user_id", "period_end"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, user_fk())
    kind: Mapped[str] = mapped_column(String(12), default="subscription", server_default="subscription")
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscription.id"))  # None for a pass
    source_invoice_id: Mapped[str] = mapped_column(
        String(64), unique=True, comment="idempotency key for the grant"
    )
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    allowance: Mapped[int]
    used: Mapped[int] = mapped_column(default=0, server_default="0")


class CreditReason(StrEnum):
    signup_grant = "signup_grant"
    admin_adjust = "admin_adjust"
    topup = "topup"
    reserve = "reserve"
    release = "release"


class CreditAccount(Base):
    """Balance cache; row-locked (FOR UPDATE) for every mutation."""

    __tablename__ = "credit_account"
    __table_args__ = (CheckConstraint("balance >= 0", name="non_negative"),)

    user_id: Mapped[str] = mapped_column(Text, user_fk(), primary_key=True)
    balance: Mapped[int] = mapped_column(default=0, server_default="0")


class CreditLedger(Base):
    """Append-only. SUM(delta) per user must equal credit_account.balance (nightly check, RM-25)."""

    __tablename__ = "credit_ledger"
    __table_args__ = (CheckConstraint("delta <> 0", name="non_zero"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, user_fk(), index=True)
    delta: Mapped[int]
    reason: Mapped[CreditReason] = mapped_column(pg_enum(CreditReason, "credit_reason"))
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    audit_id: Mapped[UUID | None] = mapped_column(ForeignKey("audit.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ---------- Listings, audits, progress, saved ----------
class AuditStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    succeeded_degraded = "succeeded_degraded"
    rejected = "rejected"
    failed_input = "failed_input"
    failed_upstream = "failed_upstream"
    failed_internal = "failed_internal"
    cancelled = "cancelled"


class ChargeSource(StrEnum):
    plan = "plan"
    credit = "credit"
    admin_free = "admin_free"


class ChargeState(StrEnum):
    reserved = "reserved"
    captured = "captured"
    released = "released"


class Listing(Base):
    """Public listing identity, shared across tenants.

    LEGAL[scraping]: derived from fetched third-party pages.
    """

    __tablename__ = "listing"
    __table_args__ = (CheckConstraint("transaction IN ('SALE','RENT')", name="transaction_vocab"),)

    otodom_id: Mapped[str] = mapped_column(String(16), primary_key=True)  # ID4CpHB
    url: Mapped[str] = mapped_column(Text)
    transaction: Mapped[str | None] = mapped_column(String(8))
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ListingSnapshot(Base):
    """LEGAL[scraping]: raw fetched page payload shared across tenants for 6 h (RM-22).
    GDPR[personal-data]: payload may contain seller name or phone.
    Retention and erasure: purge job (RM-30).
    """

    __tablename__ = "listing_snapshot"
    __table_args__ = (UniqueConstraint("otodom_id", "content_sha256"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=_UUID_DEFAULT)
    otodom_id: Mapped[str] = mapped_column(ForeignKey("listing.otodom_id"), index=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(
        comment="GDPR[personal-data]: raw _next/data pageProps.ad"
    )
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class Audit(Base):
    __tablename__ = "audit"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", text("created_at DESC")),
        Index(
            "uq_audit_one_active_per_listing",
            "user_id",
            "otodom_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
        ),
        CheckConstraint("(charge_source = 'plan') = (usage_period_id IS NOT NULL)", name="plan_has_period"),
        CheckConstraint("lang IN ('pl','en')", name="lang_vocab"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=_UUID_DEFAULT)
    user_id: Mapped[str] = mapped_column(Text, user_fk())
    otodom_id: Mapped[str] = mapped_column(ForeignKey("listing.otodom_id"))
    snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("listing_snapshot.id"))
    status: Mapped[AuditStatus] = mapped_column(pg_enum(AuditStatus, "audit_status"))
    error_code: Mapped[str | None] = mapped_column(String(40))
    charge_source: Mapped[ChargeSource] = mapped_column(pg_enum(ChargeSource, "charge_source"))
    charge_state: Mapped[ChargeState] = mapped_column(pg_enum(ChargeState, "charge_state"))
    usage_period_id: Mapped[int | None] = mapped_column(ForeignKey("usage_period.id"))
    lang: Mapped[str] = mapped_column(String(2), default="pl", server_default="pl")
    analyst: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    engine_version: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[int]
    result: Mapped[dict[str, Any] | None] = mapped_column(comment="canonical DealAnalysis JSON")
    # Extracted for filtering and sorting: copied from `result`, never computed here (invariant 4).
    grade: Mapped[str | None] = mapped_column(String(2))
    asking_price_pln: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    max_bid_pln: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    irr_10y: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    capex_pln: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_audit_id", "audit_id", "id"),
        CheckConstraint("kind IN ('progress','done','error')", name="kind_vocab"),
        CheckConstraint("pct IS NULL OR (pct >= 0 AND pct <= 100)", name="pct_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)  # SSE id
    audit_id: Mapped[UUID] = mapped_column(ForeignKey("audit.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12))
    stage: Mapped[str | None] = mapped_column(String(16))
    pct: Mapped[int | None]
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SavedListing(Base):
    __tablename__ = "saved_listing"

    user_id: Mapped[str] = mapped_column(Text, user_fk(), primary_key=True)
    otodom_id: Mapped[str] = mapped_column(ForeignKey("listing.otodom_id"), primary_key=True)
    latest_audit_id: Mapped[UUID | None] = mapped_column(ForeignKey("audit.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(
        Text, comment="GDPR[personal-data]: free text written by the user"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ---------- Market sidecars (written by fresh importers; never copied from the POC corpus) ----------
class SidecarKind(StrEnum):
    otodom_rental = "otodom_rental"
    otodom_sale = "otodom_sale"
    bdl_deed = "bdl_deed"
    cenogram_deed = "cenogram_deed"
    moniter_asking = "moniter_asking"
    yield_ranking = "yield_ranking"


class MarketSidecar(Base):
    """LEGAL[third-party-data]: market data from GUS BDL, Moniter, Cenogram, Otodom.

    LEGAL[scraping] for the Otodom-derived kinds.
    """

    __tablename__ = "market_sidecar"
    __table_args__ = (
        UniqueConstraint(
            "kind",
            "city_slug",
            "period",
            "size_bucket",
            name="uq_sidecar_grain",
            postgresql_nulls_not_distinct=True,
        ),
        # Invariant 2: asking is never deed. Enforced by the database, not by convention.
        CheckConstraint(
            "(kind IN ('bdl_deed','cenogram_deed') AND price_basis = 'deed') OR "
            "(kind IN ('moniter_asking','otodom_sale','yield_ranking') AND price_basis = 'asking') OR "
            "(kind = 'otodom_rental' AND price_basis = 'rent')",
            name="asking_is_not_deed",
        ),
        Index("ix_sidecar_city_kind_period", "city_slug", "kind", text("period DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kind: Mapped[SidecarKind] = mapped_column(pg_enum(SidecarKind, "sidecar_kind"))
    price_basis: Mapped[str] = mapped_column(String(8))  # asking | deed | rent
    city_slug: Mapped[str] = mapped_column(String(80))  # 'pl' for national rankings
    teryt: Mapped[str | None] = mapped_column(String(12))
    period: Mapped[date] = mapped_column(Date)  # first day of month or quarter
    size_bucket: Mapped[str | None] = mapped_column(String(8))  # 0-30 | 30-50 | 50-70 | 70+
    source_stem: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]]
    generated_at: Mapped[datetime]


# ---------- Feature flags ----------
class FeatureFlag(Base):
    __tablename__ = "feature_flag"
    __table_args__ = (CheckConstraint("rollout_pct >= 0 AND rollout_pct <= 100", name="rollout_range"),)

    key: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )  # screener, redesign, analyst, legal switches
    description: Mapped[str] = mapped_column(Text)
    enabled_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    min_plan: Mapped[str | None] = mapped_column(ForeignKey("plan.code"))
    rollout_pct: Mapped[int] = mapped_column(default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class FeatureOverride(Base):
    __tablename__ = "feature_override"
    __table_args__ = (UniqueConstraint("flag_key", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    flag_key: Mapped[str] = mapped_column(ForeignKey("feature_flag.key", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(Text, user_fk())
    enabled: Mapped[bool]
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None]
    created_by: Mapped[str] = mapped_column(Text)
