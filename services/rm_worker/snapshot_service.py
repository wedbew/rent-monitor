"""Get a listing snapshot: reuse a fresh shared one, otherwise fetch once and store it (blueprint §2).

LEGAL[scraping]: pages are shared across tenants for 6 hours: two users auditing one flat cost one fetch.
"""

from typing import Protocol
from uuid import UUID

from rm_core.deadline import Deadline
from rm_core.snapshots import FetchedListing, find_fresh_snapshot, store_snapshot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.clients.otodom import Priority


class ListingSource(Protocol):
    """What `OtodomClient` offers; the audit pipeline and its tests depend on this, not on the class."""

    async def fetch_listing(
        self, short_id: str, *, deadline: Deadline, priority: Priority = "interactive"
    ) -> FetchedListing: ...


async def get_snapshot(
    sessionmaker: async_sessionmaker[AsyncSession],
    client: ListingSource,
    short_id: str,
    *,
    deadline: Deadline,
    priority: Priority = "interactive",
) -> UUID:
    async with sessionmaker() as session:
        fresh = await find_fresh_snapshot(session, short_id)
    if fresh is not None:
        return fresh
    fetched = await client.fetch_listing(
        short_id, deadline=deadline, priority=priority
    )  # no transaction held here
    async with sessionmaker() as session, session.begin():
        return await store_snapshot(session, fetched)
