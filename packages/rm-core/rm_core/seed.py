"""Idempotent seed data: plans, feature flags and the admin role (blueprint §4.4 step 4).

Safe to run on every deploy: rows are upserted by key. It touches `stripe_price_id` only when one is given
and never demotes a user.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import FeatureFlag, Plan, User


@dataclass(frozen=True)
class SeedPlan:
    code: str
    monthly_audit_allowance: int
    features: dict[str, Any]


@dataclass(frozen=True)
class SeedFlag:
    key: str
    description: str
    enabled_default: bool = False
    min_plan: str | None = None


FLAGS = (
    SeedFlag("screener", "Discovery runs and approval queue (Pro)", min_plan="pro"),
    SeedFlag("redesign", "Interior redesign playground (reserved, off)"),
    SeedFlag("analyst", "Text-LLM analyst audit (reserved, off)"),
)


def plans(pro_allowance: int) -> tuple[SeedPlan, ...]:
    return (
        SeedPlan("free", 0, {"screener": False}),
        SeedPlan("pro", pro_allowance, {"screener": True}),
    )


async def seed_all(
    session: AsyncSession,
    *,
    pro_allowance: int,
    stripe_price_id_pro: str | None = None,
    admin_email: str | None = None,
) -> None:
    """Upsert plans and flags; promote `admin_email` (creating a verified user if missing)."""
    for p in plans(pro_allowance):
        stmt = insert(Plan).values(
            code=p.code,
            monthly_audit_allowance=p.monthly_audit_allowance,
            features=p.features,
            active=True,
            stripe_price_id=stripe_price_id_pro if p.code == "pro" else None,
        )
        update_cols: dict[str, Any] = {
            "monthly_audit_allowance": stmt.excluded.monthly_audit_allowance,
            "features": stmt.excluded.features,
            "active": True,
        }
        if p.code == "pro" and stripe_price_id_pro:
            update_cols["stripe_price_id"] = stmt.excluded.stripe_price_id
        await session.execute(stmt.on_conflict_do_update(index_elements=[Plan.code], set_=update_cols))
    for f in FLAGS:
        flag_stmt = insert(FeatureFlag).values(
            key=f.key, description=f.description, enabled_default=f.enabled_default, min_plan=f.min_plan
        )
        # Never overwrite a flag an operator already changed; only fill in missing descriptions.
        await session.execute(
            flag_stmt.on_conflict_do_update(
                index_elements=[FeatureFlag.key], set_={"description": flag_stmt.excluded.description}
            )
        )
    if admin_email:
        email = admin_email.strip().lower()
        user_stmt = insert(User).values(email=email, role="admin", email_verified_at=datetime.now(UTC))
        await session.execute(user_stmt.on_conflict_do_nothing(index_elements=[User.email]))
        await session.execute(update(User).where(User.email == email).values(role="admin"))
