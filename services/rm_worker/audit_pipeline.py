"""Run one audit end to end: snapshot, extract, context, engine, persist, settle (blueprint §2, §4.5 b).

Everything outside the database is injected (`AuditServices`): production wires the real Otodom client and
market context (#187); tests wire offline fakes. The engine does all the arithmetic (`deal_analyzer`,
invariant 4); this module copies its output into typed columns and decides the charge:

* captured on `succeeded` / `succeeded_degraded`; released on every other terminal state (blueprint §2);
* idempotent: a second run of the same job finds the audit no longer `queued` and does nothing, and
  `ledger.settle` claims the charge atomically, so a duplicate delivery never settles twice.

A worker killed between the claim and the final transaction leaves the audit `running`; the reconciler
(`tasks/reconcile.py`, #186) fails it past its deadline and releases the charge. The engine runs in a killable
child process (`engine_child.py`), so a hung or runaway engine cannot hold the slot.

LEGAL[scraping]: the page is fetched via the injected source, shared across tenants for 6 h (RM-184).
LEGAL[url-analysis]: only the strictly parsed short id stored on the audit row is ever fetched (RM-184).
"""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import sentry_sdk
import structlog
from deal_analyzer import (
    DealAnalysis,
    ExtractionError,
    FractionalOwnershipError,
    Listing,
    RentInput,
    RentNotADealError,
    classify_ownership,
    extract_listing,
    require_whole_ownership,
)
from rm_contracts.problems import ProblemCode
from rm_core.db.models import Audit, AuditStatus, ListingSnapshot
from rm_core.deadline import Deadline
from rm_core.ledger import settle
from rm_core.legal import LegalTag, tag_names
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.clients.otodom import ListingGone, UpstreamBlocked, UpstreamSchemaDrift
from rm_worker.engine_child import ChildEngine, EngineRunner
from rm_worker.snapshot_service import ListingSource, get_snapshot

log = structlog.get_logger(__name__)
CAPTURED = frozenset({AuditStatus.succeeded, AuditStatus.succeeded_degraded})
DEGRADING_WARNING = (
    "vision_unavailable"  # blueprint §2: no vision result is `succeeded_degraded`, charge captured
)


class ContextProvider(Protocol):
    """Market inputs the engine needs but does not fetch (the market lane, #106; rates)."""

    async def rent_input(self, listing: Listing, *, deadline: Deadline) -> RentInput: ...

    async def risk_free_rate(self, *, deadline: Deadline) -> Decimal: ...


@dataclass(frozen=True)
class AuditServices:
    sessionmaker: async_sessionmaker[AsyncSession]
    source: ListingSource
    context: ContextProvider
    timeout_s: float = 900.0  # one deadline per audit (blueprint §6)
    engine: EngineRunner = field(default_factory=ChildEngine)  # killable child process, memory capped (#186)


@dataclass(frozen=True)
class Outcome:
    status: AuditStatus
    error_code: str | None = None
    analysis: DealAnalysis | None = None
    snapshot_id: UUID | None = None


async def _claim(sm: async_sessionmaker[AsyncSession], audit_id: UUID) -> str | None:
    """queued -> running, once. Returns the Otodom id, or None if another delivery already took it."""
    async with sm() as db, db.begin():
        return await db.scalar(
            update(Audit)
            .where(Audit.id == audit_id, Audit.status == AuditStatus.queued)
            .values(status=AuditStatus.running, started_at=func.now())
            .returning(Audit.otodom_id)
        )


# Terminal state and stable code per failure (blueprint §2 error contract); first match wins.
_FAILURES: tuple[tuple[type[Exception], AuditStatus, str], ...] = (
    (RentNotADealError, AuditStatus.rejected, ProblemCode.RENT_NOT_DEAL),
    (FractionalOwnershipError, AuditStatus.rejected, ProblemCode.FRACTIONAL_OWNERSHIP),
    (ListingGone, AuditStatus.failed_input, ProblemCode.LISTING_GONE),
    (UpstreamBlocked, AuditStatus.failed_upstream, ProblemCode.UPSTREAM_BLOCKED),
    (UpstreamSchemaDrift, AuditStatus.failed_upstream, ProblemCode.UPSTREAM_SCHEMA_DRIFT),
    (ExtractionError, AuditStatus.failed_upstream, ProblemCode.UPSTREAM_SCHEMA_DRIFT),
    (TimeoutError, AuditStatus.failed_internal, "TIMEOUT"),
)
_NEEDS_A_FIX = (UpstreamSchemaDrift, ExtractionError)


def _failure(exc: Exception) -> Outcome:
    for kind, status, code in _FAILURES:
        if isinstance(exc, kind):
            if isinstance(exc, _NEEDS_A_FIX):
                sentry_sdk.capture_exception(exc)  # a code fix, not a retry
            return Outcome(status, code)
    log.error("audit.crashed", exc_info=exc)
    sentry_sdk.capture_exception(exc)
    return Outcome(AuditStatus.failed_internal, ProblemCode.INTERNAL)


async def _analyse(services: AuditServices, otodom_id: str) -> Outcome:
    deadline = Deadline.after(services.timeout_s)
    try:
        async with asyncio.timeout(services.timeout_s):
            snapshot_id = await get_snapshot(
                services.sessionmaker, services.source, otodom_id, deadline=deadline
            )
            async with services.sessionmaker() as db:
                payload = await db.scalar(
                    select(ListingSnapshot.payload).where(ListingSnapshot.id == snapshot_id)
                )
            listing = extract_listing(payload)  # RENT and malformed payloads stop here: no context, no vision
            require_whole_ownership(  # invariant 5, checked before any market work; the engine checks again
                classify_ownership(
                    title=listing.title,
                    description=listing.description,
                    structured=listing.building_ownership,
                ),
                listing.otodom_id,
            )
            rent = await services.context.rent_input(listing, deadline=deadline)
            risk_free = await services.context.risk_free_rate(deadline=deadline)
            analysis = await services.engine.run(
                listing, rent=rent, risk_free=risk_free, timeout_s=deadline.remaining()
            )
    except Exception as exc:
        return _failure(exc)
    degraded = DEGRADING_WARNING in analysis.warnings
    return Outcome(
        AuditStatus.succeeded_degraded if degraded else AuditStatus.succeeded,
        ProblemCode.VISION_UNAVAILABLE if degraded else None,
        analysis,
        snapshot_id,
    )


async def _finish(sm: async_sessionmaker[AsyncSession], audit_id: UUID, out: Outcome) -> bool:
    """One transaction: write the terminal state and settle the charge. False if the audit was no longer
    `running` (someone else ended it; they settled it)."""
    values: dict[str, object] = {
        "status": out.status,
        "error_code": out.error_code,
        "finished_at": func.now(),
        "snapshot_id": out.snapshot_id,
    }
    if out.analysis is not None:
        a = out.analysis  # copied, never computed (invariant 4)
        values |= {
            "result": a.model_dump(mode="json"),
            "grade": a.valuation.grade,
            "asking_price_pln": a.valuation.asking_price_pln,
            "max_bid_pln": a.valuation.max_bid_pln,
            "irr_10y": a.cash_flow.returns.irr,
            "capex_pln": a.capex_used_pln,
            "engine_version": a.engine_version,
            "schema_version": a.schema_version,
        }
    async with sm() as db, db.begin():
        ended = await db.scalar(
            update(Audit)
            .where(Audit.id == audit_id, Audit.status == AuditStatus.running)
            .values(**values)
            .returning(Audit.id)
        )
        if ended is None:
            return False
        await settle(db, audit_id, capture=out.status in CAPTURED)
        return True


async def execute_audit(services: AuditServices, audit_id: UUID) -> AuditStatus | None:
    """Returns the terminal status this call produced, or None if the job was a duplicate or stale."""
    bound = log.bind(audit_id=str(audit_id), legal_tags=tag_names(LegalTag.scraping, LegalTag.url_analysis))
    otodom_id = await _claim(services.sessionmaker, audit_id)
    if otodom_id is None:
        bound.info("audit.skipped_not_queued")
        return None
    out = await _analyse(services, otodom_id)
    if not await _finish(services.sessionmaker, audit_id, out):
        bound.warning("audit.finish_lost", status=out.status.value)
        return None
    bound.info("audit.finished", status=out.status.value, error_code=out.error_code)
    return out.status


async def fail_unconfigured(sm: async_sessionmaker[AsyncSession], audit_id: UUID) -> AuditStatus | None:
    """No adapters are wired in this process: end the audit as an internal failure and release the credit,
    rather than leave it queued and charged. Same claim and finish path as a real run (idempotent)."""
    if await _claim(sm, audit_id) is None:
        return None
    out = Outcome(AuditStatus.failed_internal, ProblemCode.INTERNAL)
    log.error("audit.services_not_configured", audit_id=str(audit_id))
    return out.status if await _finish(sm, audit_id, out) else None
