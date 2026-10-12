"""Nightly GDPR retention sweep (RM-30).

GDPR[retention]: purges expired sessions, login tokens, listing snapshots and audit events.
"""

import httpx
import structlog
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.privacy import purge_expired
from rm_core.settings import get_settings

from rm_worker.app import app
from rm_worker.clients.heartbeat import Heartbeat

log = structlog.get_logger(__name__)


async def run_sweep() -> None:
    settings = get_settings()
    engine = make_engine(settings)
    async with httpx.AsyncClient() as http:
        heartbeat = Heartbeat(
            http, settings.betterstack_heartbeat_retention_url.get_secret_value(), "retention"
        )
        try:
            report = await purge_expired(make_sessionmaker(engine), settings)
        except Exception:
            await heartbeat.ping(ok=False)
            raise
        finally:
            await engine.dispose()
        await heartbeat.ping(ok=True)
    log.info("retention_sweep", **report.__dict__)


@app.periodic(cron="17 3 * * *")
@app.task(queue="ops", name="retention_sweep", queueing_lock="retention_sweep")
async def retention_sweep(timestamp: int) -> None:
    await run_sweep()
