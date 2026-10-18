"""Market-data batch jobs (queue `batch`, same worker lane as ops, never the audit lane).

`import_rental_city` fills the comparable-rent store for one city (RM-209). It is deferred on demand by the
audit context when a city has no rents for the current month, one job per city and month (queueing lock), and
retried with backoff when Otodom blocks. A thin result is not an error to retry: the previous month stays.
"""

import procrastinate
import structlog
from rm_contracts.jobs import BATCH_QUEUE, IMPORT_RENTAL_CITY_TASK, OPS_QUEUE
from rm_core.comparables import city_slug
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.deadline import Deadline
from rm_core.market_corpus import PgCorpus
from rm_core.settings import get_settings

from rm_worker.app import app
from rm_worker.clients.otodom import FetchError
from rm_worker.importers.otodom_corpus import (
    CATALOGUE_VERSION,
    CorpusImporter,
    PgLocationLock,
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
CORPUS_DISPATCH_TASK = "rm_worker.tasks.batch.dispatch_corpus_nightly"
CORPUS_DISPATCH_CRON = "0 1 * * *"  # 01:00 UTC every day; DST-free (docs/OTODOM-NIGHTLY-IMPORT.md section 7)
CORPUS_RETRY = procrastinate.RetryStrategy(
    max_attempts=2, exponential_wait=900, retry_exceptions={FetchError}
)


@app.task(
    name=CORPUS_LOCATION_TASK,
    queue=BATCH_QUEUE,
    retry=CORPUS_RETRY,
)
async def sync_corpus_location(location_id: str, catalogue_version: int = CATALOGUE_VERSION) -> None:
    """Bootstrap or catch up one catalogue location. A refused or cut-off run ends `incomplete` and the
    prior checkpoint stays; the next night's window starts before the watermark, so nothing is skipped."""
    settings = get_settings()
    engine = make_engine(settings, pool_size=3, max_overflow=0)  # one connection holds the location lock
    try:
        sessionmaker = make_sessionmaker(engine)
        corpus = PgCorpus(sessionmaker)
        catalogue = await corpus.get_catalogue(catalogue_version)
        entry = (
            next((e for e in catalogue.locations if e.location_id == location_id), None)
            if catalogue
            else None
        )
        if entry is None or not entry.launch_enabled:
            log.warning("corpus_location_unknown", location_id=location_id, version=catalogue_version)
            return
        importer = CorpusImporter(
            corpus, build_search_source(sessionmaker, settings), lock=PgLocationLock(engine)
        )
        for outcome in await importer.sync_location(entry):
            log.info(
                "corpus_location_synced",
                location_id=location_id,
                state=outcome.state,
                category=outcome.error_category,
                inserted=outcome.inserted,
            )
    finally:
        await engine.dispose()


@app.periodic(cron=CORPUS_DISPATCH_CRON)
@app.task(name=CORPUS_DISPATCH_TASK, queue=OPS_QUEUE, queueing_lock=CORPUS_DISPATCH_TASK)
async def dispatch_corpus_nightly(timestamp: int) -> None:
    """Defer one `batch` job per enabled, due location of the catalogue. Without a seeded catalogue (the
    owner-verified artifact is still open, B-023) this does nothing."""
    settings = get_settings()
    engine = make_engine(settings, pool_size=2, max_overflow=0)
    try:
        sessionmaker = make_sessionmaker(engine)
        corpus = PgCorpus(sessionmaker)
        catalogue = await corpus.get_catalogue(CATALOGUE_VERSION)
        if catalogue is None:
            log.info("corpus_dispatch_no_catalogue", version=CATALOGUE_VERSION)
            return
        importer = CorpusImporter(corpus, build_search_source(sessionmaker, settings))
        due = await importer.due_locations(catalogue)
        for location_id in due:
            await sync_corpus_location.defer_async(
                location_id=location_id, catalogue_version=CATALOGUE_VERSION
            )
        log.info(
            "corpus_dispatch_done", due=len(due), enabled=sum(e.launch_enabled for e in catalogue.locations)
        )
    finally:
        await engine.dispose()
