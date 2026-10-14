"""Ask for a city's rents to be imported when an audit finds none for the current month (RM-209).

The audit never fetches: it defers one `batch` job per city and month (queueing lock) and carries on, so a
first audit in a new city gets the engine's honest refused rent and the next audit has comparables.
"""

from datetime import UTC, datetime
from typing import Protocol

import structlog
from procrastinate.exceptions import AlreadyEnqueued
from rm_core.comparables import city_slug

from rm_worker.importers.otodom_rental import month_start
from rm_worker.tasks.batch import import_rental_city

log = structlog.get_logger(__name__)


class RentalImportQueue(Protocol):
    async def request(self, city: str, location_id: str) -> None: ...


class ProcrastinateImportQueue:
    async def request(self, city: str, location_id: str) -> None:
        period = month_start(datetime.now(UTC).date())
        lock = f"rental-import:{city_slug(city)}:{period:%Y-%m}"
        try:
            await import_rental_city.configure(queueing_lock=lock).defer_async(
                city=city, location_id=location_id
            )
        except AlreadyEnqueued:
            log.debug("rental_import_already_queued", city=city_slug(city))
