"""`/api/audits`: submit a listing for analysis and read the stored result (blueprint §2 Route map, §4.5 b).

The route reserves the credit, records the audit and defers the job; the worker (`rm_worker.audit_pipeline`)
runs the engine and settles the charge. The API never computes a number: it echoes what the worker stored
(agents.md §2, invariant 4). Tenant rule (agents.md §4): another user's audit is a 404, never a 403.

LEGAL[url-analysis]: accepts a user-supplied listing URL or id; only the parsed short id is kept (RM-184).
LEGAL[republication]: the stored result echoes third-party listing fields to the requesting tenant (RM-184).
"""

from typing import Annotated
from uuid import UUID, uuid4

import structlog
from deal_analyzer.analysis import ENGINE_VERSION, SCHEMA_VERSION
from fastapi import APIRouter, Path, Query, Request
from rm_contracts.audits import (
    AuditAccepted,
    AuditCreate,
    AuditOut,
    AuditState,
    AuditSummary,
    ChargeStateName,
)
from rm_contracts.problems import ProblemCode
from rm_core.db.models import Audit, AuditStatus, ChargeSource, ChargeState, Listing
from rm_core.entitlements import load_entitlements
from rm_core.ledger import record_reservation, reserve
from rm_core.listing_ref import InvalidListingRefError, parse_listing_ref
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rm_api.deps import PrincipalDep, SessionDep
from rm_api.problems import Problem
from rm_api.queue import AuditQueue

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
    reservation = await reserve(db, principal.user_id, FEATURE, ent, audit_id=audit_id)
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


@router.get("", response_model=list[AuditSummary])
async def list_audits(
    db: SessionDep, principal: PrincipalDep, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[AuditSummary]:
    rows = (
        await db.scalars(
            select(Audit)
            .where(Audit.user_id == principal.user_id)
            .order_by(Audit.created_at.desc(), Audit.id)
            .limit(limit)
        )
    ).all()
    return [_summary(a) for a in rows]


@router.get("/{audit_id}", response_model=AuditOut)
async def get_audit(audit_id: Annotated[UUID, Path()], db: SessionDep, principal: PrincipalDep) -> AuditOut:
    audit = await db.scalar(select(Audit).where(Audit.id == audit_id, Audit.user_id == principal.user_id))
    if audit is None:
        raise Problem.not_found("Audit")  # unknown and foreign look the same
    return _out(audit)
