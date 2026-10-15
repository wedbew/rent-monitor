"""Billing jobs (queue `ops`, RM-218): process pending Paddle events and reconcile purchases.

`process_billing_events` is woken by the webhook and `billing_sweep` runs every minute, so a lost wake-up, a
dead worker or a missed notification only delays the grant. Both do the same thing: lease pending events
(`SKIP LOCKED`), read each transaction fresh from Paddle and apply it; then recover ambiguous creations and
purchases that have a transaction but no grant. Everything is idempotent and safe in parallel.
"""

import structlog
from rm_contracts.jobs import OPS_QUEUE, PROCESS_BILLING_EVENTS_TASK
from rm_core.billing_events import claim_pending, process_event, reconcile_purchases
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.paddle import PaddleClient, build_paddle_client
from rm_core.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.app import app

log = structlog.get_logger(__name__)
BATCH = 20


async def run_sweep(
    sm: async_sessionmaker[AsyncSession], client: PaddleClient, *, reconcile: bool = True
) -> dict[str, int]:
    """One pass: pending events, then (optionally) reconciliation. Returns counts by outcome."""
    counts: dict[str, int] = {}
    while True:
        ids = await claim_pending(sm, BATCH)
        for event_pk in ids:
            outcome = await process_event(sm, client, event_pk)
            counts[outcome] = counts.get(outcome, 0) + 1
        if len(ids) < BATCH:
            break
    if reconcile:
        for outcome, n in (await reconcile_purchases(sm, client)).items():
            counts[f"reconcile:{outcome}"] = counts.get(f"reconcile:{outcome}", 0) + n
    if counts:
        log.info("billing_sweep", **counts)
    return counts


async def _sweep(*, reconcile: bool) -> None:
    settings = get_settings()
    client = build_paddle_client(settings)
    if client is None:
        return  # billing is disabled: nothing to do
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    try:
        await run_sweep(make_sessionmaker(engine), client, reconcile=reconcile)
    finally:
        await engine.dispose()
        await client.aclose()


@app.task(queue=OPS_QUEUE, name=PROCESS_BILLING_EVENTS_TASK, queueing_lock="billing-events-run")
async def process_billing_events() -> None:
    await _sweep(reconcile=False)


@app.periodic(cron="* * * * *")
@app.task(queue=OPS_QUEUE, name="billing_sweep", queueing_lock="billing_sweep")
async def billing_sweep(timestamp: int) -> None:
    await _sweep(reconcile=True)
