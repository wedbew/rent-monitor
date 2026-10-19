"""Daily refresh of the risk-free rate from the ECB (queue `batch`, RM-210, ENGINE-SPEC N-12).

LEGAL[third-party-data]: one public ECB statistic per run, cited as its source; see `clients/macro.py`
(RM-210).
GDPR[processor]: no personal data is sent; the request carries the series key only (RM-210).

Behaviour: a successful answer is stored only if it is at least as new as the stored one, so a repeated or
overlapping run changes nothing (idempotent). A failed or rejected answer keeps the previous value and records
the failure code and time in `risk_free_rate`; the task does not raise, so the next daily run simply tries
again. The monthly series means most daily runs store the same observation.
"""

from datetime import UTC, datetime
from typing import Final, Literal

import httpx
import structlog
from rm_contracts.jobs import BATCH_QUEUE
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.risk_free import record_failure, record_observation
from rm_core.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.app import app
from rm_worker.clients.macro import (
    EcbRateClient,
    MacroError,
    MacroSourceUnavailable,
    MacroValueRejected,
)

log = structlog.get_logger(__name__)

REFRESH_RISK_FREE_TASK: Final = "rm_worker.tasks.macro.refresh_risk_free_rate"
# Once a day, 06:15 UTC: after the ECB's usual morning publication window; one request per run.
REFRESH_CRON: Final = "15 6 * * *"
FAILURE_UNAVAILABLE: Final = "MACRO_SOURCE_UNAVAILABLE"
FAILURE_INVALID: Final = "MACRO_RESPONSE_INVALID"
FAILURE_REJECTED: Final = "MACRO_VALUE_REJECTED"

RefreshOutcome = Literal["stored", "kept", "failed"]


def _failure_code(exc: MacroError) -> str:
    if isinstance(exc, MacroSourceUnavailable):
        return FAILURE_UNAVAILABLE
    if isinstance(exc, MacroValueRejected):
        return FAILURE_REJECTED
    return FAILURE_INVALID  # MacroResponseInvalid: the answer is not the documented shape


async def refresh_risk_free_now(
    sessionmaker: async_sessionmaker[AsyncSession], client: EcbRateClient, now: datetime
) -> RefreshOutcome:
    """One refresh. Returns `stored` (written), `kept` (an older observation than the stored one, ignored) or
    `failed` (the previous value stays, the failure is recorded). Never raises for a source failure."""
    try:
        observation = await client.latest()
    except MacroError as exc:
        code = _failure_code(exc)
        log.warning("risk_free_refresh_failed", code=code, error_type=type(exc).__name__)
        async with sessionmaker() as session, session.begin():
            await record_failure(session, code=code, now=now)
        return "failed"
    async with sessionmaker() as session, session.begin():
        written = await record_observation(
            session, observation_period=observation.period, rate=observation.rate, now=now
        )
    log.info("risk_free_refresh_done", observation_period=str(observation.period), stored=written)
    return "stored" if written else "kept"


@app.periodic(cron=REFRESH_CRON)
@app.task(name=REFRESH_RISK_FREE_TASK, queue=BATCH_QUEUE, queueing_lock=REFRESH_RISK_FREE_TASK)
async def refresh_risk_free_rate(timestamp: int) -> None:
    engine = make_engine(get_settings(), pool_size=1, max_overflow=0)
    try:
        async with httpx.AsyncClient() as http:
            await refresh_risk_free_now(
                make_sessionmaker(engine),
                EcbRateClient(http),
                datetime.fromtimestamp(timestamp, UTC),
            )
    finally:
        await engine.dispose()
