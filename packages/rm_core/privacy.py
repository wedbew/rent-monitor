"""GDPR retention sweeps, account erasure, re-erasure after a restore, and the data-subject export (RM-30).

GDPR[retention]: bounded batch deletes of expired sessions, login tokens, listing snapshots and audit events.
GDPR[erasure]: `delete_account` removes every tenant-owned row (FK cascade) and logs only a hash.
GDPR[personal-data]: `export_user_data` collects everything we hold about one user for an access request.
Retention periods are PROPOSED defaults (settings); counsel confirms them (docs/PRE-DEPLOYMENT.md section 4).
Invoices stay in Fakturownia for tax reasons and are not erased here; the caller erases the Stripe customer
(`ErasureReport.stripe_customer_id`).
"""

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import CursorResult, Delete, Update, and_, delete, exists, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import (
    Audit,
    AuditEvent,
    AuthIdentity,
    CreditAccount,
    CreditLedger,
    ErasureLog,
    FeatureOverride,
    GeoCache,
    ListingSnapshot,
    LoginToken,
    SavedListing,
    StripeCustomer,
    Subscription,
    UsagePeriod,
    User,
    UserSession,
)
from rm_core.settings import Settings

BATCH_SIZE = 1000
ERASURE_LOG_RETENTION = timedelta(days=70)  # longest backup (56 days) plus a restore window


def user_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()


def _ago(days: int) -> Any:
    return func.clock_timestamp() - literal(timedelta(days=days))


# ---------- retention sweeps ----------
@dataclass(frozen=True)
class PurgeReport:
    sessions: int = 0
    login_tokens: int = 0
    snapshots_deleted: int = 0
    snapshots_scrubbed: int = 0
    audit_events: int = 0
    erasure_log: int = 0
    geo_cache: int = 0


async def _until_drained(
    sessionmaker: async_sessionmaker[AsyncSession], build: Callable[[], Delete | Update]
) -> int:
    """Run `build()` (a bounded DELETE/UPDATE) in its own short transaction until a batch comes back short."""
    total = 0
    while True:
        async with sessionmaker() as session, session.begin():
            result = cast("CursorResult[Any]", await session.execute(build()))
            n = int(result.rowcount)
        total += n
        if n < BATCH_SIZE:
            return total


async def purge_expired(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> PurgeReport:
    sessions = await _until_drained(
        sessionmaker,
        lambda: delete(UserSession).where(
            UserSession.id.in_(
                select(UserSession.id)
                .where(UserSession.expires_at < _ago(settings.retention_session_days))
                .limit(BATCH_SIZE)
            )
        ),
    )
    tokens = await _until_drained(
        sessionmaker,
        lambda: delete(LoginToken).where(
            LoginToken.token_hash.in_(
                select(LoginToken.token_hash)
                .where(
                    or_(
                        LoginToken.expires_at < _ago(settings.retention_login_token_days),
                        LoginToken.used_at < _ago(settings.retention_login_token_days),
                    )
                )
                .limit(BATCH_SIZE)
            )
        ),
    )
    referenced = exists().where(Audit.snapshot_id == ListingSnapshot.id)
    cutoff = _ago(settings.retention_snapshot_days)
    snapshots_deleted = await _until_drained(
        sessionmaker,
        lambda: delete(ListingSnapshot).where(
            ListingSnapshot.id.in_(
                select(ListingSnapshot.id)
                .where(and_(ListingSnapshot.fetched_at < cutoff, ~referenced))
                .limit(BATCH_SIZE)
            )
        ),
    )
    # Snapshots an audit still points at keep their identity but lose the raw third-party payload.
    snapshots_scrubbed = await _until_drained(
        sessionmaker,
        lambda: (
            update(ListingSnapshot)
            .where(
                ListingSnapshot.id.in_(
                    select(ListingSnapshot.id)
                    .where(
                        and_(ListingSnapshot.fetched_at < cutoff, referenced, ListingSnapshot.payload != {})
                    )
                    .limit(BATCH_SIZE)
                )
            )
            .values(payload={})
        ),
    )
    events = await _until_drained(
        sessionmaker,
        lambda: delete(AuditEvent).where(
            AuditEvent.id.in_(
                select(AuditEvent.id)
                .where(AuditEvent.created_at < _ago(settings.retention_audit_event_days))
                .limit(BATCH_SIZE)
            )
        ),
    )
    erasure = await _until_drained(
        sessionmaker,
        lambda: delete(ErasureLog).where(
            ErasureLog.id.in_(
                select(ErasureLog.id)
                .where(ErasureLog.erased_at < func.clock_timestamp() - literal(ERASURE_LOG_RETENTION))
                .limit(BATCH_SIZE)
            )
        ),
    )
    geo = await _until_drained(
        sessionmaker,
        lambda: delete(GeoCache).where(
            GeoCache.key.in_(
                select(GeoCache.key).where(GeoCache.expires_at < func.clock_timestamp()).limit(BATCH_SIZE)
            )
        ),
    )
    return PurgeReport(sessions, tokens, snapshots_deleted, snapshots_scrubbed, events, erasure, geo)


# ---------- erasure ----------
@dataclass(frozen=True)
class ErasureReport:
    deleted: bool
    stripe_customer_id: str | None  # the caller must delete this customer at Stripe (processor)


async def delete_account(session: AsyncSession, user_id: str) -> ErasureReport:
    """Erase one user in the caller's transaction. Idempotent; one concurrent caller sees `deleted=True`."""
    stripe_id = await session.scalar(
        select(StripeCustomer.stripe_customer_id).where(StripeCustomer.user_id == user_id)
    )
    # FK cascade removes every tenant-owned row; RETURNING tells us whether this call really deleted the user.
    deleted_id = await session.scalar(delete(User).where(User.id == user_id).returning(User.id))
    if deleted_id is None:
        return ErasureReport(False, None)
    await session.execute(insert(ErasureLog).values(user_hash=user_hash(user_id)).on_conflict_do_nothing())
    return ErasureReport(True, stripe_id)


async def reapply_erasures(session: AsyncSession, hashes: Iterable[str]) -> int:
    """After restoring an older backup: delete users whose hash is in an erasure log exported earlier."""
    wanted = [h for h in {h.lower() for h in hashes} if len(h) == 64]
    if not wanted:
        return 0
    digest = func.encode(func.sha256(func.convert_to(User.id, "UTF8")), "hex")
    ids = (await session.scalars(select(User.id).where(digest.in_(wanted)))).all()
    for uid in ids:
        await delete_account(session, uid)
    return len(ids)


# ---------- data-subject export ----------
class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExportProfile(_Row):
    id: str
    email: str
    name: str | None
    avatar_url: str | None
    role: str
    email_verified_at: datetime | None
    created_at: datetime


class ExportIdentity(_Row):
    provider: str
    subject: str
    created_at: datetime


class ExportSession(_Row):
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None
    ip: str | None


class ExportLedgerEntry(_Row):
    delta: int
    reason: str
    note: str | None
    audit_id: UUID | None
    created_at: datetime


class ExportSubscription(_Row):
    id: str
    plan_code: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool


class ExportUsagePeriod(_Row):
    kind: str
    period_start: datetime
    period_end: datetime
    allowance: int
    used: int


class ExportAudit(_Row):
    id: UUID
    otodom_id: str
    status: str
    error_code: str | None
    lang: str
    grade: str | None
    asking_price_pln: Decimal | None
    max_bid_pln: Decimal | None
    created_at: datetime
    finished_at: datetime | None
    result: dict[str, Any] | None


class ExportSaved(_Row):
    otodom_id: str
    note: str | None
    created_at: datetime


class ExportOverride(_Row):
    flag_key: str
    enabled: bool
    reason: str
    expires_at: datetime | None


class UserDataExport(_Row):
    exported_at: datetime
    profile: ExportProfile
    identities: list[ExportIdentity]
    sessions: list[ExportSession]
    credit_balance: int | None
    credit_ledger: list[ExportLedgerEntry]
    subscriptions: list[ExportSubscription]
    usage_periods: list[ExportUsagePeriod]
    audits: list[ExportAudit]
    saved_listings: list[ExportSaved]
    feature_overrides: list[ExportOverride]


async def export_user_data(session: AsyncSession, user_id: str) -> UserDataExport | None:
    """Everything we hold about one user, excluding secrets (token hashes) and other tenants' data."""
    user = await session.get(User, user_id)
    if user is None:
        return None
    now = await session.scalar(select(func.clock_timestamp()))
    assert now is not None  # noqa: S101
    ident = (
        await session.scalars(
            select(AuthIdentity).where(AuthIdentity.user_id == user_id).order_by(AuthIdentity.id)
        )
    ).all()
    sess = (
        await session.scalars(
            select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.id)
        )
    ).all()
    ledger = (
        await session.scalars(
            select(CreditLedger).where(CreditLedger.user_id == user_id).order_by(CreditLedger.id)
        )
    ).all()
    subs = (await session.scalars(select(Subscription).where(Subscription.user_id == user_id))).all()
    periods = (
        await session.scalars(
            select(UsagePeriod).where(UsagePeriod.user_id == user_id).order_by(UsagePeriod.id)
        )
    ).all()
    audits = (
        await session.scalars(select(Audit).where(Audit.user_id == user_id).order_by(Audit.created_at))
    ).all()
    saved = (await session.scalars(select(SavedListing).where(SavedListing.user_id == user_id))).all()
    overrides = (
        await session.scalars(select(FeatureOverride).where(FeatureOverride.user_id == user_id))
    ).all()
    balance = await session.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == user_id))
    return UserDataExport(
        exported_at=now,
        profile=ExportProfile(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            role=user.role,
            email_verified_at=user.email_verified_at,
            created_at=user.created_at,
        ),
        identities=[
            ExportIdentity(provider=i.provider, subject=i.subject, created_at=i.created_at) for i in ident
        ],
        sessions=[
            ExportSession(
                last_seen_at=s.last_seen_at, expires_at=s.expires_at, user_agent=s.user_agent, ip=s.ip
            )
            for s in sess
        ],
        credit_balance=balance,
        credit_ledger=[
            ExportLedgerEntry(
                delta=e.delta,
                reason=e.reason.value,
                note=e.note,
                audit_id=e.audit_id,
                created_at=e.created_at,
            )
            for e in ledger
        ],
        subscriptions=[
            ExportSubscription(
                id=s.id,
                plan_code=s.plan_code,
                status=s.status.value,
                current_period_start=s.current_period_start,
                current_period_end=s.current_period_end,
                cancel_at_period_end=s.cancel_at_period_end,
            )
            for s in subs
        ],
        usage_periods=[
            ExportUsagePeriod(
                kind=p.kind,
                period_start=p.period_start,
                period_end=p.period_end,
                allowance=p.allowance,
                used=p.used,
            )
            for p in periods
        ],
        audits=[
            ExportAudit(
                id=a.id,
                otodom_id=a.otodom_id,
                status=a.status.value,
                error_code=a.error_code,
                lang=a.lang,
                grade=a.grade,
                asking_price_pln=a.asking_price_pln,
                max_bid_pln=a.max_bid_pln,
                created_at=a.created_at,
                finished_at=a.finished_at,
                result=a.result,
            )
            for a in audits
        ],
        saved_listings=[
            ExportSaved(otodom_id=x.otodom_id, note=x.note, created_at=x.created_at) for x in saved
        ],
        feature_overrides=[
            ExportOverride(flag_key=o.flag_key, enabled=o.enabled, reason=o.reason, expires_at=o.expires_at)
            for o in overrides
        ],
    )
