"""Nightly GDPR retention sweep (RM-30).

GDPR[retention]: purges expired sessions, login tokens, listing snapshots and audit events.
"""

import structlog
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.privacy import purge_expired
from rm_core.settings import get_settings

from rm_worker.app import app

log = structlog.get_logger(__name__)


async def run_sweep() -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        report = await purge_expired(make_sessionmaker(engine), settings)
    finally:
        await engine.dispose()
    log.info("retention_sweep", **report.__dict__)


@app.periodic(cron="17 3 * * *")
@app.task(queue="ops", name="retention_sweep", queueing_lock="retention_sweep")
async def retention_sweep(timestamp: int) -> None:
    await run_sweep()
