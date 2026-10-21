"""Interior media retention: expire projects and abandoned uploads, then delete queued bytes (RM-448).

GDPR[retention]: projects 30 days after creation, pending and failed uploads 7 days (owner, 2026-10-19).
GDPR[erasure]: also drains the keys queued by account erasure; an unreachable store keeps them queued.
LEGAL[images]: deletes the person's images from the private media bucket.
"""

import structlog
from rm_core import interior
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.object_store import ObjectStore, S3ObjectStore
from rm_core.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.app import app

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
