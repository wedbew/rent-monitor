"""Seeding is idempotent, respects operator changes and promotes the admin without demoting anyone."""

import pytest
from rm_core.db.models import FeatureFlag, Plan, User
from rm_core.seed import seed_all
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


async def _count(session: AsyncSession, model: type) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def test_seed_creates_plans_and_flags_and_is_idempotent(session: AsyncSession) -> None:
    await seed_all(session, pro_allowance=40)
    await seed_all(session, pro_allowance=40)
    plans = {p.code: p for p in (await session.scalars(select(Plan))).all()}
    assert plans["free"].monthly_audit_allowance == 0
    assert plans["pro"].monthly_audit_allowance == 40
    assert plans["pro"].features == {"screener": True}
    flags = {f.key: f for f in (await session.scalars(select(FeatureFlag))).all()}
    assert {"screener", "redesign", "analyst"} <= set(flags)
    assert flags["screener"].min_plan == "pro"
    assert flags["redesign"].enabled_default is False
    assert await _count(session, Plan) == 2


async def test_reseeding_updates_allowance_but_keeps_operator_flag_changes(session: AsyncSession) -> None:
    await seed_all(session, pro_allowance=40, stripe_price_id_pro="price_123")
    await session.execute(
        update(FeatureFlag).where(FeatureFlag.key == "redesign").values(enabled_default=True, rollout_pct=10)
    )
    await seed_all(session, pro_allowance=55)  # no price id: must not erase the stored one
    await session.flush()
    session.expire_all()
    pro = await session.get(Plan, "pro")
    flag = await session.get(FeatureFlag, "redesign")
    assert pro is not None
    assert pro.monthly_audit_allowance == 55
    assert pro.stripe_price_id == "price_123"
    assert flag is not None
    assert flag.enabled_default is True
    assert flag.rollout_pct == 10


async def test_admin_is_created_verified_then_promoted_without_duplicates(session: AsyncSession) -> None:
    await seed_all(session, pro_allowance=40, admin_email="  Admin@Example.TEST ")
    admin = await session.scalar(select(User).where(User.email == "admin@example.test"))
    assert admin is not None
    assert admin.role == "admin"
    assert admin.email_verified_at is not None

    other = User(email="member@example.test")
    session.add(other)
    await session.flush()
    await seed_all(session, pro_allowance=40, admin_email="member@example.test")
    await session.refresh(other)
    assert other.role == "admin"
    assert await _count(session, User) == 2
