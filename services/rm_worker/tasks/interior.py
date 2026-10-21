"""Interior media retention: expire projects and abandoned uploads, then delete queued bytes (RM-448).

GDPR[retention]: projects 30 days after creation, pending and failed uploads 7 days (owner, 2026-10-19).
GDPR[erasure]: also drains the keys queued by account erasure; an unreachable store keeps them queued.
LEGAL[images]: deletes the person's images from the private media bucket.
"""

from decimal import Decimal
from uuid import UUID

import httpx
import structlog
from rm_contracts.generation import GenerationError, GenerationState
from rm_contracts.jobs import RUN_INTERIOR_GENERATION_TASK
from rm_core import interior
from rm_core import interior_generation as ops
from rm_core.ai_budget import CallUsage, PostgresBudgetGate
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.object_store import ObjectStore, S3ObjectStore
from rm_core.settings import Settings, get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker import interior_generation as flow
from rm_worker.app import app
from rm_worker.clients.image_gen import FakeImageGenerator, ImageGenerator, OpenRouterImageGenerator

log = structlog.get_logger(__name__)
MAX_DRAIN_ROUNDS = 10  # 10 x 200 objects per run; the next run continues


async def run_interior_sweep(
    sessionmaker: async_sessionmaker[AsyncSession], store: ObjectStore | None
) -> tuple[interior.SweepReport, int]:
    report = await interior.sweep_expired(sessionmaker)
    deleted = 0
    if store is not None:
        for _ in range(MAX_DRAIN_ROUNDS):
            done = await interior.drain_tombstones(sessionmaker, store)
            deleted += done
            if done < interior.TOMBSTONE_BATCH:
                break
    return report, deleted


@app.periodic(cron="*/30 * * * *")
@app.task(queue="ops", name="interior_media_sweep", queueing_lock="interior_media_sweep")
async def interior_media_sweep(timestamp: int) -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        store = S3ObjectStore.from_settings(settings) if settings.media_store_configured else None
        report, deleted = await run_interior_sweep(make_sessionmaker(engine), store)
    finally:
        await engine.dispose()
    log.info(
        "interior_media_sweep",
        projects=report.projects,
        abandoned_media=report.abandoned_media,
        objects_deleted=deleted,
        store_configured=store is not None,
        legal_tags=["images", "retention"],
    )


def build_generator(settings: Settings, http: httpx.AsyncClient) -> ImageGenerator | None:
    """The configured image model client, or None while generation is off or its key is missing."""
    if settings.interior_image_provider == "fake":
        return FakeImageGenerator()
    key = settings.openrouter_api_key.get_secret_value()
    if settings.interior_image_provider == "openrouter" and key:
        return OpenRouterImageGenerator(http, key, settings.openrouter_base_url)
    return None


class _Recovery:
    def __init__(self, gate: PostgresBudgetGate) -> None:
        self._gate = gate

    async def settle(self, reservation_id: UUID, estimate: Decimal, model: str) -> None:
        await self._gate.settle(reservation_id, estimate, CallUsage(model=model, estimated=True))

    async def release(self, reservation_id: UUID) -> None:
        await self._gate.release(reservation_id)


@app.task(name=RUN_INTERIOR_GENERATION_TASK, queue="ops")
async def run_generation(generation_id: str) -> None:
    """One generation. Deferred by the API after the operation row committed; redelivery is harmless because
    only the first claim (queued -> running) proceeds. Runs on the `ops` lane (two slots), bounded by the
    operation deadline."""
    settings = get_settings()
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        async with httpx.AsyncClient() as http:
            generator = build_generator(settings, http)
            if generator is None or not settings.media_store_configured:
                if await ops.claim(sm, UUID(generation_id)) is not None:
                    await ops.finish(
                        sm,
                        UUID(generation_id),
                        GenerationState.failed,
                        error=GenerationError.PROVIDER_UNAVAILABLE,
                    )
                return
            deps = flow.Deps(
                sm=sm,
                store=S3ObjectStore.from_settings(settings),
                generator=generator,
                gate=PostgresBudgetGate(sm, monthly_cap_usd=settings.openrouter_monthly_budget_usd),
                settings=settings,
            )
            await flow.run_generation(deps, UUID(generation_id))
    finally:
        await engine.dispose()


@app.periodic(cron="* * * * *")
@app.task(queue="ops", name="interior_generation_reconcile", queueing_lock="interior_generation_reconcile")
async def interior_generation_reconcile(timestamp: int) -> None:
    """Close operations whose worker died: unsent ones release their hold, sent ones keep the estimate."""
    settings = get_settings()
    engine = make_engine(settings, pool_size=1, max_overflow=0)
    sm = make_sessionmaker(engine)
    try:
        recovery = _Recovery(PostgresBudgetGate(sm, monthly_cap_usd=settings.openrouter_monthly_budget_usd))
        closed = await flow.reconcile(sm, recovery)
    finally:
        await engine.dispose()
    if closed:
        log.error("interior_generation_reconciled", closed=closed)
