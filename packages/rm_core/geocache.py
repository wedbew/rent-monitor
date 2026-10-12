"""Read-through cache for OpenStreetMap lookups (geocoding and points of interest).

LEGAL[third-party-data]: caching is required by the Nominatim usage policy and keeps us inside 1
request per second.
Keys are hashes of a normalised request (address text or rounded coordinates); nothing here identifies a user.
"""

import hashlib
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import GeoCache

GEOCODE_TTL = timedelta(days=90)
POI_TTL = timedelta(days=30)


def geocode_key(address: str) -> str:
    normalised = " ".join(address.casefold().split())
    return hashlib.sha256(f"geocode|{normalised}".encode()).hexdigest()


def poi_key(latitude: Decimal, longitude: Decimal, radius_m: int) -> str:
    """Coordinates are rounded to 4 decimals (about 11 m) so near-identical flats share one lookup."""
    rounded = f"{latitude.quantize(Decimal('0.0001'))}|{longitude.quantize(Decimal('0.0001'))}|{radius_m}"
    return hashlib.sha256(f"poi|{rounded}".encode()).hexdigest()


async def cache_get(session: AsyncSession, key: str) -> dict[str, Any] | None:
    return await session.scalar(
        select(GeoCache.payload).where(GeoCache.key == key, GeoCache.expires_at > func.clock_timestamp())
    )


async def cache_put(
    session: AsyncSession, key: str, kind: str, payload: dict[str, Any], ttl: timedelta
) -> None:
    expires = func.clock_timestamp() + literal(ttl)
    stmt = insert(GeoCache).values(key=key, kind=kind, payload=payload, expires_at=expires)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[GeoCache.key],
            set_={"payload": payload, "fetched_at": func.clock_timestamp(), "expires_at": expires},
        )
    )
