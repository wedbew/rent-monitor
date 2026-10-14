"""Market-data batch jobs (queue `batch`, same worker lane as ops, never the audit lane).

`import_rental_city` fills the comparable-rent store for one city (RM-209). It is deferred on demand by the
audit context when a city has no rents for the current month, one job per city and month (queueing lock), and
retried with backoff when Otodom blocks. A thin result is not an error to retry: the previous month stays.
"""

import procrastinate
import structlog
from rm_contracts.jobs import BATCH_QUEUE, IMPORT_RENTAL_CITY_TASK
from rm_core.comparables import city_slug
from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.deadline import Deadline
from rm_core.settings import get_settings

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
