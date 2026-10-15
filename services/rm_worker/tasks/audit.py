"""The `run_audit` job (queue `audit`). The API defers it by name after the reservation commits."""

from uuid import UUID

import structlog
from rm_contracts.jobs import AUDIT_QUEUE, RUN_AUDIT_TASK
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.settings import get_settings

from rm_worker import audit_services
from rm_worker.app import app
from rm_worker.audit_pipeline import execute_audit, fail_unconfigured

log = structlog.get_logger(__name__)


@app.task(name=RUN_AUDIT_TASK, queue=AUDIT_QUEUE)
async def run_audit(audit_id: str) -> None:
    try:
        services = audit_services.get()
    except audit_services.NotConfiguredError:
        engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
        try:
            await fail_unconfigured(make_sessionmaker(engine), UUID(audit_id))
        finally:
            await engine.dispose()
        return
    await execute_audit(services, UUID(audit_id))
