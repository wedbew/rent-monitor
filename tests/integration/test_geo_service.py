"""Cached geocoding and POIs on real Postgres; failures are never cached; expired rows are purged."""

from datetime import timedelta
from decimal import Decimal as D
from uuid import uuid4

import httpx
import pytest
from rm_core.deadline import Deadline
from rm_core.geocache import cache_get, cache_put, geocode_key, poi_key
from rm_core.privacy import purge_expired
from rm_core.settings import Settings
from rm_worker.clients.osm import OsmClient
from rm_worker.geo_service import GeoService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

pytestmark = [pytest.mark.integration]


class Slots:
    async def reserve(self, host: str) -> float:
        return 0.0

    async def audit_queue_busy(self) -> bool:
        return False


def service(engine: AsyncEngine, handler) -> GeoService:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    client = OsmClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        "RentMonitor/1.0 (ops@example.test)",
        Slots(),
        Slots(),
    )
    return GeoService(sm, client)


async def _cleanup(engine: AsyncEngine, *keys: str) -> None:
    async with engine.begin() as conn:
        for k in keys:
            await conn.execute(text("DELETE FROM app.geo_cache WHERE key = :k"), {"k": k})


async def test_geocode_hits_the_network_once_and_then_the_cache(engine: AsyncEngine) -> None:
    address = f"Testowa {uuid4().hex[:8]}, Warszawa"
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=[{"lat": "52.2297", "lon": "21.0122"}])

    svc = service(engine, handler)
    try:
        first = await svc.geocode(address, deadline=Deadline.after(30))
        second = await svc.geocode(
            address.upper(), deadline=Deadline.after(30)
        )  # same key after normalisation
        assert first is not None
        assert second is not None
        assert (second.latitude, second.longitude) == (D("52.2297"), D("21.0122"))
        assert len(calls) == 1
    finally:
        await _cleanup(engine, geocode_key(address))


async def test_a_not_found_answer_is_cached_too_but_a_failure_is_not(engine: AsyncEngine) -> None:
    nowhere, broken = f"Nigdzie {uuid4().hex[:8]}", f"Awaria {uuid4().hex[:8]}"
    state = {"fail": True, "calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if broken in request.url.params["q"] and state["fail"]:
            return httpx.Response(503)
        return httpx.Response(
            200, json=[] if nowhere in request.url.params["q"] else [{"lat": "50.06", "lon": "19.94"}]
        )

    svc = service(engine, handler)
    try:
        assert await svc.geocode(nowhere, deadline=Deadline.after(30)) is None
        before = state["calls"]
        assert await svc.geocode(nowhere, deadline=Deadline.after(30)) is None
        assert state["calls"] == before  # "not found" is remembered
        assert await svc.geocode(broken, deadline=Deadline.after(30)) is None  # degraded, not raised
        state["fail"] = False
        assert (
            await svc.geocode(broken, deadline=Deadline.after(30)) is not None
        )  # not poisoned by the failure
    finally:
        await _cleanup(engine, geocode_key(nowhere), geocode_key(broken))


async def test_pois_are_cached_per_rounded_coordinates(engine: AsyncEngine) -> None:
    lat, lon = D("52.22971"), D("21.01221")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"elements": [{"lat": 52.23, "lon": 21.01, "tags": {"highway": "bus_stop"}}]}
        )

    svc = service(engine, handler)
    try:
        first = await svc.pois(lat, lon, 800, deadline=Deadline.after(30))
        second = await svc.pois(
            D("52.22974"), D("21.01224"), 800, deadline=Deadline.after(30)
        )  # ~3 m away: same key
        assert first is not None
        assert second == first
        assert second is not None
        assert len(second) == 1
        assert len(calls) == 1
        await svc.pois(lat, lon, 1_500, deadline=Deadline.after(30))  # another radius is another lookup
        assert len(calls) == 2
    finally:
        await _cleanup(engine, poi_key(lat, lon, 800), poi_key(lat, lon, 1_500))


async def test_an_unavailable_poi_service_returns_none_and_caches_nothing(engine: AsyncEngine) -> None:
    lat, lon = D("51.1111"), D("17.2222")
    svc = service(engine, lambda r: httpx.Response(500))
    assert await svc.pois(lat, lon, 800, deadline=Deadline.after(30)) is None
    async with async_sessionmaker(engine)() as s:
        assert await cache_get(s, poi_key(lat, lon, 800)) is None


async def test_expired_entries_are_not_served_and_the_retention_sweep_removes_them(
    engine: AsyncEngine,
) -> None:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    key = uuid4().hex.ljust(64, "0")
    try:
        async with sm() as s, s.begin():
            await cache_put(s, key, "geocode", {"found": None}, timedelta(milliseconds=1))
        async with sm() as s:
            await s.execute(text("SELECT pg_sleep(0.05)"))
            assert await cache_get(s, key) is None
        report = await purge_expired(sm, Settings())
        assert report.geo_cache >= 1
        async with engine.connect() as conn:
            assert (
                await conn.scalar(text("SELECT count(*) FROM app.geo_cache WHERE key = :k"), {"k": key}) == 0
            )
    finally:
        await _cleanup(engine, key)
