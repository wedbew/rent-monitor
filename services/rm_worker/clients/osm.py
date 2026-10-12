"""OpenStreetMap clients: Nominatim geocoding and Overpass points of interest, with a Postgres cache.

LEGAL[third-party-data]: OpenStreetMap data is ODbL (attribution required) and the Nominatim usage
policy applies:
an identifying User-Agent, at most 1 request per second (shared Postgres slot) and caching. The
placeholder User-Agent is
refused so we never call the public service anonymously. GDPR: only public listing addresses and
coordinates are sent.
Failures never fail an audit: callers degrade to "no distances" (`GeoUnavailable`).
"""

import asyncio
import contextlib
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx
import structlog
from deal_analyzer.geo import Poi, PoiCategory, in_poland
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rm_core.deadline import Deadline

from rm_worker.clients.otodom import SlotReserver

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_HOST = "nominatim.openstreetmap.org"
OVERPASS_HOST = "overpass-api.de"
PLACEHOLDER_AGENT = "set-an-ops-contact"
TIMEOUT_S = 20.0
MAX_ATTEMPTS = 2
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ELEMENTS = 500
log = structlog.get_logger(__name__)


class GeoUnavailable(Exception):
    """The lookup could not be done; the audit continues without distances."""


@dataclass(frozen=True)
class GeoPoint:
    latitude: Decimal
    longitude: Decimal


class _Hit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lat: str = Field(max_length=32)
    lon: str = Field(max_length=32)


class _Element(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lat: float | None = None
    lon: float | None = None
    center: dict[str, float] | None = None
    tags: dict[str, str] = Field(default_factory=dict)


_TAG_RULES: tuple[tuple[PoiCategory, str, tuple[str, ...]], ...] = (
    (PoiCategory.TRANSIT, "highway", ("bus_stop",)),
    (PoiCategory.TRANSIT, "railway", ("tram_stop", "station", "subway_entrance")),
    (PoiCategory.SCHOOL, "amenity", ("school",)),
    (PoiCategory.SHOP, "shop", ("supermarket", "convenience")),
    (PoiCategory.PARK, "leisure", ("park",)),
)


def _clause(around: str, key: str, values: tuple[str, ...]) -> str:
    if len(values) == 1:
        return f"nwr{around}[{key}={values[0]}];"
    return f'nwr{around}[{key}~"^({"|".join(values)})$"];'


def build_overpass_query(latitude: Decimal, longitude: Decimal, radius_m: int) -> str:
    """Only numbers are interpolated (Decimal/int), so no caller-supplied text can alter the query."""
    lat, lon = (
        format(latitude.quantize(Decimal("0.0001")), "f"),
        format(longitude.quantize(Decimal("0.0001")), "f"),
    )
    around = f"(around:{int(radius_m)},{lat},{lon})"
    clauses = "".join(_clause(around, key, values) for _, key, values in _TAG_RULES)
    return f"[out:json][timeout:20];({clauses});out center {MAX_ELEMENTS};"


def parse_pois(body: dict[str, Any]) -> tuple[Poi, ...]:
    elements = body.get("elements")
    if not isinstance(elements, list):
        raise GeoUnavailable("Overpass answer has no elements list")
    out: list[Poi] = []
    for raw in elements[:MAX_ELEMENTS]:  # pyright: ignore[reportUnknownVariableType]
        try:
            el = _Element.model_validate(raw)
        except ValidationError:
            continue
        lat, lon = el.lat, el.lon
        if (lat is None or lon is None) and el.center:
            lat, lon = el.center.get("lat"), el.center.get("lon")
        if lat is None or lon is None:
            continue
        for category, key, values in _TAG_RULES:
            if el.tags.get(key) in values:
                with contextlib.suppress(ValidationError):  # impossible coordinates are dropped
                    out.append(
                        Poi(category=category, latitude=Decimal(repr(lat)), longitude=Decimal(repr(lon)))
                    )
                break
    return tuple(out)


@dataclass
class OsmClient:
    http: httpx.AsyncClient
    user_agent: str
    nominatim_slots: SlotReserver
    overpass_slots: SlotReserver
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    rng: random.Random = field(default_factory=random.Random)

    async def geocode(self, address: str, *, deadline: Deadline) -> GeoPoint | None:
        """Address to coordinates inside Poland, or None when nothing plausible is found."""
        self._require_identity()
        params = {"q": address[:300], "format": "jsonv2", "limit": "1", "countrycodes": "pl"}
        body = await self._get(NOMINATIM_URL, NOMINATIM_HOST, self.nominatim_slots, deadline, params=params)
        if not isinstance(body, list):
            raise GeoUnavailable("Nominatim answer is not a list")
        hits: list[Any] = body  # pyright: ignore[reportUnknownVariableType]
        if not hits:
            return None
        try:
            hit = _Hit.model_validate(hits[0])
            point = GeoPoint(Decimal(hit.lat), Decimal(hit.lon))
        except (ValidationError, ArithmeticError) as exc:
            raise GeoUnavailable("Nominatim answer is malformed") from exc
        return point if in_poland(point.latitude, point.longitude) else None

    async def pois(
        self, latitude: Decimal, longitude: Decimal, radius_m: int, *, deadline: Deadline
    ) -> tuple[Poi, ...]:
        self._require_identity()
        query = build_overpass_query(latitude, longitude, radius_m)
        body = await self._get(
            OVERPASS_URL, OVERPASS_HOST, self.overpass_slots, deadline, params={"data": query}
        )
        if not isinstance(body, dict):
            raise GeoUnavailable("Overpass answer is not an object")
        return parse_pois(body)  # pyright: ignore[reportUnknownArgumentType]

    def _require_identity(self) -> None:
        if not self.user_agent.strip() or PLACEHOLDER_AGENT in self.user_agent:
            raise GeoUnavailable("NOMINATIM_USER_AGENT must contain a real contact (OSM usage policy)")

    async def _get(
        self, url: str, host: str, slots: SlotReserver, deadline: Deadline, *, params: dict[str, str]
    ) -> Any:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            wait = await slots.reserve(host)
            if wait >= deadline.remaining():
                raise GeoUnavailable("no request slot before the deadline")
            if wait > 0:
                await self.sleep(wait)
            budget = deadline.cap(TIMEOUT_S)
            if budget <= 0:
                raise GeoUnavailable("deadline exhausted")
            try:
                async with asyncio.timeout(budget):
                    async with self.http.stream(
                        "GET",
                        url,
                        params=params,
                        headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                    ) as response:
                        if response.status_code in {429, 502, 503, 504} and attempt < MAX_ATTEMPTS:
                            await self.sleep(self.rng.uniform(1.0, 2.0))
                            continue
                        if response.status_code != 200:
                            raise GeoUnavailable(f"{host} answered HTTP {response.status_code}")
                        chunks: list[bytes] = []
                        size = 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > MAX_RESPONSE_BYTES:
                                raise GeoUnavailable("response too large")
                            chunks.append(chunk)
            except (httpx.HTTPError, TimeoutError) as exc:
                if attempt < MAX_ATTEMPTS:
                    continue
                raise GeoUnavailable(f"{host} unreachable: {type(exc).__name__}") from exc
            try:
                return json.loads(b"".join(chunks))
            except ValueError as exc:
                raise GeoUnavailable("answer is not JSON") from exc
        raise GeoUnavailable("unreachable")  # pragma: no cover
