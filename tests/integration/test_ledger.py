"""Ledger, quota and entitlements on real Postgres (blueprint §3, §4.6): races, idempotency and the
ledger-sum rule."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from rm_core.db.models import (
    Audit,
    AuditStatus,
    ChargeSource,
    ChargeState,
    CreditAccount,
    Listing,
    Plan,
    Subscription,
    SubStatus,
    UsagePeriod,
    User,
)
from rm_core.entitlements import has_pro, load_entitlements
from rm_core.ledger import (
    FEATURE_COST,
    UnknownFeatureError,
    admin_adjust,
    ensure_credit_account,
    ledger_mismatches,
    lock_owner,
    record_reservation,
    reserve,
    settle,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = [pytest.mark.integration, pytest.mark.money]
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


@pytest.fixture
def sm(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def user(engine: AsyncEngine, sm: async_sessionmaker[AsyncSession]) -> AsyncIterator[str]:
    uid = str(uuid4())
    oid = "IDLEDGER"
    async with sm() as s, s.begin():
        s.add(User(id=uid, email=f"{uid}@example.test"))
        if await s.get(Listing, oid) is None:
            s.add(Listing(otodom_id=oid, url="https://x.test"))
    yield uid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.app_user WHERE id = :u"), {"u": uid})


async def _balance(sm: async_sessionmaker[AsyncSession], uid: str) -> int:
    async with sm() as s:
        return await s.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == uid)) or 0


async def _ledger_sum(sm: async_sessionmaker[AsyncSession], uid: str) -> int:
    async with sm() as s:
        return int(
            await s.scalar(
                text("SELECT coalesce(sum(delta), 0) FROM app.credit_ledger WHERE user_id = :u"), {"u": uid}
            )
            or 0
        )


async def submit(
    sm: async_sessionmaker[AsyncSession], uid: str, *, feature: str = "deal_audit", oid: str = "IDLEDGER"
) -> UUID | None:
    """The API's submit transaction: entitlement, reserve, audit row, ledger row. Returns the audit id
    or None (402)."""
    audit_id = uuid4()
    try:
        return await _submit_tx(sm, uid, feature, oid, audit_id)
    except IntegrityError as exc:
        if "uq_audit_one_active_per_listing" not in str(exc):
            raise
        return None  # the API answers 409 AUDIT_IN_PROGRESS; the reservation rolled back with the transaction


async def _submit_tx(
    sm: async_sessionmaker[AsyncSession], uid: str, feature: str, oid: str, audit_id: UUID
) -> UUID | None:
    async with sm() as s, s.begin():
        ent = await load_entitlements(s, uid)
        res = await reserve(s, uid, feature, ent, audit_id=audit_id)
        if res is None:
            return None
        s.add(
            Audit(
                id=audit_id,
                user_id=uid,
                otodom_id=oid,
                status=AuditStatus.queued,
                charge_source=res.source,
                charge_state=ChargeState.reserved,
                usage_period_id=res.usage_period_id,
                analyst=feature == "deal_audit_analyst",
                engine_version="t",
                schema_version=1,
            )
        )
        await s.flush()
        await record_reservation(s, res, uid)
    return audit_id


async def _finish(sm: async_sessionmaker[AsyncSession], audit_id: UUID, *, capture: bool) -> bool:
    async with sm() as s, s.begin():
        await lock_owner(s, audit_id)  # the owner's credit lock comes before the audit row (fixed lock order)
        # a terminal status is needed before a second audit for the same listing can be queued
        await s.execute(text("UPDATE app.audit SET status = 'succeeded' WHERE id = :a"), {"a": audit_id})
        return await settle(s, audit_id, capture=capture)


async def _grant_signup(sm: async_sessionmaker[AsyncSession], uid: str, credits: int = 3) -> bool:
    async with sm() as s, s.begin():
        return await ensure_credit_account(s, uid, verified=True, signup_credits=credits)


# ---- signup grant ----
async def test_signup_credits_are_granted_exactly_once_even_in_parallel(sm, user: str) -> None:
    results = await asyncio.gather(*(_grant_signup(sm, user) for _ in range(10)))
    assert results.count(True) == 1
    assert await _balance(sm, user) == 3
    assert await _ledger_sum(sm, user) == 3


async def test_unverified_users_get_an_account_but_no_credits_until_verified(sm, user: str) -> None:
    async with sm() as s, s.begin():
        assert await ensure_credit_account(s, user, verified=False, signup_credits=3) is False
    assert await _balance(sm, user) == 0
    assert await _grant_signup(sm, user) is True
    assert await _balance(sm, user) == 3


# ---- the quota race ----
async def test_quota_race_ten_concurrent_submits_with_three_credits(
    engine: AsyncEngine, sm, user: str
) -> None:
    await _grant_signup(sm, user, 3)
    async with (
        engine.begin() as conn
    ):  # ten different listings, so the one-active-audit-per-listing rule is not the limiter
        for i in range(10):
            await conn.execute(
                text(
                    "INSERT INTO app.listing (otodom_id, url) VALUES (:o, 'https://x.test') "
                    "ON CONFLICT DO NOTHING"
                ),
                {"o": f"IDRACE{i}"},
            )
    results = await asyncio.gather(*(submit(sm, user, oid=f"IDRACE{i}") for i in range(10)))
    try:
        assert sum(r is not None for r in results) == 3
        assert sum(r is None for r in results) == 7  # the API answers 402 QUOTA_EXHAUSTED
        assert await _balance(sm, user) == 0
        assert await _ledger_sum(sm, user) == 0  # +3 signup, -3 reserved: SUM(delta) equals the balance
        async with sm() as s:
            assert await ledger_mismatches(s) == []
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.credit_ledger WHERE user_id = :u"), {"u": user})
            await conn.execute(text("DELETE FROM app.audit WHERE user_id = :u"), {"u": user})
            await conn.execute(text("DELETE FROM app.listing WHERE otodom_id LIKE 'IDRACE%'"))


async def test_a_user_with_no_account_cannot_reserve(sm, user: str) -> None:
    assert await submit(sm, user) is None


# ---- settle ----
async def test_a_failed_audit_releases_its_credit_and_leaves_reserve_and_release_rows(sm, user: str) -> None:
    await _grant_signup(sm, user, 3)
    audit_id = await submit(sm, user)
    assert audit_id is not None
    assert await _balance(sm, user) == 2
    assert await _finish(sm, audit_id, capture=False) is True
    assert await _balance(sm, user) == 3
    async with sm() as s:
        rows = (
            await s.execute(
                text("SELECT reason, delta FROM app.credit_ledger WHERE audit_id = :a ORDER BY id"),
                {"a": audit_id},
            )
        ).all()
    assert [(r[0], r[1]) for r in rows] == [("reserve", -1), ("release", 1)]
    assert await _ledger_sum(sm, user) == await _balance(sm, user)


async def test_a_successful_audit_keeps_the_charge(sm, user: str) -> None:
    await _grant_signup(sm, user, 3)
    audit_id = await submit(sm, user)
    assert audit_id is not None
    assert await _finish(sm, audit_id, capture=True) is True
    assert await _balance(sm, user) == 2


async def test_settling_twice_or_in_parallel_changes_the_balance_once(sm, user: str) -> None:
    await _grant_signup(sm, user, 3)
    audit_id = await submit(sm, user)
    assert audit_id is not None
    results = await asyncio.gather(*(_finish(sm, audit_id, capture=False) for _ in range(8)))
    assert results.count(True) == 1
    assert await _balance(sm, user) == 3  # released once, not eight times
    assert await _finish(sm, audit_id, capture=True) is False  # a captured-after-released flip is refused
    assert await _balance(sm, user) == 3
    assert await _ledger_sum(sm, user) == 3


async def test_the_analyst_audit_costs_two_and_releases_two(sm, user: str) -> None:
    await _grant_signup(sm, user, 3)
    audit_id = await submit(sm, user, feature="deal_audit_analyst")
    assert audit_id is not None
    assert await _balance(sm, user) == 1
    await _finish(sm, audit_id, capture=False)
    assert await _balance(sm, user) == 3
    assert await submit(sm, user, feature="deal_audit_analyst", oid="IDLEDGER") is not None
    assert await _balance(sm, user) == 1


async def test_unknown_features_are_refused_not_charged_zero(sm, user: str) -> None:
    await _grant_signup(sm, user)
    with pytest.raises(UnknownFeatureError):
        await submit(sm, user, feature="free_lunch")
    assert FEATURE_COST["deal_audit"] == 1


# ---- plan allowance first, then credits ----
async def _give_pro(
    sm: async_sessionmaker[AsyncSession], uid: str, *, allowance: int, kind: str = "subscription"
) -> int:
    async with sm() as s, s.begin():
        if await s.get(Plan, "pro") is None:
            s.add(Plan(code="pro", monthly_audit_allowance=40))
            await s.flush()
        now = await s.scalar(select(func.clock_timestamp()))
        assert now is not None
        sub_id = None
        if kind == "subscription":
            sub_id = f"sub_{uuid4().hex[:12]}"
            s.add(
                Subscription(
                    id=sub_id,
                    user_id=uid,
                    plan_code="pro",
                    status=SubStatus.active,
                    price_id="price_1",
                    current_period_start=now - timedelta(days=1),
                    current_period_end=now + timedelta(days=29),
                    stripe_seen_at=now,
                )
            )
            await s.flush()
        period = UsagePeriod(
            user_id=uid,
            kind=kind,
            subscription_id=sub_id,
            source_invoice_id=f"in_{uuid4().hex[:12]}",
            period_start=now - timedelta(days=1),
            period_end=now + timedelta(days=29),
            allowance=allowance,
        )
        s.add(period)
        await s.flush()
        return period.id


async def test_pro_spends_the_allowance_first_then_falls_back_to_credits(sm, user: str) -> None:
    await _grant_signup(sm, user, 3)
    period_id = await _give_pro(sm, user, allowance=2)
    first, second, third = (
        [await submit(sm, user, oid=f"IDPLAN{i}") for i in range(3)] if await _make_listings(sm, 3) else []
    )
    assert first is not None
    assert second is not None
    assert third is not None
    async with sm() as s:
        period = await s.get(UsagePeriod, period_id)
        assert period is not None
        assert period.used == 2  # the first two came from the plan
        sources = (
            (
                await s.execute(
                    select(Audit.charge_source).where(Audit.user_id == user).order_by(Audit.created_at)
                )
            )
            .scalars()
            .all()
        )
    assert sources == [ChargeSource.plan, ChargeSource.plan, ChargeSource.credit]
    assert await _balance(sm, user) == 2  # only the third audit touched the credits
    await _finish(
        sm, first, capture=False
    )  # releasing a plan charge returns it to the allowance, not to credits
    async with sm() as s:
        period = await s.get(UsagePeriod, period_id)
        assert period is not None
        assert period.used == 1
    assert await _balance(sm, user) == 2
    assert await _ledger_sum(sm, user) == await _balance(sm, user)


async def _make_listings(sm: async_sessionmaker[AsyncSession], n: int) -> bool:
    async with sm() as s, s.begin():
        for i in range(n):
            if await s.get(Listing, f"IDPLAN{i}") is None:
                s.add(Listing(otodom_id=f"IDPLAN{i}", url="https://x.test"))
    return True


async def test_a_free_user_never_touches_a_stale_period(sm, user: str) -> None:
    await _grant_signup(sm, user, 1)
    async with sm() as s:
        ent = await load_entitlements(s, user)
    assert not ent.is_pro
    assert ent.period is None
    assert ent.credit_balance == 1


async def test_concurrent_submits_never_overspend_a_plan_allowance(
    engine: AsyncEngine, sm, user: str
) -> None:
    period_id = await _give_pro(sm, user, allowance=4)
    await _grant_signup(sm, user, 0)
    async with engine.begin() as conn:
        for i in range(12):
            await conn.execute(
                text(
                    "INSERT INTO app.listing (otodom_id, url) VALUES (:o, 'https://x.test') "
                    "ON CONFLICT DO NOTHING"
                ),
                {"o": f"IDPQ{i}"},
            )
    results = await asyncio.gather(*(submit(sm, user, oid=f"IDPQ{i}") for i in range(12)))
    try:
        assert sum(r is not None for r in results) == 4
        async with sm() as s:
            period = await s.get(UsagePeriod, period_id)
            assert period is not None
            assert period.used == 4
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.credit_ledger WHERE user_id = :u"), {"u": user})
            await conn.execute(text("DELETE FROM app.audit WHERE user_id = :u"), {"u": user})
            await conn.execute(
                text("DELETE FROM app.listing WHERE otodom_id LIKE 'IDPQ%' OR otodom_id LIKE 'IDPLAN%'")
            )


# ---- a paid pass ----
async def test_a_pass_period_grants_pro_without_a_subscription(sm, user: str) -> None:
    await _give_pro(sm, user, allowance=40, kind="pass")
    async with sm() as s:
        ent = await load_entitlements(s, user)
    assert ent.is_pro
    assert ent.plan_code == "pro"
    assert ent.subscription_status is None
    assert ent.period is not None
    assert ent.period.kind == "pass"
    assert ent.period.remaining == 40


# ---- admin ----
async def test_admin_adjustments_are_idempotent_and_cannot_go_negative(sm, user: str) -> None:
    async with sm() as s, s.begin():
        assert await admin_adjust(s, user, 5, key="k1", note="goodwill") is True
        assert await admin_adjust(s, user, 5, key="k1", note="goodwill") is False  # replay
    assert await _balance(sm, user) == 5
    with pytest.raises(Exception, match="non_negative"):
        async with sm() as s, s.begin():
            await admin_adjust(s, user, -9, key="k2", note="too much")
    assert await _balance(sm, user) == 5  # the failed adjustment rolled back with its ledger row
    assert await _ledger_sum(sm, user) == 5


# ---- the ledger sum rule ----
async def test_the_nightly_check_finds_a_tampered_balance(sm, user: str, engine: AsyncEngine) -> None:
    await _grant_signup(sm, user, 3)
    async with sm() as s:
        assert user not in await ledger_mismatches(s)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE app.credit_account SET balance = balance + 1 WHERE user_id = :u"), {"u": user}
        )
    async with sm() as s:
        assert user in await ledger_mismatches(s)


@pytest.mark.parametrize("seed", range(6))
async def test_random_operation_sequences_keep_the_balance_equal_to_the_ledger(
    sm, user: str, seed: int
) -> None:
    import random  # noqa: PLC0415

    rng = random.Random(seed)  # noqa: S311
    await _grant_signup(sm, user, 4)
    await _make_listings(sm, 8)
    open_audits: list[UUID] = []
    for step in range(25):
        action = rng.choice(["submit", "capture", "release", "admin"])
        if action == "submit":
            audit = await submit(sm, user, oid=f"IDPLAN{rng.randrange(8)}")
            if audit is not None:
                open_audits.append(audit)
        elif action in {"capture", "release"} and open_audits:
            await _finish(sm, open_audits.pop(rng.randrange(len(open_audits))), capture=action == "capture")
        elif action == "admin":
            async with sm() as s, s.begin():
                await admin_adjust(s, user, rng.randint(1, 3), key=f"{seed}-{step}", note="t")
        assert await _balance(sm, user) >= 0
        assert await _ledger_sum(sm, user) == await _balance(sm, user)
    async with sm() as s, s.begin():
        await s.execute(text("DELETE FROM app.credit_ledger WHERE user_id = :u"), {"u": user})
        await s.execute(text("DELETE FROM app.audit WHERE user_id = :u"), {"u": user})
        await s.execute(text("DELETE FROM app.listing WHERE otodom_id LIKE 'IDPLAN%'"))


# ---- has_pro (pure) ----
def _sub(status: SubStatus, *, ends: datetime, grace: datetime | None = None) -> Subscription:
    return Subscription(
        id="sub_1",
        user_id="u",
        plan_code="pro",
        status=status,
        price_id="p",
        current_period_start=ends - timedelta(days=30),
        current_period_end=ends,
        grace_until=grace,
        stripe_seen_at=NOW,
    )


def test_has_pro_for_each_state() -> None:
    assert has_pro(None, NOW) is False
    assert has_pro(_sub(SubStatus.active, ends=NOW + timedelta(days=3)), NOW)
    assert has_pro(_sub(SubStatus.trialing, ends=NOW + timedelta(days=3)), NOW)
    for dead in (
        SubStatus.canceled,
        SubStatus.unpaid,
        SubStatus.incomplete,
        SubStatus.incomplete_expired,
        SubStatus.paused,
    ):
        assert has_pro(_sub(dead, ends=NOW + timedelta(days=3)), NOW) is False


def test_has_pro_fails_closed_48_hours_after_the_period_end() -> None:
    ends = NOW - timedelta(hours=47, minutes=59)
    assert has_pro(_sub(SubStatus.active, ends=ends), NOW) is True  # renewal still in flight
    assert (
        has_pro(_sub(SubStatus.active, ends=NOW - timedelta(hours=48)), NOW) is False
    )  # exactly at the limit: closed
    assert has_pro(_sub(SubStatus.active, ends=NOW - timedelta(days=5)), NOW) is False


def test_grace_period_is_pro_until_grace_until_and_free_one_second_after() -> None:
    grace = NOW + timedelta(days=7)
    sub = _sub(SubStatus.past_due, ends=NOW - timedelta(days=1), grace=grace)
    assert has_pro(sub, NOW) is True
    assert has_pro(sub, grace - timedelta(seconds=1)) is True
    assert has_pro(sub, grace + timedelta(seconds=1)) is False
    assert has_pro(_sub(SubStatus.past_due, ends=NOW, grace=None), NOW) is False


async def test_entitlements_follow_the_subscription_with_an_explicit_clock(sm, user: str) -> None:
    async with sm() as s, s.begin():
        s.add(Plan(code="pro", monthly_audit_allowance=40)) if await s.get(Plan, "pro") is None else None
        await s.flush()
        s.add(
            _sub(SubStatus.active, ends=NOW + timedelta(days=2)).__class__(
                id=f"sub_{uuid4().hex[:12]}",
                user_id=user,
                plan_code="pro",
                status=SubStatus.active,
                price_id="p",
                current_period_start=NOW - timedelta(days=28),
                current_period_end=NOW + timedelta(days=2),
                stripe_seen_at=NOW,
            )
        )
    async with sm() as s:
        assert (await load_entitlements(s, user, now=NOW)).is_pro
        assert (await load_entitlements(s, user, now=NOW + timedelta(days=2, hours=47))).is_pro
        assert not (await load_entitlements(s, user, now=NOW + timedelta(days=2, hours=48))).is_pro
