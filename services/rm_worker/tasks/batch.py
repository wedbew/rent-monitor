"""Market-data batch jobs (queue `batch`, same worker lane as ops, never the audit lane).

`import_rental_city` fills the comparable-rent store for one city (RM-209). It is deferred on demand by the
audit context when a city has no rents for the current month, one job per city and month (queueing lock), and
retried with backoff when Otodom blocks. A thin result is not an error to retry: the previous month stays.
"""

from datetime import UTC, datetime

import procrastinate
import structlog
from deal_analyzer.market_stats import summarise_asking
from rm_contracts.jobs import BATCH_QUEUE, IMPORT_RENTAL_CITY_TASK, PUBLISH_MARKET_SUMMARIES_TASK
from rm_core.comparables import city_slug
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.deadline import Deadline
from rm_core.market_corpus import PgCorpus
from rm_core.market_history import PgMarketHistory
from rm_core.settings import Settings, get_settings

from rm_worker.app import app
from rm_worker.clients.otodom import FetchError
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


@app.periodic(cron="30 5 * * *")  # after the default night window end (05:00 UTC); the importer owns 01:00
@app.task(name=PUBLISH_MARKET_SUMMARIES_TASK, queue=BATCH_QUEUE, queueing_lock="publish_market_summaries")
async def publish_market_summaries(timestamp: int) -> None:
    await publish_summaries_now(get_settings(), datetime.fromtimestamp(timestamp, UTC))
