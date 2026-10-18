"""GUS BDL statistics client and observation validator (LCTX-01b part 1, no database).

LEGAL[third-party-data]: GUS BDL statistics; source terms, attribution and redistribution limits are
unreviewed (B-023, B-012). Nothing here selects or activates a metric: callers pass reviewed
`MetricDefinition`s (RM-386).
LEGAL[scraping]: automated requests to a third-party API; an optional client id header, a shared request slot,
a local quota window and bounded retries keep the load polite (RM-386).
GDPR[personal-data]: none; aggregate public statistics only.

The response shape in the fixtures is an assumption about the public BDL v1 `data/by-variable` answer and is
not verified against the live service (no live call authorised). Unknown variable id, wrong unit and
malformed answers are rejected; gaps become typed non-measured observations with a reason.
"""

import asyncio
import hashlib
import json
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rm_contracts.location_context import (
    MetricDefinition,
    Observation,
    ObservationStatus,
    SelectionStatus,
    TerritoryLevel,
)
from rm_core.deadline import Deadline

from rm_worker.clients.otodom import SlotReserver

BDL_HOST = "bdl.stat.gov.pl"
BDL_URL = f"https://{BDL_HOST}/api/v1/data/by-variable"
TIMEOUT_S = 20.0
MAX_ATTEMPTS = 3
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PAGE_SIZE = 100
MAX_RETRY_AFTER_S = 60.0
ACCEPTED_ATTR_IDS = frozenset({1})  # 1 = normal value in BDL; others are flagged, never used silently

# BDL unit-level numbers (contract proposal): 0 country, 2 voivodeship, 5 powiat, 6 gmina.
_UNIT_LEVEL = {
    TerritoryLevel.country: 0,
    TerritoryLevel.wojewodztwo: 2,
    TerritoryLevel.powiat: 5,
    TerritoryLevel.gmina: 6,
}


class BdlUnavailable(Exception):
    """The page could not be fetched (network, status, size, quota, deadline). Retry later from the cursor."""


class BdlQuotaExhausted(BdlUnavailable):
    """The local or remote request quota is used up; resume from the cursor after `retry_after_s`."""

    def __init__(self, message: str, retry_after_s: float) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class BdlValidationError(Exception):
    """The answer is for the wrong variable or unit, or is structurally unusable: nothing is accepted."""


@dataclass(frozen=True)
class BdlCursor:
    """Resume point: the next page to fetch for one (variable, level, year)."""

    variable_id: str
    level: TerritoryLevel
    year: int
    page: int = 0


@dataclass(frozen=True)
class BdlPage:
    body: bytes
    digest: str  # sha256 of the raw body, becomes `Observation.source_digest`
    next_cursor: BdlCursor | None


@dataclass
class QuotaWindow:
    """Local request budget per rolling window; the remote quota still answers 429."""

    max_requests: int
    window_s: float = 900.0
    clock: Callable[[], float] = time.monotonic
    _stamps: list[float] = field(default_factory=lambda: [])

    def acquire(self) -> None:
        now = self.clock()
        self._stamps = [t for t in self._stamps if now - t < self.window_s]
        if len(self._stamps) >= self.max_requests:
            raise BdlQuotaExhausted("local BDL quota window used up", self.window_s - (now - self._stamps[0]))
        self._stamps.append(now)


@dataclass
class BdlClient:
    http: httpx.AsyncClient
    slots: SlotReserver
    quota: QuotaWindow
    client_id: str | None = None
    base_url: str = BDL_URL
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    rng: random.Random = field(default_factory=random.Random)

    async def fetch_page(self, cursor: BdlCursor, *, deadline: Deadline) -> BdlPage:  # noqa: PLR0912 - retry loop
        params = {
            "format": "json",
            "unit-level": str(_UNIT_LEVEL[cursor.level]),
            "year": str(cursor.year),
            "page": str(cursor.page),
            "page-size": str(PAGE_SIZE),
        }
        headers = {"Accept": "application/json"}
        if self.client_id:
            headers["X-ClientId"] = self.client_id
        url = f"{self.base_url}/{cursor.variable_id}"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.quota.acquire()
            wait = await self.slots.reserve(BDL_HOST)
            if wait >= deadline.remaining():
                raise BdlUnavailable("no request slot before the deadline")
            if wait > 0:
                await self.sleep(wait)
            budget = deadline.cap(TIMEOUT_S)
            if budget <= 0:
                raise BdlUnavailable("deadline exhausted")
            try:
                async with asyncio.timeout(budget):
                    async with self.http.stream("GET", url, params=params, headers=headers) as response:
                        if response.status_code == 429:
                            retry = _retry_after(response)
                            if attempt < MAX_ATTEMPTS and retry < deadline.remaining():
                                await self.sleep(retry)
                                continue
                            raise BdlQuotaExhausted("BDL answered HTTP 429", retry)
                        if response.status_code in {502, 503, 504} and attempt < MAX_ATTEMPTS:
                            await self.sleep(self.rng.uniform(1.0, 2.0))
                            continue
                        if response.status_code != 200:
                            raise BdlUnavailable(f"BDL answered HTTP {response.status_code}")
                        chunks: list[bytes] = []
                        size = 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > MAX_RESPONSE_BYTES:
                                raise BdlUnavailable("response too large")
                            chunks.append(chunk)
            except (httpx.HTTPError, TimeoutError) as exc:
                if attempt < MAX_ATTEMPTS:
                    continue
                raise BdlUnavailable(f"BDL unreachable: {type(exc).__name__}") from exc
            body = b"".join(chunks)
            return BdlPage(body, hashlib.sha256(body).hexdigest(), _next_cursor(body, cursor))
        raise BdlUnavailable("unreachable")  # pragma: no cover


def _retry_after(response: httpx.Response) -> float:
    try:
        value = float(response.headers.get("retry-after", ""))
    except ValueError:
        return 5.0
    return min(max(value, 0.0), MAX_RETRY_AFTER_S)


def _next_cursor(body: bytes, cursor: BdlCursor) -> BdlCursor | None:
    """Next page only when the answer links one; a malformed body ends the walk (the validator rejects it)."""
    try:
        data: Any = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    links: Any = data.get("links")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if isinstance(links, dict) and links.get("next"):  # pyright: ignore[reportUnknownMemberType]
        return BdlCursor(cursor.variable_id, cursor.level, cursor.year, cursor.page + 1)
    return None


class _Value(BaseModel):
    model_config = ConfigDict(extra="ignore")
    year: str = Field(max_length=4)
    val: Decimal | None = None
    attrId: int | None = None


class _Row(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z]+$")
    values: list[_Value] = Field(default_factory=lambda: [], max_length=50)


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore")
    variableId: str
    measureUnitName: str
    results: list[_Row] = Field(max_length=1000)


@dataclass(frozen=True)
class ValidatedPage:
    observations: tuple[Observation, ...]
    unexpected_units: tuple[str, ...]  # returned by the source but not requested; never stored


def validate_page(
    page: BdlPage,
    metric: MetricDefinition,
    *,
    year: int,
    expected_units: frozenset[str],
) -> ValidatedPage:
    """Raw answer to observations. Raises `BdlValidationError` for a wrong variable, unit or shape.

    Row-level problems do not raise: a null value is `suppressed`, an unaccepted attribute or an out-of-range
    value is `invalid_attribute`. Expected units absent from this page are reported `missing`, so pass
    only the units expected on this page (the caller owns the page-to-unit mapping).
    """
    if metric.selection is SelectionStatus.unavailable or not metric.bdl_variable_id:
        raise BdlValidationError("metric has no reviewed BDL variable")
    try:
        body = _Body.model_validate_json(page.body)
    except ValidationError as exc:
        raise BdlValidationError("answer does not match the expected shape") from exc
    if body.variableId != metric.bdl_variable_id:
        raise BdlValidationError("unknown or unexpected variable id")
    if body.measureUnitName != metric.unit:
        raise BdlValidationError("unit differs from the reviewed metric")
    out: list[Observation] = []
    seen: set[str] = set()
    extra: list[str] = []
    for row in body.results:
        if row.id not in expected_units:
            extra.append(row.id)
            continue
        if row.id in seen:
            raise BdlValidationError("duplicate territory in one answer")
        seen.add(row.id)
        out.append(_observe(row, metric, year, page.digest))
    out.extend(
        _gap(tid, metric, year, page.digest, ObservationStatus.missing, "no source row")
        for tid in sorted(expected_units - seen)
    )
    return ValidatedPage(tuple(out), tuple(extra))


def _gap(  # noqa: PLR0917 - private helper taking every field of one observation
    territory_id: str,
    metric: MetricDefinition,
    year: int,
    digest: str,
    status: ObservationStatus,
    reason: str,
) -> Observation:
    return Observation(
        territory_id=territory_id,
        metric_key=metric.key,
        metric_version=metric.version,
        year=year,
        status=status,
        reason=reason,
        source_digest=digest,
    )


def _observe(row: _Row, metric: MetricDefinition, year: int, digest: str) -> Observation:
    matches = [v for v in row.values if v.year == str(year)]
    if not matches:
        return _gap(row.id, metric, year, digest, ObservationStatus.missing, "no value for the year")
    if len(matches) > 1:
        return _gap(
            row.id, metric, year, digest, ObservationStatus.invalid_attribute, "several values for the year"
        )
    v = matches[0]
    if v.val is None:
        return _gap(row.id, metric, year, digest, ObservationStatus.suppressed, "source withholds the value")
    if v.attrId not in ACCEPTED_ATTR_IDS:
        return _gap(
            row.id, metric, year, digest, ObservationStatus.invalid_attribute, "attribute not accepted"
        )
    out_of_range = (
        not v.val.is_finite()
        or (metric.min_value is not None and v.val < metric.min_value)
        or (metric.max_value is not None and v.val > metric.max_value)
    )
    if out_of_range:
        return _gap(
            row.id,
            metric,
            year,
            digest,
            ObservationStatus.invalid_attribute,
            "value outside the reviewed range",
        )
    return Observation(
        territory_id=row.id,
        metric_key=metric.key,
        metric_version=metric.version,
        year=year,
        status=ObservationStatus.measured,
        value=v.val,
        source_digest=digest,
    )
