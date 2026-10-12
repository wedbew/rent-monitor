"""Feature flags (blueprint §3). First match wins: unexpired user override, plan below `min_plan`
(off), rollout bucket, default.

Tagged legal features keep a flag so counsel can switch one off without a deploy (LEGAL tags,
`rm_core.legal`).
"""

import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import FeatureFlag, FeatureOverride
from rm_core.entitlements import PlanCode, db_now

_RANK: dict[str, int] = {"free": 0, "pro": 1}


def rollout_bucket(user_id: str, key: str) -> int:
    """Stable 0-99 bucket per (user, flag): the same user always lands in the same bucket for a flag."""
    return int(hashlib.sha256(f"{user_id}{key}".encode()).hexdigest(), 16) % 100


def decide(
    flag: FeatureFlag | None,
    override: FeatureOverride | None,
    *,
    user_id: str,
    plan: PlanCode,
    now: datetime,
) -> bool:
    """The pure resolution rule. An unknown flag is off (fail closed)."""
    if flag is None:
        return False
    if override is not None and (override.expires_at is None or override.expires_at > now):
        return override.enabled
    if flag.min_plan is not None and _RANK.get(plan, 0) < _RANK.get(flag.min_plan, 99):
        return False
    if flag.rollout_pct > 0 and rollout_bucket(user_id, flag.key) < flag.rollout_pct:
        return True
    return flag.enabled_default


async def flag_enabled(
    session: AsyncSession, key: str, *, user_id: str, plan: PlanCode, now: datetime | None = None
) -> bool:
    moment = now or await db_now(session)
    flag = await session.get(FeatureFlag, key)
    override = await session.scalar(
        select(FeatureOverride).where(FeatureOverride.flag_key == key, FeatureOverride.user_id == user_id)
    )
    return decide(flag, override, user_id=user_id, plan=plan, now=moment)


async def resolve_flags(
    session: AsyncSession, *, user_id: str, plan: PlanCode, now: datetime | None = None
) -> dict[str, bool]:
    """Every flag for one user (for /api/me)."""
    moment = now or await db_now(session)
    flags = (await session.scalars(select(FeatureFlag))).all()
    overrides = {
        o.flag_key: o
        for o in (
            await session.scalars(select(FeatureOverride).where(FeatureOverride.user_id == user_id))
        ).all()
    }
    return {f.key: decide(f, overrides.get(f.key), user_id=user_id, plan=plan, now=moment) for f in flags}
