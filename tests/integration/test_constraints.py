"""Database-enforced rules: uniqueness, ranges, vocabularies and erasure cascade (blueprint §3)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from rm_core.db.models import (
    Audit,
    AuditEvent,
    AuditStatus,
    AuthIdentity,
    ChargeSource,
    ChargeState,
    CreditAccount,
    CreditLedger,
    CreditReason,
    Listing,
    Plan,
    Subscription,
    SubStatus,
    UsagePeriod,
    User,
    UserSession,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


async def _user(s: AsyncSession, email: str = "a@example.test") -> User:
    u = User(email=email)
    s.add(u)
    await s.flush()
    return u


async def _listing(s: AsyncSession, oid: str = "ID4CpHB") -> Listing:
    existing = await s.get(Listing, oid)
    if existing:
        return existing
    ls = Listing(otodom_id=oid, url=f"https://example.test/{oid}", transaction="SALE")
    s.add(ls)
    await s.flush()
    return ls


def _audit(user_id: str, oid: str, status: AuditStatus = AuditStatus.queued) -> Audit:
    return Audit(
        user_id=user_id,
        otodom_id=oid,
        status=status,
        charge_source=ChargeSource.credit,
        charge_state=ChargeState.reserved,
        engine_version="test",
        schema_version=1,
    )


async def test_email_must_be_lowercase(session: AsyncSession) -> None:
    session.add(User(email="Mixed@Example.test"))
    with pytest.raises(IntegrityError, match="email_lowercase"):
        await session.flush()


async def test_role_vocabulary(session: AsyncSession) -> None:
    session.add(User(email="r@example.test", role="root"))
    with pytest.raises(IntegrityError, match="role_vocab"):
        await session.flush()


async def test_identity_is_unique_per_provider_subject(session: AsyncSession) -> None:
    u1, u2 = await _user(session, "1@example.test"), await _user(session, "2@example.test")
    session.add(AuthIdentity(user_id=u1.id, provider="google", subject="sub-1"))
    await session.flush()
    session.add(AuthIdentity(user_id=u2.id, provider="google", subject="sub-1"))
    with pytest.raises(IntegrityError, match="uq_auth_identity"):
        await session.flush()


async def test_one_active_audit_per_user_and_listing(session: AsyncSession) -> None:
    u = await _user(session)
    ls = await _listing(session)
    session.add(_audit(u.id, ls.otodom_id))
    await session.flush()
    session.add(_audit(u.id, ls.otodom_id, AuditStatus.running))
    with pytest.raises(IntegrityError, match="uq_audit_one_active_per_listing"):
        await session.flush()


async def test_finished_audit_does_not_block_a_new_one(session: AsyncSession) -> None:
    u = await _user(session)
    ls = await _listing(session)
    session.add(_audit(u.id, ls.otodom_id, AuditStatus.succeeded))
    session.add(_audit(u.id, ls.otodom_id))
    await session.flush()


async def test_plan_charge_requires_a_usage_period(session: AsyncSession) -> None:
    u = await _user(session)
    ls = await _listing(session)
    a = _audit(u.id, ls.otodom_id)
    a.charge_source = ChargeSource.plan
    session.add(a)
    with pytest.raises(IntegrityError, match="plan_has_period"):
        await session.flush()


async def test_credit_balance_cannot_go_negative(session: AsyncSession) -> None:
    u = await _user(session)
    session.add(CreditAccount(user_id=u.id, balance=-1))
    with pytest.raises(IntegrityError, match="non_negative"):
        await session.flush()


async def test_ledger_idempotency_key_is_unique_and_delta_non_zero(session: AsyncSession) -> None:
    u = await _user(session)
    session.add(
        CreditLedger(
            user_id=u.id, delta=3, reason=CreditReason.signup_grant, idempotency_key=f"signup:{u.id}"
        )
    )
    await session.flush()
    async with session.begin_nested():
        session.add(
            CreditLedger(
                user_id=u.id, delta=3, reason=CreditReason.signup_grant, idempotency_key=f"signup:{u.id}"
            )
        )
        with pytest.raises(IntegrityError, match="credit_ledger_idempotency_key"):
            await session.flush()
    session.add(
        CreditLedger(user_id=u.id, delta=0, reason=CreditReason.admin_adjust, idempotency_key="admin:zero")
    )
    with pytest.raises(IntegrityError, match="non_zero"):
        await session.flush()


async def test_usage_period_cannot_overspend_allowance(session: AsyncSession) -> None:
    u = await _user(session)
    session.add(Plan(code="pro", monthly_audit_allowance=40))
    await session.flush()
    session.add(
        Subscription(
            id="sub_1",
            user_id=u.id,
            plan_code="pro",
            status=SubStatus.active,
            price_id="price_1",
            current_period_start=NOW,
            current_period_end=NOW + timedelta(days=30),
            stripe_seen_at=NOW,
        )
    )
    await session.flush()
    session.add(
        UsagePeriod(
            user_id=u.id,
            subscription_id="sub_1",
            source_invoice_id="in_1",
            period_start=NOW,
            period_end=NOW + timedelta(days=30),
            allowance=2,
            used=3,
        )
    )
    with pytest.raises(IntegrityError, match="used_within_allowance"):
        await session.flush()


async def test_only_one_live_subscription_per_user(session: AsyncSession) -> None:
    u = await _user(session)
    session.add(Plan(code="pro", monthly_audit_allowance=40))
    await session.flush()
    for sub_id in ("sub_a", "sub_b"):
        session.add(
            Subscription(
                id=sub_id,
                user_id=u.id,
                plan_code="pro",
                status=SubStatus.active,
                price_id="price_1",
                current_period_start=NOW,
                current_period_end=NOW + timedelta(days=30),
                stripe_seen_at=NOW,
            )
        )
    with pytest.raises(IntegrityError, match="uq_subscription_one_live_per_user"):
        await session.flush()


async def test_audit_event_percentage_range(session: AsyncSession) -> None:
    u = await _user(session)
    ls = await _listing(session)
    a = _audit(u.id, ls.otodom_id)
    session.add(a)
    await session.flush()
    session.add(AuditEvent(audit_id=a.id, kind="progress", stage="fetch", pct=101))
    with pytest.raises(IntegrityError, match="pct_range"):
        await session.flush()


# GDPR[erasure]: deleting the user removes every tenant-owned row in one statement.
async def test_deleting_a_user_cascades_to_all_tenant_data(session: AsyncSession) -> None:
    u = await _user(session)
    ls = await _listing(session)
    a = _audit(u.id, ls.otodom_id)
    session.add_all(
        [
            a,
            AuthIdentity(user_id=u.id, provider="email", subject=u.email),
            UserSession(token_hash=uuid4().hex + uuid4().hex, user_id=u.id, expires_at=NOW),
            CreditAccount(user_id=u.id, balance=3),
            CreditLedger(
                user_id=u.id, delta=3, reason=CreditReason.signup_grant, idempotency_key=f"signup:{u.id}"
            ),
        ]
    )
    await session.flush()
    session.add(AuditEvent(audit_id=a.id, kind="progress", stage="fetch", pct=5))
    session.add(
        CreditLedger(
            user_id=u.id,
            delta=-1,
            reason=CreditReason.reserve,
            idempotency_key=f"reserve:{a.id}",
            audit_id=a.id,
        )
    )
    await session.flush()

    await session.execute(text("DELETE FROM app.app_user WHERE id = :id"), {"id": u.id})

    for table in ("auth_identity", "user_session", "credit_account", "credit_ledger", "audit"):
        count = await session.scalar(
            select(func.count())
            .select_from(text(f"app.{table}"))
            .where(text("user_id = :id"))
            .params(id=u.id)
        )
        assert count == 0, table
    assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0
