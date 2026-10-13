"""The production `ContextProvider`: rent from the comparable-rent store, the risk-free rate from settings
(#187, blueprint §2 stage `context`).

LEGAL[third-party-data]: rents derive from stored Otodom rental sidecars (RM-106, RM-187).
Invariant 2 (asking is not deed): the rent comes from `otodom_rental` rows only and is labelled `asking`.
The estimate is `deal_analyzer.rent.estimate_rent` (deterministic Python); this class only loads inputs.
A city with too few comparables yields the engine's own refused estimate (rent 0 plus its warnings), never a
guess.
"""

from decimal import Decimal

from deal_analyzer import Listing, RentInput
from deal_analyzer.rent import RentComparable, estimate_rent
from rm_core.comparables import ComparableCache, city_slug, load_comparables
from rm_core.deadline import Deadline
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class ContextUnavailableError(RuntimeError):
    """An input the engine needs is missing: the audit ends `CONTEXT_UNAVAILABLE`, credit released."""


class MarketContext:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        risk_free: Decimal | None,
        cache: ComparableCache | None = None,
    ) -> None:
        self._sm = sessionmaker
        self._risk_free = risk_free
        self._cache = cache or ComparableCache()

    async def rent_input(self, listing: Listing, *, deadline: Deadline) -> RentInput:
        if not listing.city:
            raise ContextUnavailableError("the listing has no city to anchor rent on")
        async with self._sm() as session:
            found = await load_comparables(session, city_slug(listing.city), self._cache)
        comparables = [
            RentComparable(monthly_rent_pln=c.monthly_rent_pln, area_m2=c.area_m2) for c in found.comparables
        ]
        return estimate_rent(listing.area_m2, comparables).to_input()

    async def risk_free_rate(self, *, deadline: Deadline) -> Decimal:
        if self._risk_free is None:
            raise ContextUnavailableError("RISK_FREE_RATE is not set")
        return self._risk_free
