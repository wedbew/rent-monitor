"""Scheduled GUS BDL location-context refresh (queue `batch`, RM-48).

LEGAL[third-party-data]: reads public GUS BDL statistics; source terms and attribution are with counsel
(B-012) (RM-48)
LEGAL[scraping]: automated requests to a third-party API under the Postgres-shared quota (RM-48)
GDPR[processor]: no personal data; aggregate territorial statistics only (RM-48)

Weekly by default (`BDL_REFRESH_CRON`, read at worker start). Annual statistics change rarely, so a pass over
finished runs costs no source request; a new source year or a resumed run does the real work. The same pass
publishes each metric-year that passes its coverage gate and leaves the previous release in place otherwise.
"""

from typing import Final

import httpx
import procrastinate
import structlog
from rm_contracts.jobs import BATCH_QUEUE
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.location_repo import PgLocationRepo
from rm_core.settings import Settings, get_settings

from rm_worker.app import app
from rm_worker.clients.bdl import BdlClient, BdlObservationValidator, BdlUnavailable, QuotaWindow
from rm_worker.clients.bdl_quota import PgQuotaGate
from rm_worker.importers.bdl_context import RefreshReport, refresh_context
from rm_worker.tasks.location_context import BDL_BINDINGS

log = structlog.get_logger(__name__)

REFRESH_BDL_CONTEXT_TASK: Final = "rm_worker.tasks.bdl_refresh.refresh_bdl_context"
RETRY = procrastinate.RetryStrategy(max_attempts=3, exponential_wait=900, retry_exceptions={BdlUnavailable})


async def refresh_now(settings: Settings) -> RefreshReport:
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    try:
        sessions = make_sessionmaker(engine)
        gate = PgQuotaGate(
            sessions, windows=(QuotaWindow(limit=settings.bdl_requests_per_minute, seconds=60.0),)
        )
        key = settings.bdl_api_key.get_secret_value()
        async with httpx.AsyncClient(follow_redirects=False) as http:
            return await refresh_context(
                PgLocationRepo(sessions),
                BdlClient(http=http, quota=gate, api_key=key or None),
                reference_version=settings.location_reference_version,
                validator=BdlObservationValidator(bindings=BDL_BINDINGS),
            )
    finally:
        await engine.dispose()


@app.periodic(cron=get_settings().bdl_refresh_cron)
@app.task(
    name=REFRESH_BDL_CONTEXT_TASK, queue=BATCH_QUEUE, queueing_lock=REFRESH_BDL_CONTEXT_TASK, retry=RETRY
)
async def refresh_bdl_context(timestamp: int) -> None:
    report = await refresh_now(get_settings())
    log.info("bdl_refresh_task_done", published=report.published, metrics=len(report.metrics))
