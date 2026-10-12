"""Nightly AI-budget housekeeping (RM-24): return holds left behind by crashed workers."""

import structlog
from rm_core.ai_budget import sweep_stale_reservations
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.settings import get_settings

from rm_worker.app import app

log = structlog.get_logger(__name__)


async def run_sweep() -> tuple[int, str]:
    engine = make_engine(get_settings())
    try:
        count, total = await sweep_stale_reservations(make_sessionmaker(engine))
    finally:
        await engine.dispose()
    log.info("ai_budget_sweep", reservations=count, usd=str(total))
    return count, str(total)


@app.periodic(cron="23 3 * * *")
@app.task(queue="ops", name="ai_budget_sweep", queueing_lock="ai_budget_sweep")
async def ai_budget_sweep(timestamp: int) -> None:
    await run_sweep()
