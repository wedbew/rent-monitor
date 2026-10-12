"""Flags read from Postgres: seeded flags resolve per user, with overrides and the plan gate."""

from datetime import timedelta
from uuid import uuid4

import pytest
from rm_core.db.models import FeatureFlag, FeatureOverride, Plan, User
from rm_core.flags import flag_enabled, resolve_flags
from rm_core.seed import seed_all
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


async def _user(session: AsyncSession) -> str:
    uid = str(uuid4())
    session.add(User(id=uid, email=f"{uid}@example.test"))
    await session.flush()
    return uid


async def test_seeded_flags_resolve_by_plan(session: AsyncSession) -> None:
    await seed_all(session, pro_allowance=40)
    uid = await _user(session)
    assert await flag_enabled(session, "screener", user_id=uid, plan="free") is False  # min_plan pro
    assert (
        await flag_enabled(session, "screener", user_id=uid, plan="pro") is False
    )  # default off until enabled
    assert await flag_enabled(session, "nonexistent", user_id=uid, plan="pro") is False


async def test_an_override_enables_a_flag_for_one_user_until_it_expires(session: AsyncSession) -> None:
    await seed_all(session, pro_allowance=40)
    uid, other = await _user(session), await _user(session)
    session.add(
        FeatureOverride(flag_key="redesign", user_id=uid, enabled=True, reason="beta", created_by="admin")
    )
    await session.flush()
    assert await flag_enabled(session, "redesign", user_id=uid, plan="free") is True
    assert await flag_enabled(session, "redesign", user_id=other, plan="free") is False
    now = await session.scalar(select(__import__("sqlalchemy").func.clock_timestamp()))
    assert now is not None
    assert (
        await flag_enabled(session, "redesign", user_id=uid, plan="free", now=now + timedelta(days=1)) is True
    )


async def test_resolve_flags_returns_every_flag_for_the_user(session: AsyncSession) -> None:
    await seed_all(session, pro_allowance=40)
    uid = await _user(session)
    session.add(Plan(code="x", monthly_audit_allowance=0)) if await session.get(Plan, "x") is None else None
    session.add(
        FeatureOverride(flag_key="analyst", user_id=uid, enabled=True, reason="t", created_by="admin")
    )
    await session.flush()
    flags = await resolve_flags(session, user_id=uid, plan="free")
    assert {"screener", "redesign", "analyst"} <= set(flags)
    assert flags["analyst"] is True
    assert flags["screener"] is False
    count = len((await session.scalars(select(FeatureFlag))).all())
    assert len(flags) == count
