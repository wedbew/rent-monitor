"""Report credit lots and allocations (docs/PADDLE-INTEGRATION.md section 4, slice 2): provenance of units
that never becomes a second balance authority. Real Postgres, concurrency and a property test."""

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from rm_core.db.models import (
    Audit,
    AuditStatus,
    ChargeState,
    CreditAccount,
    Listing,
    ReportCreditAllocation,
    ReportCreditLot,
    User,
)
from rm_core.entitlements import load_entitlements
from rm_core.ledger import (
    admin_adjust,
    ensure_credit_account,
    ledger_mismatches,
    lock_owner,
    lot_mismatches,
    record_reservation,
    reserve,
    settle,
)
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

pytestmark = [pytest.mark.integration, pytest.mark.money]


@pytest.fixture
def sm(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def user(engine: AsyncEngine, sm: async_sessionmaker[AsyncSession]) -> AsyncIterator[str]:
    uid = str(uuid4())
    async with sm() as s, s.begin():
        s.add(User(id=uid, email=f"{uid}@example.test"))
    yield uid
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app.app_user WHERE id = :u"), {"u": uid})
        await conn.execute(text("DELETE FROM app.listing WHERE otodom_id LIKE 'IDLOT%'"))


async def grant_signup(sm: async_sessionmaker[AsyncSession], uid: str, n: int) -> None:
    async with sm() as s, s.begin():
        await ensure_credit_account(s, uid, verified=True, signup_credits=n)


async def grant_admin(sm: async_sessionmaker[AsyncSession], uid: str, delta: int, key: str) -> None:
    async with sm() as s, s.begin():
        await admin_adjust(s, uid, delta, key=key, note="test")


async def submit(sm: async_sessionmaker[AsyncSession], uid: str, feature: str = "deal_audit") -> UUID | None:
    """The API's submit transaction on a fresh listing."""
    audit_id, oid = uuid4(), f"IDLOT{uuid4().hex[:8].upper()}"
    async with sm() as s, s.begin():
        s.add(Listing(otodom_id=oid, url="https://x.test"))
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


async def finish(sm: async_sessionmaker[AsyncSession], audit_id: UUID, *, capture: bool) -> bool:
    async with sm() as s, s.begin():
        await lock_owner(s, audit_id)
        await s.execute(update(Audit).where(Audit.id == audit_id).values(status=AuditStatus.succeeded))
        return await settle(s, audit_id, capture=capture)


async def lots(sm: async_sessionmaker[AsyncSession], uid: str) -> list[ReportCreditLot]:
    async with sm() as s:
        return list(
            (
                await s.scalars(
                    select(ReportCreditLot)
                    .where(ReportCreditLot.user_id == uid)
                    .order_by(ReportCreditLot.created_at, ReportCreditLot.id)
                )
            ).all()
        )


async def assert_consistent(sm: async_sessionmaker[AsyncSession], uid: str) -> None:
    """The invariants of the provenance layer, after any operation."""
    async with sm() as s:
        balance = await s.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == uid)) or 0
        ledger = await s.scalar(
            text("SELECT coalesce(sum(delta), 0) FROM app.credit_ledger WHERE user_id = :u"), {"u": uid}
        )
        assert balance == ledger >= 0
        assert await ledger_mismatches(s) == []
        assert await lot_mismatches(s) == []
        rows = (await s.scalars(select(ReportCreditLot).where(ReportCreditLot.user_id == uid))).all()
        assert sum(lot.available for lot in rows) == balance
        for lot in rows:
            assert lot.granted == lot.available + lot.reserved + lot.consumed + lot.revoked
            held = await s.scalar(
                select(func.coalesce(func.sum(ReportCreditAllocation.units), 0)).where(
                    ReportCreditAllocation.lot_id == lot.id, ReportCreditAllocation.state == "reserved"
                )
            )
            assert held == lot.reserved


# ------------------------------------------------------------------------------ grants
async def test_signup_and_admin_grants_create_one_lot_each_keyed_like_the_ledger(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 3)
    await grant_admin(sm, user, 2, "bonus")
    await grant_signup(sm, user, 3)  # a repeated grant is a no-op: no second lot
    a, b = await lots(sm, user)
    assert (a.source, a.granted, a.available, a.grant_key) == ("signup", 3, 3, f"signup:{user}")
    assert (b.source, b.granted, b.available, b.grant_key) == ("admin", 2, 2, "admin:bonus")
    await assert_consistent(sm, user)


async def test_a_negative_adjustment_revokes_from_the_oldest_lots(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 3)
    await grant_admin(sm, user, 2, "bonus")
    await grant_admin(sm, user, -4, "correction")
    a, b = await lots(sm, user)
    assert (a.available, a.revoked, b.available, b.revoked) == (0, 3, 1, 1)
    await assert_consistent(sm, user)


# ------------------------------------------------------------------------------ reserve, capture, release
async def test_reserve_spends_oldest_first_across_lots_and_release_returns_to_the_same_lots(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 3)
    await grant_admin(sm, user, 2, "bonus")
    first = await submit(sm, user)  # 1 unit from the signup lot -> 2 left there
    spanning = await submit(sm, user, "deal_audit_analyst")  # 2 units: both from the signup lot
    third = await submit(sm, user, "deal_audit_analyst")  # signup lot empty: 2 from the admin lot
    assert None not in (first, spanning, third)
    signup, admin = await lots(sm, user)
    assert (signup.available, signup.reserved, admin.available, admin.reserved) == (0, 3, 0, 2)
    await assert_consistent(sm, user)

    assert await finish(sm, third, capture=False)  # type: ignore[arg-type]
    signup, admin = await lots(sm, user)
    assert (admin.available, admin.reserved) == (2, 0)  # back on the lot it came from, no new lot
    assert len(await lots(sm, user)) == 2
    assert await finish(sm, spanning, capture=True)  # type: ignore[arg-type]
    signup, admin = await lots(sm, user)
    assert (signup.reserved, signup.consumed) == (1, 2)
    await assert_consistent(sm, user)


async def test_settling_twice_changes_nothing_the_second_time(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 1)
    audit = await submit(sm, user)
    assert audit is not None
    assert await finish(sm, audit, capture=False) is True
    snapshot = [(x.available, x.reserved, x.consumed) for x in await lots(sm, user)]
    assert await finish(sm, audit, capture=False) is False
    assert await finish(sm, audit, capture=True) is False  # a late capture cannot undo a release
    assert [(x.available, x.reserved, x.consumed) for x in await lots(sm, user)] == snapshot
    await assert_consistent(sm, user)


async def test_a_frozen_lot_counts_in_the_balance_but_cannot_be_spent(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 2)
    await grant_admin(sm, user, 1, "extra")
    async with sm() as s, s.begin():
        await s.execute(
            update(ReportCreditLot).where(ReportCreditLot.grant_key == f"signup:{user}").values(frozen=True)
        )
    assert await submit(sm, user) is not None  # the unfrozen admin lot pays
    assert await submit(sm, user) is None  # 2 units remain, but both are frozen: quota exhausted
    signup, admin = await lots(sm, user)
    assert (signup.available, signup.frozen, admin.reserved) == (2, True, 1)
    await assert_consistent(sm, user)


# ------------------------------------------------------------------------------ healing
async def test_units_no_lot_explains_get_an_explicit_migration_lot(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 1)
    async with sm() as s, s.begin():  # a balance edited outside the service, as old rows and some tests do
        await s.execute(update(CreditAccount).where(CreditAccount.user_id == user).values(balance=3))
        await s.execute(
            text(
                "INSERT INTO app.credit_ledger (user_id, delta, reason, idempotency_key)"
                " VALUES (:u, 2, 'topup', :k)"
            ),
            {"u": user, "k": f"manual:{user}"},
        )
    assert await submit(sm, user) is not None
    rows = await lots(sm, user)
    assert [r.source for r in rows] == ["signup", "migration"]
    assert rows[1].granted == 2
    assert rows[1].grant_key.startswith("heal:")
    await assert_consistent(sm, user)


async def test_an_audit_without_allocations_is_healed_when_it_is_released(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 1)
    async with sm() as s, s.begin():
        s.add(Listing(otodom_id="IDLOTLEGACY", url="https://x.test"))
        await s.flush()
        audit = Audit(
            id=uuid4(),
            user_id=user,
            otodom_id="IDLOTLEGACY",
            status=AuditStatus.running,
            charge_source="credit",
            charge_state=ChargeState.reserved,
            engine_version="t",
            schema_version=1,
        )
        s.add(audit)
    assert await finish(sm, audit.id, capture=False)
    assert "migration" in [r.source for r in await lots(sm, user)]


# ------------------------------------------------------------------------------ concurrency
async def test_ten_racing_reservations_for_two_units_admit_exactly_two(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 2)
    results = await asyncio.gather(*(submit(sm, user) for _ in range(10)))
    assert sum(r is not None for r in results) == 2
    (lot,) = await lots(sm, user)
    assert (lot.available, lot.reserved) == (0, 2)
    await assert_consistent(sm, user)


async def test_capture_and_release_racing_on_one_audit_settle_it_once(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 2)
    for _ in range(2):
        audit = await submit(sm, user)
        assert audit is not None
        outcomes = await asyncio.gather(
            finish(sm, audit, capture=True), finish(sm, audit, capture=False), finish(sm, audit, capture=True)
        )
        assert outcomes.count(True) == 1
        await assert_consistent(sm, user)


async def test_reservations_and_settlements_for_one_user_never_deadlock(
    sm: async_sessionmaker[AsyncSession], user: str
) -> None:
    await grant_signup(sm, user, 8)
    queued = [a for a in await asyncio.gather(*(submit(sm, user) for _ in range(4))) if a is not None]
    work = [finish(sm, a, capture=i % 2 == 0) for i, a in enumerate(queued)]
    work += [submit(sm, user) for _ in range(4)]
    await asyncio.wait_for(asyncio.gather(*work), 30)  # a lock-order inversion would raise or hang here
    await assert_consistent(sm, user)


# ------------------------------------------------------------------------------ properties
OPERATIONS = st.one_of(
    st.tuples(st.just("grant"), st.integers(1, 5)),
    st.tuples(st.just("remove"), st.integers(1, 4)),
    st.tuples(st.just("reserve"), st.sampled_from(["deal_audit", "deal_audit_analyst"])),
    st.tuples(st.just("capture"), st.integers(0, 9)),
    st.tuples(st.just("release"), st.integers(0, 9)),
    st.tuples(st.just("freeze"), st.integers(0, 3)),
    st.tuples(st.just("unfreeze"), st.integers(0, 3)),
)


async def run_sequence(url: str, ops: list[tuple[str, int | str]]) -> None:
    engine = create_async_engine(url, pool_size=3)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    uid = str(uuid4())
    open_audits: list[UUID] = []
    grants = 0
    try:
        async with sm() as s, s.begin():
            s.add(User(id=uid, email=f"{uid}@example.test"))
            await ensure_credit_account(s, uid, verified=False, signup_credits=0)
        for kind, arg in ops:
            if kind == "grant":
                grants += 1
                await grant_admin(sm, uid, int(arg), f"g{grants}")
            elif kind == "remove":
                async with sm() as s:
                    balance = (
                        await s.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == uid)) or 0
                    )
                if balance >= int(arg):  # the CHECK forbids a negative balance; the service is not asked to
                    grants += 1
                    await grant_admin(sm, uid, -int(arg), f"r{grants}")
            elif kind == "reserve":
                audit = await submit(sm, uid, str(arg))
                if audit is not None:
                    open_audits.append(audit)
            elif kind in {"capture", "release"} and open_audits:
                audit = open_audits.pop(int(arg) % len(open_audits))
                assert await finish(sm, audit, capture=kind == "capture")
            elif kind in {"freeze", "unfreeze"}:
                rows = await lots(sm, uid)
                if rows:
                    async with sm() as s, s.begin():
                        await s.execute(
                            update(ReportCreditLot)
                            .where(ReportCreditLot.id == rows[int(arg) % len(rows)].id)
                            .values(frozen=kind == "freeze")
                        )
            await assert_consistent(sm, uid)
        for audit in open_audits:  # everything still held can be released again
            assert await finish(sm, audit, capture=False)
        await assert_consistent(sm, uid)
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM app.app_user WHERE id = :u"), {"u": uid})
            await conn.execute(text("DELETE FROM app.listing WHERE otodom_id LIKE 'IDLOT%'"))
        await engine.dispose()


def test_pack_ledger_properties(migrated_url: str) -> None:
    """Any order of grants, removals, reservations, captures, releases and freezes keeps the ledger, the
    cached balance, the lots and the allocations in agreement."""

    @settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(st.lists(OPERATIONS, min_size=1, max_size=24))
    def check(ops: list[tuple[str, int | str]]) -> None:
        asyncio.run(run_sequence(migrated_url, ops))

    check()
