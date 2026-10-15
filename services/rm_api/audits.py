"""`/api/audits`: submit a listing for analysis and read the stored result (blueprint §2 Route map, §4.5 b).

The route reserves the credit, records the audit and defers the job; the worker (`rm_worker.audit_pipeline`)
runs the engine and settles the charge. The API never computes a number: it echoes what the worker stored
(agents.md §2, invariant 4). Tenant rule (agents.md §4): another user's audit is a 404, never a 403.

LEGAL[url-analysis]: accepts a user-supplied listing URL or id; only the parsed short id is kept (RM-184).
LEGAL[republication]: the stored result echoes third-party listing fields to the requesting tenant (RM-184).
"""

import base64
import binascii
import json
from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

import structlog
from deal_analyzer.analysis import ENGINE_VERSION, SCHEMA_VERSION
from fastapi import APIRouter, Header, Path, Query, Request
from fastapi.responses import StreamingResponse
from rm_contracts.audits import (
    AuditAccepted,
    AuditCreate,
    AuditOut,
    AuditPage,
    AuditState,
    AuditSummary,
    ChargeStateName,
)
from rm_contracts.problems import ProblemCode
from rm_core.db.models import Audit, AuditStatus, ChargeSource, ChargeState, Listing
from rm_core.entitlements import load_entitlements
from rm_core.ledger import BillingHoldError, record_reservation, reserve
from rm_core.listing_ref import InvalidListingRefError, parse_listing_ref
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rm_api.deps import PrincipalDep, SessionDep
from rm_api.problems import Problem
from rm_api.queue import AuditQueue
from rm_api.sse import stream_events

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/audits", tags=["audits"])
FEATURE = "deal_audit"
OTODOM_OFFER_URL = "https://www.otodom.pl/pl/oferta/"
ACTIVE = (AuditStatus.queued, AuditStatus.running)


def _out(a: Audit) -> AuditOut:
    return AuditOut(
        audit_id=a.id,
        otodom_id=a.otodom_id,
        status=AuditState(a.status.value),
        error_code=a.error_code,
        charge_state=ChargeStateName(a.charge_state.value),
        created_at=a.created_at,
        started_at=a.started_at,
        finished_at=a.finished_at,
        grade=a.grade,
        asking_price_pln=a.asking_price_pln,
        max_bid_pln=a.max_bid_pln,
        irr_10y=a.irr_10y,
        capex_pln=a.capex_pln,
        result=a.result,
    )


def _summary(a: Audit) -> AuditSummary:
    return AuditSummary(
        audit_id=a.id,
        otodom_id=a.otodom_id,
        status=AuditState(a.status.value),
        error_code=a.error_code,
        created_at=a.created_at,
        finished_at=a.finished_at,
        grade=a.grade,
        asking_price_pln=a.asking_price_pln,
        max_bid_pln=a.max_bid_pln,
    )


async def _active_audit_id(db: AsyncSession, user_id: str, otodom_id: str) -> UUID | None:
    return await db.scalar(
        select(Audit.id).where(
            Audit.user_id == user_id, Audit.otodom_id == otodom_id, Audit.status.in_(ACTIVE)
        )
    )


def _in_progress(audit_id: UUID) -> Problem:
    return Problem(
        409,
        ProblemCode.AUDIT_IN_PROGRESS,
        "An analysis of this listing is already running",
        audit_id=str(audit_id),
    )


@router.post("", status_code=202, response_model=AuditAccepted)
async def create_audit(
    body: AuditCreate, request: Request, db: SessionDep, principal: PrincipalDep
) -> AuditAccepted:
    try:
        short_id = parse_listing_ref(body.listing_ref)
    except InvalidListingRefError:
        raise Problem(422, ProblemCode.INVALID_LISTING_REF, "Not an Otodom listing URL or ID") from None
    if (
        body.analyst
    ):  # the text-LLM audit does not exist yet: refuse instead of charging 2 credits for nothing
        raise Problem(403, ProblemCode.FEATURE_NOT_IN_PLAN, "The analyst audit is not available yet")

    existing = await _active_audit_id(db, principal.user_id, short_id)
    if existing is not None:
        raise _in_progress(existing)

    audit_id = uuid4()
    ent = await load_entitlements(db, principal.user_id)
    try:
        reservation = await reserve(db, principal.user_id, FEATURE, ent, audit_id=audit_id)
    except BillingHoldError:
        raise Problem(
            403, ProblemCode.BILLING_HOLD, "Your account is on a billing review; contact support"
        ) from None
    if reservation is None:
        raise Problem(402, ProblemCode.QUOTA_EXHAUSTED, "No analyses left", upgrade_url="/billing")

    await db.execute(
        insert(Listing)
        .values(otodom_id=short_id, url=f"{OTODOM_OFFER_URL}{short_id}")
        .on_conflict_do_nothing(index_elements=[Listing.otodom_id])
    )
    db.add(
        Audit(
            id=audit_id,
            user_id=principal.user_id,
            otodom_id=short_id,
            status=AuditStatus.queued,
            charge_source=reservation.source,
            charge_state=ChargeState.reserved,
            usage_period_id=reservation.usage_period_id,
            lang=body.lang,
            analyst=False,
            engine_version=ENGINE_VERSION,
            schema_version=SCHEMA_VERSION,
        )
    )
    try:
        await db.flush()  # hits uq_audit_one_active_per_listing when a parallel request got there first
    except IntegrityError:
        await db.rollback()  # also undoes the reservation made above
        winner = await _active_audit_id(db, principal.user_id, short_id)
        if winner is None:
            raise
        raise _in_progress(winner) from None
    await record_reservation(db, reservation, principal.user_id)
    await db.commit()  # the reservation and the audit become durable together, before the job exists

    queue: AuditQueue = request.app.state.audit_queue
    try:
        await queue.run_audit(audit_id)
    except Exception:
        # The audit stays `queued` and charged; the reconciler (#186) re-defers it. Do not fail the request.
        log.exception("audit.defer_failed", audit_id=str(audit_id))
    remaining = ent.credit_balance - reservation.cost if reservation.source is ChargeSource.credit else None
    return AuditAccepted(
        audit_id=audit_id,
        status=AuditState.queued,
        events_url=f"/api/audits/{audit_id}/events",
        credits_remaining=remaining,
    )


def _encode_cursor(a: Audit) -> str:
    raw = json.dumps([a.created_at.isoformat(), str(a.id)], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Strict: anything that is not exactly what `_encode_cursor` makes is a 422, never a 500 or a guess."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        stamp, ident = json.loads(raw)
        at = datetime.fromisoformat(stamp)
        if at.tzinfo is None or not isinstance(ident, str):
            raise ValueError
        return at, UUID(ident)
    except (ValueError, TypeError, binascii.Error):
        raise Problem(
            422,
            ProblemCode.VALIDATION_ERROR,
            "Invalid cursor",
            errors=[
                {"loc": ["query", "cursor"], "type": "invalid_cursor", "msg": "Not a cursor from this API"}
            ],
        ) from None


@router.get("", response_model=AuditPage)
async def list_audits(
    db: SessionDep,
    principal: PrincipalDep,
    *,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[
        str | None, Query(max_length=200, description="`next_cursor` of the previous page")
    ] = None,
    status: Annotated[list[AuditState] | None, Query(description="repeat to match any of several")] = None,
    grade: Annotated[str | None, Query(pattern=r"^[A-Za-z][+-]?$", max_length=2)] = None,
    q: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9]{1,16}$", description="Otodom id prefix")] = None,
) -> AuditPage:
    """The caller's audits, newest first, by keyset over `(created_at, id)`: a row inserted between two
    requests never repeats or skips a row. Another user's cursor only ever pages the caller's own rows."""
    stmt = select(Audit).where(Audit.user_id == principal.user_id)
    if status:
        stmt = stmt.where(Audit.status.in_([AuditStatus(s.value) for s in status]))
    if grade is not None:
        stmt = stmt.where(Audit.grade == grade.upper())
    if q is not None:
        stmt = stmt.where(Audit.otodom_id.ilike(f"{q}%"))  # q is alphanumeric only (pattern above)
    if cursor is not None:
        at, ident = _decode_cursor(cursor)
        stmt = stmt.where(or_(Audit.created_at < at, and_(Audit.created_at == at, Audit.id < ident)))
    rows = (await db.scalars(stmt.order_by(Audit.created_at.desc(), Audit.id.desc()).limit(limit + 1))).all()
    page = rows[:limit]
    return AuditPage(
        items=[_summary(a) for a in page], next_cursor=_encode_cursor(page[-1]) if len(rows) > limit else None
    )


@router.get("/{audit_id}", response_model=AuditOut)
async def get_audit(audit_id: Annotated[UUID, Path()], db: SessionDep, principal: PrincipalDep) -> AuditOut:
    audit = await db.scalar(select(Audit).where(Audit.id == audit_id, Audit.user_id == principal.user_id))
    if audit is None:
        raise Problem.not_found("Audit")  # unknown and foreign look the same
    return _out(audit)


STREAM_GRACE_S = 120  # a stream may outlive the job deadline a little; the client then reconnects


@router.get(
    "/{audit_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "progress, then done or error"}},
)
async def audit_events(
    audit_id: Annotated[UUID, Path()],
    request: Request,
    db: SessionDep,
    principal: PrincipalDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID", max_length=20)] = None,
) -> StreamingResponse:
    """Server-sent progress. Replays every event after `Last-Event-ID`, then streams live; the first terminal
    event (`done` or `error`) ends the stream. Another tenant's or an unknown audit is a 404."""
    owned = await db.scalar(select(Audit.id).where(Audit.id == audit_id, Audit.user_id == principal.user_id))
    if owned is None:
        raise Problem.not_found("Audit")
    await db.close()  # the stream holds no pooled connection while it waits
    cursor = int(last_event_id) if last_event_id is not None and last_event_id.isdecimal() else 0
    settings = request.app.state.settings
    return StreamingResponse(
        stream_events(
            request.app.state.sessionmaker,
            request.app.state.progress_hub,
            audit_id,
            last_event_id=cursor,
            max_seconds=settings.audit_job_timeout_s + STREAM_GRACE_S,
            is_disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
