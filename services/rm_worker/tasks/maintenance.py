"""Nightly and periodic maintenance (blueprint §4.7; docs/OBSERVABILITY-SPEC.md sections 4 and 5), queue
`ops`.

- `ledger_check`: credit balance must equal the sum of the ledger and of the available units of the
  credit lots (and a lot's reserved units the sum of its allocations) for every account. Any mismatch is an
error event
  and a failed heartbeat; no mismatch pings the heartbeat. Read only, it never changes a balance.
- `remove_old_jobs_ops` / `remove_old_jobs_other`: delete finished and failed Procrastinate jobs. The `ops`
queue carries
  mail jobs whose arguments hold a magic-link token, so its rows go after a day (L-011).
- `monitor`: queue lag, database connections and cgroup memory against their budgets; warnings go to Sentry.
"""

import httpx
import sentry_sdk
import structlog
from procrastinate import JobContext, builtin_tasks
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.ledger import ledger_mismatches, lot_mismatches
from rm_core.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker import monitors
from rm_worker.app import app
from rm_worker.clients.heartbeat import Heartbeat, HeartbeatSink

log = structlog.get_logger(__name__)
OPS_JOB_MAX_HOURS = 24  # L-011: rows holding a magic-link token live at most a day
OTHER_JOB_MAX_HOURS = (
    24 * 7
)  # failed audit/batch jobs stay a week for inspection; the audit row is the record
MAX_IDS_LOGGED = 20


async def run_ledger_check(
    sessionmaker: async_sessionmaker[AsyncSession], heartbeat: HeartbeatSink
) -> list[str]:
    async with sessionmaker() as session:
        mismatched = sorted(set(await ledger_mismatches(session)) | set(await lot_mismatches(session)))
    if mismatched:
        # User ids are pseudonymous UUIDs; the Sentry message carries only the count.
        log.error("ledger_mismatch", count=len(mismatched), user_ids=mismatched[:MAX_IDS_LOGGED])
        sentry_sdk.capture_message(f"ledger mismatch on {len(mismatched)} account(s)", level="error")
        await heartbeat.ping(ok=False)
    else:
        log.info("ledger_check_ok")
        await heartbeat.ping(ok=True)
    return mismatched


async def run_monitor(sessionmaker: async_sessionmaker[AsyncSession]) -> list[monitors.Alert]:
    async with sessionmaker() as session:
        reading = await monitors.read(session)
    alerts = monitors.evaluate(reading)
    for alert in alerts:
        log.warning("ops_alert", key=alert.key, message=alert.message)
        sentry_sdk.capture_message(alert.message, level="warning")
    log.info("monitor", connections=reading.connections, queues=len(reading.queue_age_s), alerts=len(alerts))
    return alerts


@app.periodic(cron="41 3 * * *")
@app.task(queue="ops", name="ledger_check", queueing_lock="ledger_check")
async def ledger_check(timestamp: int) -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        async with httpx.AsyncClient() as http:
            heartbeat = Heartbeat(
                http, settings.betterstack_heartbeat_ledger_url.get_secret_value(), "ledger"
            )
            await run_ledger_check(make_sessionmaker(engine), heartbeat)
    finally:
        await engine.dispose()


@app.periodic(cron="*/5 * * * *")
@app.task(queue="ops", name="monitor", queueing_lock="monitor")
async def monitor(timestamp: int) -> None:
    engine = make_engine(get_settings())
    try:
        await run_monitor(make_sessionmaker(engine))
    finally:
        await engine.dispose()


@app.periodic(cron="31 3 * * *")
@app.task(queue="ops", name="remove_old_jobs_ops", queueing_lock="remove_old_jobs_ops", pass_context=True)
async def remove_old_jobs_ops(context: JobContext, timestamp: int) -> None:
    await builtin_tasks.remove_old_jobs(
        context,
        max_hours=OPS_JOB_MAX_HOURS,
        queue="ops",
        remove_failed=True,
        remove_cancelled=True,
        remove_aborted=True,
    )


@app.periodic(cron="33 3 * * *")
@app.task(queue="ops", name="remove_old_jobs_other", queueing_lock="remove_old_jobs_other", pass_context=True)
async def remove_old_jobs_other(context: JobContext, timestamp: int) -> None:
    await builtin_tasks.remove_old_jobs(
        context,
        max_hours=OTHER_JOB_MAX_HOURS,
        remove_failed=True,
        remove_cancelled=True,
        remove_aborted=True,
    )
