"""Cached geocoding and points of interest for the audit `context` stage.

LEGAL[third-party-data]: results come from OpenStreetMap (ODbL); see `rm_worker.clients.osm`.
Read-through cache in Postgres:
no transaction is held while the network is used, failures are NOT cached, and an unavailable service
degrades to "no data".
"""

from decimal import Decimal

import structlog
from deal_analyzer.geo import Poi
from pydantic import TypeAdapter
from rm_core.deadline import Deadline
from rm_core.geocache import GEOCODE_TTL, POI_TTL, cache_get, cache_put, geocode_key, poi_key
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rm_worker.clients.osm import GeoPoint, GeoUnavailable, OsmClient

log = structlog.get_logger(__name__)
_POIS = TypeAdapter(tuple[Poi, ...])


class GeoService:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], client: OsmClient) -> None:
        self._sm = sessionmaker
        self._client = client

    async def geocode(self, address: str, *, deadline: Deadline) -> GeoPoint | None:
        key = geocode_key(address)
        async with self._sm() as session:
            cached = await cache_get(session, key)
        if cached is not None:
            found = cached.get("found")
            return GeoPoint(Decimal(found["lat"]), Decimal(found["lon"])) if found else None
        try:
            point = await self._client.geocode(address, deadline=deadline)
        except GeoUnavailable as exc:
            log.warning("geocode_unavailable", reason=str(exc))
            return None
        payload = {"found": {"lat": str(point.latitude), "lon": str(point.longitude)} if point else None}
        async with self._sm() as session, session.begin():
            await cache_put(session, key, "geocode", payload, GEOCODE_TTL)
        return point

    async def pois(
        self, latitude: Decimal, longitude: Decimal, radius_m: int, *, deadline: Deadline
    ) -> tuple[Poi, ...] | None:
        """Points of interest around a point, or None when the service is unavailable (nothing is
        cached then)."""
        key = poi_key(latitude, longitude, radius_m)
        async with self._sm() as session:
            cached = await cache_get(session, key)
        if cached is not None:
            return _POIS.validate_python(cached["pois"], strict=False)
        try:
            found = await self._client.pois(latitude, longitude, radius_m, deadline=deadline)
        except GeoUnavailable as exc:
            log.warning("poi_unavailable", reason=str(exc))
            return None
        async with self._sm() as session, session.begin():
            await cache_put(
                session, key, "poi", {"pois": [p.model_dump(mode="json") for p in found]}, POI_TTL
            )
        return found
