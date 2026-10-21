"""Interior generation operations: the durable state machine around an image-model call (RM-450).

queued -> running -> succeeded | failed, or queued -> cancelled. Every transition is a conditional UPDATE
(`WHERE state = <expected>`), so a duplicate job delivery, a racing cancel and the recovery sweep each
settle an operation exactly once. Cancelling works only while queued: once a request may be in flight at
the provider it cannot be recalled. Reservation handling lives in the worker
(`rm_worker.interior_generation`).

Tenant rule: every read and write filters on the caller's user id; a foreign id is `InteriorNotFoundError`.

LEGAL[images]: operations concern the person's room photo and permitted reference images (RM-450)
GDPR[erasure]: rows cascade with the project and the account (RM-450)
"""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from rm_contracts.generation import PROMPT_VERSION, GenerationError, GenerationOut, GenerationState
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_core.db.models import InteriorGeneration, InteriorMedia, InteriorRevision
from rm_core.entitlements import db_now
from rm_core.interior import InteriorNotFoundError, _media_ref, _project  # pyright: ignore[reportPrivateUsage]
from rm_core.principal import Principal
from rm_core.settings import Settings

QUEUE_SLACK = timedelta(minutes=8)  # time allowed in the queue before an operation counts as lost
RECENT = 20


class GenerationConflictError(Exception):
    """`reason`: no_source_photo, idempotency, active, running or finished."""

    def __init__(self, reason: str, generation_id: UUID | None = None):
        super().__init__(reason)
        self.reason = reason
        self.generation_id = generation_id


def _cost(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.6f}"


def _out(row: InteriorGeneration, output: InteriorMedia | None) -> GenerationOut:
    return GenerationOut(
        generation_id=row.id,
        revision_id=row.revision_id,
        state=GenerationState(row.state),
        error_code=GenerationError(row.error_code) if row.error_code else None,
        model=row.model,
        prompt_version=row.prompt_version,
        references_used=row.references_used,
        references_skipped=row.references_skipped,
        output=_media_ref(output) if output is not None and output.state == "stored" else None,
        cost_usd=_cost(row.cost_usd),
        cost_estimated=row.cost_estimated,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


async def _outputs(db: AsyncSession, rows: list[InteriorGeneration]) -> dict[UUID, InteriorMedia]:
    ids = [r.output_media_id for r in rows if r.output_media_id is not None]
    if not ids:
        return {}
    found = (await db.scalars(select(InteriorMedia).where(InteriorMedia.id.in_(ids)))).all()
    return {m.id: m for m in found}


async def create_generation(
    db: AsyncSession,
    principal: Principal,
    project_id: UUID,
    revision_id: UUID,
    settings: Settings,
    *,
    idempotency_key: UUID | None,
) -> tuple[UUID, bool]:
    """Queue an operation for a saved revision. Returns `(id, created)`. A repeated key, or the same revision
    already queued or running, returns the existing operation instead of creating a second one."""
    await _project(db, principal, project_id, lock=True)
    revision = await db.scalar(
        select(InteriorRevision).where(
            InteriorRevision.id == revision_id,
            InteriorRevision.project_id == project_id,
            InteriorRevision.user_id == principal.user_id,
        )
    )
    if revision is None:
        raise InteriorNotFoundError
    key = str(idempotency_key) if idempotency_key is not None else None
    if key is not None:
        twin = await db.scalar(
            select(InteriorGeneration).where(
                InteriorGeneration.project_id == project_id, InteriorGeneration.idempotency_key == key
            )
        )
        if twin is not None:
            if twin.revision_id != revision_id:
                raise GenerationConflictError("idempotency", twin.id)
            return twin.id, False
    active = await db.scalar(
        select(InteriorGeneration).where(
            InteriorGeneration.project_id == project_id, InteriorGeneration.state.in_(("queued", "running"))
        )
    )
    if active is not None:
        if active.revision_id == revision_id:
            return active.id, False
        raise GenerationConflictError("active", active.id)
    if revision.source_digest is None:
        raise GenerationConflictError("no_source_photo")
    now = await db_now(db)
    row = InteriorGeneration(
        user_id=principal.user_id,
        project_id=project_id,
        revision_id=revision_id,
        idempotency_key=key,
        model=settings.interior_image_model,
        prompt_version=PROMPT_VERSION,
        estimate_usd=settings.interior_attempt_estimate_usd,
        deadline_at=now + timedelta(seconds=settings.interior_generation_deadline_s) + QUEUE_SLACK,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:  # a concurrent request created the active one first
        await db.rollback()
        winner = await db.scalar(
            select(InteriorGeneration.id).where(
                InteriorGeneration.project_id == project_id,
                InteriorGeneration.state.in_(("queued", "running")),
            )
        )
        if winner is None:
            raise
        raise GenerationConflictError("active", winner) from None
    return row.id, True


async def get_generation(
    db: AsyncSession, principal: Principal, project_id: UUID, generation_id: UUID
) -> GenerationOut:
    await _project(db, principal, project_id)
    row = await db.scalar(
        select(InteriorGeneration).where(
            InteriorGeneration.id == generation_id,
            InteriorGeneration.project_id == project_id,
            InteriorGeneration.user_id == principal.user_id,
        )
    )
    if row is None:
        raise InteriorNotFoundError
    return _out(row, (await _outputs(db, [row])).get(row.output_media_id) if row.output_media_id else None)


async def list_generations(db: AsyncSession, principal: Principal, project_id: UUID) -> list[GenerationOut]:
    await _project(db, principal, project_id)
    rows = list(
        (
            await db.scalars(
                select(InteriorGeneration)
                .where(
                    InteriorGeneration.project_id == project_id,
                    InteriorGeneration.user_id == principal.user_id,
                )
                .order_by(InteriorGeneration.created_at.desc(), InteriorGeneration.id)
                .limit(RECENT)
            )
        ).all()
    )
    outputs = await _outputs(db, rows)
    return [_out(r, outputs.get(r.output_media_id) if r.output_media_id else None) for r in rows]


async def cancel_generation(
    db: AsyncSession, principal: Principal, project_id: UUID, generation_id: UUID
) -> None:
    """Queued-only (owner decision 2026-10-19). Idempotent for an already cancelled operation."""
    await _project(db, principal, project_id, lock=True)
    now = await db_now(db)
    changed = await db.scalar(
        update(InteriorGeneration)
        .where(
            InteriorGeneration.id == generation_id,
            InteriorGeneration.project_id == project_id,
            InteriorGeneration.user_id == principal.user_id,
            InteriorGeneration.state == "queued",
        )
        .values(state="cancelled", finished_at=now)
        .returning(InteriorGeneration.id)
    )
    if changed is not None:
        return
    row = await db.scalar(
        select(InteriorGeneration).where(
            InteriorGeneration.id == generation_id,
            InteriorGeneration.project_id == project_id,
            InteriorGeneration.user_id == principal.user_id,
        )
    )
    if row is None:
        raise InteriorNotFoundError
    if row.state == "cancelled":
        return
    raise GenerationConflictError("running" if row.state == "running" else "finished", row.id)


# ---------------------------------------------------------------------------- worker-side transitions
async def claim(sm: async_sessionmaker[AsyncSession], generation_id: UUID) -> InteriorGeneration | None:
    """queued -> running, once. None means another delivery or a cancel got there first."""
    async with sm() as db, db.begin():
        now = await db_now(db)
        row = await db.scalar(
            update(InteriorGeneration)
            .where(InteriorGeneration.id == generation_id, InteriorGeneration.state == "queued")
            .values(state="running", started_at=now)
            .returning(InteriorGeneration)
        )
        if row is None:
            return None
        db.expunge(row)
        return row


async def record_reservation(
    sm: async_sessionmaker[AsyncSession], generation_id: UUID, reservation_id: UUID | None
) -> None:
    async with sm() as db, db.begin():
        await db.execute(
            update(InteriorGeneration)
            .where(InteriorGeneration.id == generation_id)
            .values(reservation_id=reservation_id)
        )


async def mark_sent(sm: async_sessionmaker[AsyncSession], generation_id: UUID) -> None:
    """Committed before the provider is called: from here on the spend is unknown if we crash."""
    async with sm() as db, db.begin():
        now = await db_now(db)
        await db.execute(
            update(InteriorGeneration)
            .where(InteriorGeneration.id == generation_id)
            .values(request_sent_at=now)
        )


async def finish(
    sm: async_sessionmaker[AsyncSession],
    generation_id: UUID,
    state: GenerationState,
    *,
    error: GenerationError | None = None,
    cost_usd: Decimal | None = None,
    cost_estimated: bool = False,
    output_media_id: UUID | None = None,
    references_used: int | None = None,
    references_skipped: int | None = None,
) -> bool:
    """running -> terminal, once. False means it already ended (e.g. the recovery sweep got there first)."""
    values: dict[str, object] = {
        "state": state.value,
        "error_code": error.value if error else None,
        "cost_usd": cost_usd,
        "cost_estimated": cost_estimated,
        "output_media_id": output_media_id,
    }
    if references_used is not None:
        values["references_used"] = references_used
    if references_skipped is not None:
        values["references_skipped"] = references_skipped
    async with sm() as db, db.begin():
        values["finished_at"] = await db_now(db)
        done = await db.scalar(
            update(InteriorGeneration)
            .where(InteriorGeneration.id == generation_id, InteriorGeneration.state == "running")
            .values(**values)
            .returning(InteriorGeneration.id)
        )
        return done is not None


async def set_references(
    sm: async_sessionmaker[AsyncSession], generation_id: UUID, used: int, skipped: int
) -> None:
    async with sm() as db, db.begin():
        await db.execute(
            update(InteriorGeneration)
            .where(InteriorGeneration.id == generation_id)
            .values(references_used=used, references_skipped=skipped)
        )


async def count_running_or_queued(sm: async_sessionmaker[AsyncSession]) -> int:
    async with sm() as db:
        return (
            await db.scalar(
                select(func.count())
                .select_from(InteriorGeneration)
                .where(InteriorGeneration.state.in_(("queued", "running")))
            )
        ) or 0
