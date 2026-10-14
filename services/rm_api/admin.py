"""`/api/admin/*`: flags, overrides, credit adjustments and job inspection (blueprint §2 Route map).

Administrators only (`role = 'admin'`, otherwise 403 `ADMIN_ONLY`). Every action is logged with the admin's
id and the
target, never with personal data. Credit adjustments are idempotent by a caller-chosen UUID (`admin:{uuid}`
in the ledger).
GDPR[personal-data]: job inspection returns metadata only; job arguments (addresses, login tokens) are never
exposed.
"""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Path, Query, Response
from rm_contracts.me import (
    BillingHoldClear,
    BillingHoldOut,
    CreditAdjust,
    CreditAdjustOut,
    FlagKey,
    FlagOut,
    FlagUpdate,
    JobOut,
    JobsOut,
    OverrideOut,
    OverridePut,
)
from rm_contracts.problems import ProblemCode
from rm_core.db.models import CreditAccount, FeatureFlag, FeatureOverride, User
from rm_core.ledger import admin_adjust, clear_billing_hold, lock_user
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from rm_api.deps import AdminDep, SessionDep
from rm_api.problems import Problem

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])
JobStatus = Literal["todo", "doing", "succeeded", "failed", "cancelled", "aborting", "aborted"]
QueueName = Annotated[str, Query(pattern=r"^[a-z][a-z0-9_]{0,31}$")]


def _flag_out(flag: FeatureFlag, overrides: int) -> FlagOut:
    return FlagOut(
        key=flag.key,
        description=flag.description,
        enabled_default=flag.enabled_default,
        min_plan=flag.min_plan,
        rollout_pct=flag.rollout_pct,
        overrides=overrides,
    )


async def _override_count(db: SessionDep, key: str) -> int:
    count = await db.scalar(
        select(func.count()).select_from(FeatureOverride).where(FeatureOverride.flag_key == key)
    )
    return int(count or 0)


@router.get("/flags", response_model=list[FlagOut])
async def list_flags(db: SessionDep, admin: AdminDep) -> list[FlagOut]:
    rows = await db.execute(select(FeatureOverride.flag_key, func.count()).group_by(FeatureOverride.flag_key))
    counts = {str(key): int(n) for key, n in rows}
    flags = (await db.scalars(select(FeatureFlag).order_by(FeatureFlag.key))).all()
    return [_flag_out(f, counts.get(f.key, 0)) for f in flags]


@router.put("/flags/{key}", response_model=FlagOut)
async def update_flag(
    key: Annotated[FlagKey, Path()], body: FlagUpdate, db: SessionDep, admin: AdminDep
) -> FlagOut:
    flag = await db.get(FeatureFlag, key, with_for_update=True)
    if flag is None:
        raise Problem.not_found("Flag")
    changes = body.model_dump(exclude_none=True, exclude={"clear_min_plan"})
    if body.clear_min_plan:
        changes["min_plan"] = None
    for field, value in changes.items():
        setattr(flag, field, value)
    await db.flush()
    log.info("admin_action", admin=admin.user_id, action="flag_update", flag=key, changes=changes)
    return _flag_out(flag, await _override_count(db, key))


@router.put("/flags/{key}/overrides/{user_id}", response_model=OverrideOut)
async def put_override(
    key: Annotated[FlagKey, Path()],
    user_id: Annotated[str, Path(min_length=1, max_length=64)],
    body: OverridePut,
    db: SessionDep,
    admin: AdminDep,
) -> OverrideOut:
    if await db.get(FeatureFlag, key) is None or await db.get(User, user_id) is None:
        raise Problem.not_found("Flag or user")
    stmt = insert(FeatureOverride).values(
        flag_key=key,
        user_id=user_id,
        enabled=body.enabled,
        reason=body.reason,
        expires_at=body.expires_at,
        created_by=admin.user_id,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[FeatureOverride.flag_key, FeatureOverride.user_id],
        set_={
            "enabled": stmt.excluded.enabled,
            "reason": stmt.excluded.reason,
            "expires_at": stmt.excluded.expires_at,
            "created_by": stmt.excluded.created_by,
        },
    ).returning(FeatureOverride)
    row = (await db.execute(stmt)).scalar_one()
    log.info(
        "admin_action",
        admin=admin.user_id,
        action="override_put",
        flag=key,
        target=user_id,
        enabled=body.enabled,
    )
    return OverrideOut(
        flag_key=row.flag_key,
        user_id=row.user_id,
        enabled=row.enabled,
        reason=row.reason,
        expires_at=row.expires_at,
        created_by=row.created_by,
    )


@router.delete("/flags/{key}/overrides/{user_id}", status_code=204)
async def delete_override(
    key: Annotated[FlagKey, Path()],
    user_id: Annotated[str, Path(min_length=1, max_length=64)],
    db: SessionDep,
    admin: AdminDep,
) -> Response:
    await db.execute(
        delete(FeatureOverride).where(FeatureOverride.flag_key == key, FeatureOverride.user_id == user_id)
    )
    log.info("admin_action", admin=admin.user_id, action="override_delete", flag=key, target=user_id)
    return Response(status_code=204)


@router.post("/credits/adjust", response_model=CreditAdjustOut)
async def adjust_credits(body: CreditAdjust, db: SessionDep, admin: AdminDep) -> CreditAdjustOut:
    """Add or remove credits. Repeating the same `idempotency_key` changes nothing and reports `applied:
    false`."""
    if body.delta == 0:
        raise Problem(422, ProblemCode.VALIDATION_ERROR, "delta must not be zero")
    if await db.get(User, body.user_id) is None:
        raise Problem.not_found("User")
    try:
        async with db.begin_nested():  # a refused adjustment leaves no half-written ledger row behind
            applied = await admin_adjust(
                db,
                body.user_id,
                body.delta,
                key=str(body.idempotency_key),
                note=f"{admin.user_id}: {body.note}",
            )
    except IntegrityError:
        raise Problem(409, ProblemCode.CREDIT_BELOW_ZERO, "The balance cannot go below zero") from None
    balance = await db.scalar(select(CreditAccount.balance).where(CreditAccount.user_id == body.user_id))
    log.info(
        "admin_action",
        admin=admin.user_id,
        action="credit_adjust",
        target=body.user_id,
        delta=body.delta,
        applied=applied,
    )
    return CreditAdjustOut(applied=applied, balance=int(balance or 0))


@router.post("/users/{user_id}/billing-hold/clear", response_model=BillingHoldOut)
async def clear_hold(
    user_id: Annotated[str, Path(min_length=1, max_length=64)],
    body: BillingHoldClear,
    db: SessionDep,
    admin: AdminDep,
) -> BillingHoldOut:
    """End a billing review (units were consumed before a purchase was reversed). The note and the admin are
    logged; reports already made stay readable, and nothing is claimed back."""
    if await db.get(User, user_id) is None:
        raise Problem.not_found("User")
    await lock_user(db, user_id)
    cleared = await clear_billing_hold(db, user_id)
    log.info(
        "admin_action", admin=admin.user_id, action="billing_hold_clear", target=user_id, cleared=cleared
    )
    return BillingHoldOut(cleared=cleared)


@router.get("/jobs", response_model=JobsOut)
async def inspect_jobs(
    db: SessionDep,
    admin: AdminDep,
    queue: QueueName | None = None,
    status: JobStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> JobsOut:
    """Procrastinate job metadata: counts per queue and status, and the newest jobs. Never the arguments."""
    counts: dict[str, dict[str, int]] = {}
    count_rows = await db.execute(
        text("SELECT queue_name, status::text, count(*) FROM public.procrastinate_jobs GROUP BY 1, 2")
    )
    for q, s, n in count_rows:
        counts.setdefault(str(q), {})[str(s)] = int(n)
    recent_rows = await db.execute(
        text(
            "SELECT id, queue_name, task_name, status::text, attempts, scheduled_at "
            "FROM public.procrastinate_jobs "
            "WHERE (CAST(:q AS text) IS NULL OR queue_name = CAST(:q AS text)) "
            "AND (CAST(:s AS text) IS NULL OR status::text = CAST(:s AS text)) "
            "ORDER BY id DESC LIMIT :n"
        ),
        {"q": queue, "s": status, "n": limit},
    )
    recent = [
        JobOut(id=int(i), queue=str(q), task=str(t), status=str(s), attempts=int(a), scheduled_at=at)
        for i, q, t, s, a, at in recent_rows
    ]
    return JobsOut(counts=counts, recent=recent)
