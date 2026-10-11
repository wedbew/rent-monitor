"""Listing snapshots shared across tenants for 6 hours, keyed by (otodom_id, content hash) (blueprint §2).

LEGAL[scraping]: stores fetched third-party page data and shares it across tenants.
GDPR[personal-data]: the payload may contain seller names or phones; retention and erasure: RM-30.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import Listing, ListingSnapshot

SNAPSHOT_TTL = timedelta(hours=6)


@dataclass(frozen=True)
class FetchedListing:
    otodom_id: str
    url: str
    ad: dict[str, Any]
    content_sha256: str


def content_hash(ad: dict[str, Any]) -> str:
    """Stable across key order and whitespace, so the same ad always hashes the same."""
    canonical = json.dumps(ad, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def find_fresh_snapshot(session: AsyncSession, otodom_id: str) -> UUID | None:
    return await session.scalar(
        select(ListingSnapshot.id)
        .where(
            ListingSnapshot.otodom_id == otodom_id,
            ListingSnapshot.fetched_at > func.clock_timestamp() - literal(SNAPSHOT_TTL),
        )
        .order_by(ListingSnapshot.fetched_at.desc())
        .limit(1)
    )


async def store_snapshot(session: AsyncSession, fetched: FetchedListing) -> UUID:
    """Upsert the listing identity and the snapshot; the same content only refreshes `fetched_at`."""
    await session.execute(
        insert(Listing)
        .values(otodom_id=fetched.otodom_id, url=fetched.url)
        .on_conflict_do_update(
            index_elements=[Listing.otodom_id], set_={"url": fetched.url, "last_seen_at": func.now()}
        )
    )
    snapshot_id = await session.scalar(
        insert(ListingSnapshot)
        .values(otodom_id=fetched.otodom_id, content_sha256=fetched.content_sha256, payload=fetched.ad)
        .on_conflict_do_update(
            index_elements=[ListingSnapshot.otodom_id, ListingSnapshot.content_sha256],
            set_={"fetched_at": func.clock_timestamp()},
        )
        .returning(ListingSnapshot.id)
    )
    assert snapshot_id is not None  # noqa: S101  (RETURNING always yields a row for an upsert)
    return snapshot_id
