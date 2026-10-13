"""The production `ListingSource`: the Otodom client on `curl_cffi` with Postgres slots and a circuit breaker,
behind the legal kill switch (#187, blueprint §2).

LEGAL[scraping]: fetches Otodom `_next/data` pages with browser TLS impersonation; ToS and EU database-right
exposure are with counsel (RM-187). `LEGAL_SCRAPING_ENABLED=false` ends audits at the fetch without a deploy.
LEGAL[url-analysis]: only the short id parsed from the user's reference is ever requested (RM-187).
"""

from datetime import timedelta

from rm_core.deadline import Deadline
from rm_core.settings import Settings
from rm_core.snapshots import FetchedListing
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.clients.otodom import OtodomClient, Priority, UpstreamBlocked
from rm_worker.clients.otodom_policy import PostgresHostPolicy
from rm_worker.clients.otodom_transport import CurlCffiTransport
from rm_worker.snapshot_service import ListingSource

REQUEST_INTERVAL = timedelta(seconds=1)  # one request per second per host (blueprint §2)


class ScrapingDisabledError(UpstreamBlocked):
    """The operator switched listing fetches off (counsel's kill switch); the audit fails and the credit is
    released."""

    def __init__(self) -> None:
        super().__init__("listing fetching is switched off", retryable=False)


class GatedListingSource:
    def __init__(self, inner: ListingSource, *, enabled: bool) -> None:
        self._inner, self._enabled = inner, enabled

    async def fetch_listing(
        self, short_id: str, *, deadline: Deadline, priority: Priority = "interactive"
    ) -> FetchedListing:
        if not self._enabled:
            raise ScrapingDisabledError
        return await self._inner.fetch_listing(short_id, deadline=deadline, priority=priority)


def build_listing_source(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings) -> ListingSource:
    policy = PostgresHostPolicy(sessionmaker, REQUEST_INTERVAL)
    client = OtodomClient(transport=CurlCffiTransport(), slots=policy, breaker=policy)
    return GatedListingSource(client, enabled=settings.legal_scraping_enabled)
