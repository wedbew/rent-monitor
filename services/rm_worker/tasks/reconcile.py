"""`reconcile_queued_audits` (queue `ops`, every minute): make an interrupted audit end
correctly (#186, blueprint §2 error contract, §4.5 b).

Three ways an audit gets stranded, all recovered here from the database alone:

* the API committed the audit and the reservation, then the defer failed (queue outage): the audit is `queued`
  and has no job. Re-deferred after `REDEFER_AFTER_S`; the queueing lock makes a repeated defer a no-op.
* the job was lost or never started and the audit outlived its deadline while `queued`: failed, charge
  released.
* the worker died (OOM, deploy restart, host loss) after the claim: the audit is `running` past its deadline
  plus a grace: failed `TIMEOUT`, charge released. A job that is merely slow is never touched before then.

Exactly-once settlement: the failure is one transaction, `UPDATE ... WHERE <stale>`
followed by `ledger.settle`. The worker's own finish is `UPDATE ... WHERE status = 'running'`, so when the two
race, row locking lets exactly one UPDATE match; the loser changes nothing and `settle` is an atomic
claim on `charge_state`, so the charge is released at most once and never both released and captured.
Everything is idempotent: running the reconciler twice, or concurrently, gives the same result.

Staleness is judged with the database clock (`now()`), never a worker clock.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

import structlog
from procrastinate import exceptions as procrastinate_exceptions
from rm_contracts.jobs import AUDIT_QUEUE, RUN_AUDIT_TASK
from rm_core.db.models import Audit, AuditStatus
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import settle
from rm_core.settings import get_settings
from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.app import app

log = structlog.get_logger(__name__)
REDEFER_AFTER_S = 60  # a queued audit older than this and still queued is probably missing its job
GRACE_S = 60  # on top of the audit deadline: the worker's own timeout fires first
BATCH = 100  # per run; the next minute continues, so a backlog drains without one long transaction
WORKER_LOST = "TIMEOUT"

Redefer = Callable[[UUID], Awaitable[None]]


@dataclass
class Reconciled:
    redeferred: list[UUID] = field(default_factory=list[UUID])
    failed: list[UUID] = field(default_factory=list[UUID])


def _stale(job_timeout_s: float) -> ColumnElement[bool]:
    """SQL predicate: queued past the deadline since creation, or running past it since the claim."""
    limit = timedelta(seconds=job_timeout_s + GRACE_S)
    return or_(
        and_(Audit.status == AuditStatus.queued, Audit.created_at < func.now() - limit),
        and_(Audit.status == AuditStatus.running, Audit.started_at < func.now() - limit),
    )


async def _fail(sm: async_sessionmaker[AsyncSession], audit_id: UUID, job_timeout_s: float) -> bool:
    """Fail one stale audit and release its charge, atomically. False if it was no longer stale."""
    async with sm() as db, db.begin():
        ended = await db.scalar(
            update(Audit)
            .where(Audit.id == audit_id, _stale(job_timeout_s))
            .values(
                status=AuditStatus.failed_internal,
                error_code=WORKER_LOST,
                finished_at=func.now(),
            )
            .returning(Audit.id)
        )
        if ended is None:
            return False
        await settle(db, audit_id, capture=False)
        return True


async def reconcile_audits(
    sm: async_sessionmaker[AsyncSession], redefer: Redefer, *, job_timeout_s: float
) -> Reconciled:
    done = Reconciled()
    limit = timedelta(seconds=job_timeout_s + GRACE_S)
    async with sm() as db:
        stale = (
            await db.scalars(
                select(Audit.id).where(_stale(job_timeout_s)).order_by(Audit.created_at).limit(BATCH)
            )
        ).all()
        orphans = (
            await db.scalars(
                select(Audit.id)
                .where(
                    Audit.status == AuditStatus.queued,
                    Audit.created_at < func.now() - timedelta(seconds=REDEFER_AFTER_S),
                    Audit.created_at >= func.now() - limit,
                )
                .order_by(Audit.created_at)
                .limit(BATCH)
            )
        ).all()
    for audit_id in stale:
        if await _fail(sm, audit_id, job_timeout_s):
            done.failed.append(audit_id)
            log.warning("audit.reconciled_failed", audit_id=str(audit_id), error_code=WORKER_LOST)
    for audit_id in orphans:
        try:
            await redefer(audit_id)
        except Exception:
            log.exception("audit.redefer_failed", audit_id=str(audit_id))  # the next run tries again
            continue
        done.redeferred.append(audit_id)
    if done.failed or done.redeferred:
        log.info("audit.reconciled", failed=len(done.failed), redeferred=len(done.redeferred))
    return done


async def defer_run_audit(audit_id: UUID) -> None:
    """Same job, same lock as the API's defer: a todo job for this audit makes this a no-op."""
    try:
        await app.configure_task(
            name=RUN_AUDIT_TASK, queue=AUDIT_QUEUE, queueing_lock=f"audit:{audit_id}"
        ).defer_async(audit_id=str(audit_id))
    except procrastinate_exceptions.AlreadyEnqueued:
        return


@app.periodic(cron="* * * * *")
@app.task(queue="ops", name="reconcile_queued_audits", queueing_lock="reconcile_queued_audits")
async def reconcile_queued_audits(timestamp: int) -> None:
    settings = get_settings()
    engine = make_engine(settings, pool_size=1, max_overflow=0)
    try:
        await reconcile_audits(
            make_sessionmaker(engine), defer_run_audit, job_timeout_s=settings.audit_job_timeout_s
        )
    finally:
        await engine.dispose()
