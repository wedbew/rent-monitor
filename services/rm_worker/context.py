"""The production `ContextProvider`: rent from the comparable-rent store, the risk-free rate from settings
(#187, blueprint §2 stage `context`).

LEGAL[third-party-data]: rents derive from stored Otodom rental sidecars (RM-106, RM-187).
Invariant 2 (asking is not deed): the rent comes from `otodom_rental` rows only and is labelled `asking`.
The estimate is `deal_analyzer.rent.estimate_rent` (deterministic Python); this class only loads inputs.
A city with too few comparables yields the engine's own refused estimate (rent 0 plus its warnings), never a
guess.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import structlog
from deal_analyzer import Listing, RentInput
from deal_analyzer.rent import RentComparable, estimate_rent
from rm_core.comparables import ComparableCache, city_slug, load_comparables
from rm_core.deadline import Deadline
from rm_core.risk_free import (
    ECB_SERIES_KEY,
    SETTING_SOURCE,
    SOURCE_ECB,
    RiskFreeRate,
    is_fresh,
    is_plausible,
    load_stored,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.importers.demand import RentalImportQueue
from rm_worker.importers.otodom_rental import month_start

log = structlog.get_logger(__name__)


class ContextUnavailableError(RuntimeError):
    """An input the engine needs is missing: the audit ends `CONTEXT_UNAVAILABLE`, credit released."""


class MarketContext:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        risk_free: Decimal | None,
        cache: ComparableCache | None = None,
        import_queue: RentalImportQueue | None = None,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._sm = sessionmaker
        self._risk_free = risk_free
        self._cache = cache or ComparableCache()
        self._queue = import_queue
        self._today = today

    async def rent_input(self, listing: Listing, *, deadline: Deadline) -> RentInput:
        if not listing.city:
            raise ContextUnavailableError("the listing has no city to anchor rent on")
        async with self._sm() as session:
            found = await load_comparables(session, city_slug(listing.city), self._cache)
        await self._request_import_if_stale(listing, found.period, bool(found.comparables))
        comparables = [
            RentComparable(monthly_rent_pln=c.monthly_rent_pln, area_m2=c.area_m2) for c in found.comparables
        ]
        return estimate_rent(listing.area_m2, comparables).to_input()

    async def _request_import_if_stale(self, listing: Listing, period: date | None, has_rows: bool) -> None:
        """No rents, or none for this month: queue an import (batch lane). Never fails or delays the audit."""
        if self._queue is None or not listing.city or not listing.location_id:
            return
        if has_rows and period is not None and period >= month_start(self._today()):
            return
        try:
            await self._queue.request(listing.city, listing.location_id)
        except Exception:
            log.warning("rental_import_request_failed", city=city_slug(listing.city), exc_info=True)

    async def risk_free_rate(self, *, deadline: Deadline) -> RiskFreeRate:
        """Order (RM-210): the stored ECB value while fresh (<= MAX_AGE_DAYS after its month), else the
        RISK_FREE_RATE setting, else refuse. The rate used and its source/date go onto the audit row."""
        async with self._sm() as session:
            stored = await load_stored(session)
        today = self._today()
        if stored is not None and stored.rate is not None and stored.observation_period is not None:
            if is_fresh(stored.observation_period, today) and is_plausible(stored.rate):
                return RiskFreeRate(
                    rate=stored.rate,
                    source=f"{SOURCE_ECB}:{ECB_SERIES_KEY}",
                    as_of=stored.observation_period,
                )
            log.warning(
                "risk_free_rate_stored_not_used",
                observation_period=str(stored.observation_period),
                fresh=is_fresh(stored.observation_period, today),
            )
        if self._risk_free is not None:
            return RiskFreeRate(rate=self._risk_free, source=SETTING_SOURCE, as_of=None)
        raise ContextUnavailableError("no fresh stored risk-free rate and RISK_FREE_RATE is not set")
