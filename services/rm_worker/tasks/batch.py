"""Market-data batch jobs (queue `batch`, same worker lane as ops, never the audit lane).

`import_rental_city` fills the comparable-rent store for one city (RM-209). It is deferred on demand by the
audit context when a city has no rents for the current month, one job per city and month (queueing lock), and
retried with backoff when Otodom blocks. A thin result is not an error to retry: the previous month stays.
"""

from collections.abc import Callable
from datetime import UTC, datetime

import procrastinate
import structlog
from deal_analyzer.market_stats import summarise_asking
from rm_contracts.jobs import (
    BATCH_QUEUE,
    IMPORT_RENTAL_CITY_TASK,
    OPS_QUEUE,
    PUBLISH_MARKET_SUMMARIES_TASK,
)
from rm_core.comparables import city_slug
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.deadline import Deadline
from rm_core.legal import LegalTag, tag_names
from rm_core.market_corpus import PgCorpus
from rm_core.market_history import PgMarketHistory
from rm_core.settings import Settings, get_settings

from rm_worker.app import app
from rm_worker.clients.otodom import FetchError
from rm_worker.importers.otodom_corpus import (
    CorpusSearchSource,
    DistrictSweep,
    PgLocationLock,
    RunOutcome,
    importer_from_settings,
)
from rm_worker.importers.otodom_rental import ImportTooThinError, import_city_rentals
from rm_worker.listing_source import build_search_source

log = structlog.get_logger(__name__)
IMPORT_DEADLINE_S = 300.0
RETRY = procrastinate.RetryStrategy(max_attempts=3, exponential_wait=300, retry_exceptions={FetchError})


@app.task(name=IMPORT_RENTAL_CITY_TASK, queue=BATCH_QUEUE, retry=RETRY)
async def import_rental_city(city: str, location_id: str) -> None:
    settings = get_settings()
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    try:
        sessionmaker = make_sessionmaker(engine)
        source = build_search_source(sessionmaker, settings)
        try:
            await import_city_rentals(
                sessionmaker,
                source,
                city_name=city,
                location_id=location_id,
                deadline=Deadline.after(IMPORT_DEADLINE_S),
            )
        except ImportTooThinError:
            log.warning("rental_import_skipped_thin", city=city_slug(city))  # keep the last good month
    finally:
        await engine.dispose()


# --- Otodom rental corpus (RM-392, OTO-02/03) ---------------------------------------------------------
# LEGAL[scraping]: these jobs page through Otodom search results (insert-once corpus); the gated search source
# honours LEGAL_SCRAPING_ENABLED, so counsel can stop them without a deploy (RM-392).
# LEGAL[third-party-data]: whitelisted analytical offer fields only (RM-392).
# Task names are local constants, not in rm_contracts.jobs: only the worker defers them (RM-392-L05).

CORPUS_LOCATION_TASK = "rm_worker.tasks.batch.sync_corpus_location"
DISTRICT_SWEEP_TASK = "rm_worker.tasks.batch.sweep_market_districts"
CORPUS_DISPATCH_TASK = "rm_worker.tasks.batch.dispatch_corpus_nightly"
# The periodic cron is a decorator argument, so it is read once when the worker process starts: change
# OTODOM_MARKET_NIGHTLY_CRON and restart the worker (RM-209). Default 01:00 UTC, DST-free (section 7).
CORPUS_DISPATCH_CRON = get_settings().otodom_market_nightly_cron
CORPUS_RETRY = procrastinate.RetryStrategy(
    max_attempts=2, exponential_wait=900, retry_exceptions={FetchError}
)


async def sync_location_now(
    settings: Settings,
    location_id: str,
    *,
    catalogue_version: int | None = None,
    source: CorpusSearchSource | None = None,
    now: datetime | None = None,
    may_fetch: Callable[[], bool] | None = None,
) -> list[RunOutcome]:
    """Bootstrap or catch up one location of the configured catalogue (RM-209).

    The import switch is checked first: when it is off nothing is read, no source is built and no request is
    sent. A refused, cut-off or night-window-stopped run ends `incomplete` and the prior checkpoint stays; the
    next night's window starts before the watermark, so nothing is skipped."""
    if not settings.otodom_market_import_enabled:
        log.info("corpus_import_disabled", location_id=location_id)
        return []
    version = settings.otodom_market_catalogue_version if catalogue_version is None else catalogue_version
    engine = make_engine(settings, pool_size=3, max_overflow=0)  # one connection holds the location lock
    try:
        sessionmaker = make_sessionmaker(engine)
        corpus = PgCorpus(sessionmaker)
        catalogue = await corpus.get_catalogue(version)
        entry = (
            next((e for e in catalogue.locations if e.location_id == location_id), None)
            if catalogue
            else None
        )
        if entry is None or not entry.launch_enabled:
            log.warning("corpus_location_unknown", location_id=location_id, version=version)
            return []
        importer = importer_from_settings(
            corpus,
            source if source is not None else build_search_source(sessionmaker, settings),
            settings,
            lock=PgLocationLock(engine),
            may_fetch=may_fetch,
        )
        outcomes = await importer.sync_location(entry, now=now)
        for outcome in outcomes:
            log.info(
                "corpus_location_synced",
                location_id=location_id,
                state=outcome.state,
                category=outcome.error_category,
                inserted=outcome.inserted,
            )
        return outcomes
    finally:
        await engine.dispose()


async def sweep_districts_now(
    settings: Settings,
    location_id: str,
    *,
    catalogue_version: int | None = None,
    source: CorpusSearchSource | None = None,
    may_fetch: Callable[[], bool] | None = None,
) -> DistrictSweep | None:
    """Attach the source's districts to one place's stored offers (RM-439). Same switches, throttle, breaker
    and location lock as the import: nothing is read when the import is off, and a place being imported is
    skipped (`None`), never raced."""
    if not settings.otodom_market_import_enabled:
        log.info("district_sweep_disabled", location_id=location_id)
        return None
    version = settings.otodom_market_catalogue_version if catalogue_version is None else catalogue_version
    engine = make_engine(settings, pool_size=3, max_overflow=0)
    try:
        sessionmaker = make_sessionmaker(engine)
        corpus = PgCorpus(sessionmaker)
        catalogue = await corpus.get_catalogue(version)
        entry = (
            next((e for e in catalogue.locations if e.location_id == location_id), None)
            if catalogue
            else None
        )
        if entry is None or not entry.launch_enabled:
            log.warning("district_sweep_location_unknown", location_id=location_id, version=version)
            return None
        importer = importer_from_settings(
            corpus,
            source if source is not None else build_search_source(sessionmaker, settings),
            settings,
            lock=PgLocationLock(engine),
            may_fetch=may_fetch,
        )
        lock = importer.lock
        assert lock is not None  # noqa: S101
        async with lock.hold(location_id) as owned:
            if not owned:
                return None
            result = await importer.sweep_districts(entry)
        log.info(
            "district_sweep_done",
            location_id=location_id,
            state=result.state,
            pages=result.pages,
            attached=result.attached,
            legal_tags=tag_names(LegalTag.scraping, LegalTag.third_party_data),
        )
        return result
    finally:
        await engine.dispose()


@app.task(name=DISTRICT_SWEEP_TASK, queue=BATCH_QUEUE, retry=CORPUS_RETRY)
async def sweep_market_districts(location_id: str, catalogue_version: int | None = None) -> None:
    await sweep_districts_now(get_settings(), location_id, catalogue_version=catalogue_version)


@app.task(
    name=CORPUS_LOCATION_TASK,
    queue=BATCH_QUEUE,
    retry=CORPUS_RETRY,
)
async def sync_corpus_location(location_id: str, catalogue_version: int | None = None) -> None:
    await sync_location_now(get_settings(), location_id, catalogue_version=catalogue_version)


async def dispatch_nightly_now(settings: Settings, *, now: datetime | None = None) -> list[str]:
    """Defer one `batch` job per enabled, due location of the configured catalogue (RM-209).

    The import switch is checked first: when it is off nothing is deferred. Without a seeded catalogue (the
    owner-verified artifact is still open, B-023) this does nothing."""
    if not settings.otodom_market_import_enabled:
        log.info("corpus_dispatch_disabled")
        return []
    version = settings.otodom_market_catalogue_version
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    try:
        sessionmaker = make_sessionmaker(engine)
        corpus = PgCorpus(sessionmaker)
        catalogue = await corpus.get_catalogue(version)
        if catalogue is None:
            log.info("corpus_dispatch_no_catalogue", version=version)
            return []
        importer = importer_from_settings(corpus, build_search_source(sessionmaker, settings), settings)
        due = await importer.due_locations(catalogue, now)
        for location_id in due:
            await sync_corpus_location.defer_async(location_id=location_id, catalogue_version=version)
        log.info(
            "corpus_dispatch_done",
            due=len(due),
            enabled=sum(e.launch_enabled for e in catalogue.locations),
            version=version,
        )
        return due
    finally:
        await engine.dispose()


@app.periodic(cron=CORPUS_DISPATCH_CRON)
@app.task(name=CORPUS_DISPATCH_TASK, queue=OPS_QUEUE, queueing_lock=CORPUS_DISPATCH_TASK)
async def dispatch_corpus_nightly(timestamp: int) -> None:
    await dispatch_nightly_now(get_settings())


async def publish_summaries_now(settings: Settings, now: datetime) -> dict[str, int]:
    """Publish today's asking-rent summaries for every launch-enabled location that finished its bootstrap.

    LEGAL[third-party-data]: aggregates Otodom asking rents already stored; fetches nothing (RM-395).
    Gated by `OTODOM_MARKET_IMPORT_ENABLED`. One failing location is logged and never blocks the rest."""
    counts = {"published": 0, "skipped": 0, "failed": 0}
    if not settings.otodom_market_import_enabled:
        log.info("market_summaries_disabled")
        return counts
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    try:
        sessionmaker = make_sessionmaker(engine)
        catalogue = await PgCorpus(sessionmaker).get_catalogue(settings.otodom_market_catalogue_version)
        if catalogue is None:
            log.info("market_summaries_no_catalogue", version=settings.otodom_market_catalogue_version)
            return counts
        history = PgMarketHistory(
            sessionmaker,
            fresh_hours=settings.otodom_market_fresh_hours,
            stale_hours=settings.otodom_market_stale_hours,
        )
        ids = [e.location_id for e in catalogue.locations if e.launch_enabled]
        results = await history.publish_all(
            ids, now.astimezone(UTC).date(), now=now, summarise=summarise_asking
        )
        for location_id, result in results.items():
            if isinstance(result, Exception):
                counts["failed"] += 1
                log.error("market_summary_failed", location_id=location_id, error=type(result).__name__)
            elif result.status == "published":
                counts["published"] += 1
            else:
                counts["skipped"] += 1
    finally:
        await engine.dispose()
    log.info("market_summaries", legal_tags=["third-party-data", "republication"], **counts)
    return counts


# Read at worker start, like CORPUS_DISPATCH_CRON. Default 05:30 UTC, after the night window end (RM-209).
@app.periodic(cron=get_settings().otodom_market_summary_cron)
@app.task(name=PUBLISH_MARKET_SUMMARIES_TASK, queue=BATCH_QUEUE, queueing_lock="publish_market_summaries")
async def publish_market_summaries(timestamp: int) -> None:
    await publish_summaries_now(get_settings(), datetime.fromtimestamp(timestamp, UTC))
