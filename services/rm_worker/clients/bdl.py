"""GUS BDL source side: injectable HTTP client, quota gate, resumable cursor and observation validator.

LEGAL[third-party-data]: reads public GUS BDL statistics; source terms, attribution and redistribution
limits are unreviewed (B-023, B-012). Only variables bound to a reviewed `MetricDefinition` pass (RM-386)
LEGAL[scraping]: automated requests to a third-party API; kept under a request quota, a per-request
timeout and a total deadline, honouring HTTP 429 (RM-386)
GDPR[processor]: no personal data is sent or received; aggregate territorial statistics only (RM-386)

Policy: nothing here selects a metric. The validator needs a `BdlMetricBinding` built from a
`MetricDefinition` with `selection=selected` and a reviewed `bdl_variable_id` (the reviewed set is
`rm_core.bdl_metrics`).
Response shapes were checked against the live service on 2026-10-20 (RM-48, closes RM-386-L01): the variable
id is a number, a data page has no `page`/`pageSize` of its own, years arrive as strings, `attrId` 1 is a
value, 3 an incomplete aggregate and 91 ("x") confidential or no information with a placeholder `0`.

No database: the cursor is a plain value the caller persists and resumes from (part 2 of LCTX-01b).
"""

import asyncio
import hashlib
import json
import random
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Annotated, Any, Protocol

import httpx
import structlog
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, ValidationError
from rm_contracts.location_context import (
    MetricDefinition,
    Observation,
    ObservationStatus,
    SelectionStatus,
    TerritoryId,
    TerritoryRef,
)
from rm_core.deadline import Deadline

BDL_BASE_URL = "https://bdl.stat.gov.pl/api/v1"
BDL_HOST = "bdl.stat.gov.pl"
TIMEOUT_S = 20.0
MAX_ATTEMPTS = 2
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PAGE_SIZE = 100
MAX_PAGE_INDEX = 10_000
MAX_YEARS = 40

log = structlog.get_logger(__name__)

VariableId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]{1,16}$")]


def _text(value: object) -> object:
    """The live service sends ids as numbers; the contract keeps them as strings (leading zeros matter)."""
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else value


WireId = Annotated[str, BeforeValidator(_text), StringConstraints(min_length=1, max_length=16)]


class BdlError(Exception):
    """Base class for every failure of this module."""


class BdlUnavailable(BdlError):
    """The source could not be read now; retry from the same cursor later."""


class BdlQuotaExhausted(BdlUnavailable):
    """The request quota (ours or the server's 429) forbids a request before the deadline."""

    def __init__(self, message: str, retry_after_s: float) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class BdlResponseInvalid(BdlError):
    """The answer is not the documented shape; never retried, never partially accepted."""


class BdlValidationError(BdlError):
    """Base class for validator rejections."""


class UnknownVariableError(BdlValidationError):
    """A variable id with no reviewed binding."""


class WrongUnitError(BdlValidationError):
    """The source measure unit differs from the reviewed one."""


class UnexpectedDataError(BdlValidationError):
    """A year or territory the request did not ask for, or conflicting duplicate rows."""


class GapError(BdlValidationError):
    """Strict mode: an expected (territory, year) is not a measured value."""


# --- quota -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class QuotaWindow:
    limit: int
    seconds: float


class QuotaGate(Protocol):
    async def acquire(self, *, max_wait_s: float) -> None:
        """Take one request slot or raise `BdlQuotaExhausted` when none opens within `max_wait_s`."""
        ...


@dataclass
class SlidingWindowQuota:
    """Process-local quota gate. The real limits are the owner's to confirm (RM-386-L02); none are baked in.

    A Postgres-shared gate (one budget for all workers) is part 2.
    """

    windows: tuple[QuotaWindow, ...]
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    _stamps: list[float] = field(default_factory=list[float], init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        if not self.windows or any(w.limit < 1 or w.seconds <= 0 for w in self.windows):
            raise ValueError("quota windows must be positive")

    def _wait_needed(self, now: float) -> float:
        wait = 0.0
        for w in self.windows:
            inside = [t for t in self._stamps if t > now - w.seconds]
            if len(inside) >= w.limit:
                wait = max(wait, inside[-w.limit] + w.seconds - now)
        return wait

    async def acquire(self, *, max_wait_s: float) -> None:
        async with self._lock:
            now = self.clock()
            horizon = max(w.seconds for w in self.windows)
            self._stamps = [t for t in self._stamps if t > now - horizon]
            wait = self._wait_needed(now)
            if wait > max_wait_s:
                raise BdlQuotaExhausted("BDL request quota used up", retry_after_s=wait)
            if wait > 0:
                await self.sleep(wait)
            self._stamps.append(self.clock())


# --- wire models -----------------------------------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class BdlValue(_Model):
    year: int
    val: Decimal | None = None
    attr_id: int = Field(alias="attrId")


class BdlUnitResult(_Model):
    id: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    name: Annotated[str, StringConstraints(max_length=200)] = ""
    values: tuple[BdlValue, ...] = ()


class BdlPageBody(_Model):
    variable_id: WireId = Field(alias="variableId")
    page: int | None = Field(default=None, ge=0)  # the live service does not echo it
    page_size: int | None = Field(default=None, alias="pageSize", ge=1, le=500)  # nor this
    total_records: int = Field(alias="totalRecords", ge=0)
    results: tuple[BdlUnitResult, ...]


class BdlVariableMeta(_Model):
    id: WireId
    unit: Annotated[str, StringConstraints(min_length=1, max_length=40)] = Field(alias="measureUnitName")
    years: tuple[int, ...] = ()


class BdlUnit(_Model):
    """One territorial unit of `/units`; `kind` is BDL's own unit type, `parent_id` its direct parent."""

    id: Annotated[str, StringConstraints(pattern=r"^[0-9]{12}$")]
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    level: int = Field(ge=0, le=7)
    parent_id: Annotated[str, StringConstraints(pattern=r"^[0-9]{12}$")] | None = Field(
        default=None, alias="parentId"
    )
    kind: Annotated[str, StringConstraints(max_length=4)] | None = None


class BdlUnitsBody(_Model):
    total_records: int = Field(alias="totalRecords", ge=0)
    results: tuple[BdlUnit, ...]


class BdlCursor(BaseModel):
    """Position in one variable's data. Plain value: the caller stores it and resumes from it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable_id: VariableId
    unit_level: int = Field(ge=0, le=7)
    years: tuple[int, ...] = Field(min_length=1, max_length=MAX_YEARS)
    page: int = Field(default=0, ge=0, le=MAX_PAGE_INDEX)


@dataclass(frozen=True)
class BdlPage:
    cursor: BdlCursor
    body: BdlPageBody
    next_cursor: BdlCursor | None


# --- client ----------------------------------------------------------------------------------------------


@dataclass
class BdlClient:
    http: httpx.AsyncClient
    quota: QuotaGate
    api_key: str | None = None
    base_url: str = BDL_BASE_URL
    page_size: int = PAGE_SIZE
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    rng: random.Random = field(default_factory=random.Random)

    async def variable_meta(self, variable_id: str, *, deadline: Deadline) -> BdlVariableMeta:
        vid = _variable_id(variable_id)
        body = await self._get(
            f"{self.base_url}/variables/{vid}", httpx.QueryParams({"format": "json"}), deadline
        )
        try:
            return BdlVariableMeta.model_validate(body)
        except ValidationError as exc:
            raise BdlResponseInvalid("variable metadata is malformed") from exc

    async def fetch_page(self, cursor: BdlCursor, *, deadline: Deadline) -> BdlPage:
        params = httpx.QueryParams(
            [
                ("unit-level", str(cursor.unit_level)),
                ("page", str(cursor.page)),
                ("page-size", str(self.page_size)),
                ("format", "json"),
                *(("year", str(y)) for y in cursor.years),
            ]
        )
        raw = await self._get(f"{self.base_url}/data/by-variable/{cursor.variable_id}", params, deadline)
        try:
            body = BdlPageBody.model_validate(raw)
        except ValidationError as exc:
            raise BdlResponseInvalid("data page is malformed") from exc
        if body.variable_id != cursor.variable_id or (body.page is not None and body.page != cursor.page):
            raise BdlResponseInvalid("data page does not answer the request")
        page_size = body.page_size or self.page_size
        if len(body.results) > page_size:
            raise BdlResponseInvalid("data page exceeds its page size")
        more = (cursor.page + 1) * page_size < body.total_records and bool(body.results)
        nxt = cursor.model_copy(update={"page": cursor.page + 1}) if more else None
        if nxt is not None and nxt.page > MAX_PAGE_INDEX:
            raise BdlResponseInvalid("too many pages")
        return BdlPage(cursor=cursor, body=body, next_cursor=nxt)

    async def units(self, level: int, *, deadline: Deadline) -> tuple[BdlUnit, ...]:
        """Every unit of one territorial level (`/units?level=`), all pages. Used to build the reference."""
        found: list[BdlUnit] = []
        page = 0
        while True:
            params = httpx.QueryParams(
                [
                    ("level", str(level)),
                    ("page", str(page)),
                    ("page-size", str(self.page_size)),
                    ("format", "json"),
                ]
            )
            raw = await self._get(f"{self.base_url}/units", params, deadline)
            try:
                body = BdlUnitsBody.model_validate(raw)
            except ValidationError as exc:
                raise BdlResponseInvalid("units page is malformed") from exc
            found += body.results
            page += 1
            if not body.results or page * self.page_size >= body.total_records:
                break
            if page > MAX_PAGE_INDEX:
                raise BdlResponseInvalid("too many pages")
        if len(found) != len({u.id for u in found}):
            raise BdlResponseInvalid("duplicate unit ids")
        return tuple(found)

    async def record_count(self, variable_id: str, unit_level: int, year: int, *, deadline: Deadline) -> int:
        """How many unit rows the source holds for one variable, level and year (one tiny request)."""
        vid = _variable_id(variable_id)
        params = httpx.QueryParams(
            [
                ("unit-level", str(unit_level)),
                ("year", str(year)),
                ("page", "0"),
                ("page-size", "1"),
                ("format", "json"),
            ]
        )
        raw = await self._get(f"{self.base_url}/data/by-variable/{vid}", params, deadline)
        try:
            return BdlPageBody.model_validate(raw).total_records
        except ValidationError as exc:
            raise BdlResponseInvalid("data page is malformed") from exc

    async def unit_ids_with_values(
        self, variable_id: str, unit_level: int, year: int, *, deadline: Deadline
    ) -> frozenset[str]:
        """Ids of the units that carry a value row for one variable and year: which units existed then."""
        start = BdlCursor(variable_id=variable_id, unit_level=unit_level, years=(year,))
        ids: set[str] = set()
        async for page in self.pages(start, deadline=deadline):
            ids |= {
                u.id for u in page.body.results if any(v.year == year and v.val is not None for v in u.values)
            }
        return frozenset(ids)

    async def pages(self, start: BdlCursor, *, deadline: Deadline) -> AsyncIterator[BdlPage]:
        """Yield pages from `start`. After an error the last yielded `next_cursor` resumes the work."""
        cursor: BdlCursor | None = start
        while cursor is not None:
            page = await self.fetch_page(cursor, deadline=deadline)
            yield page
            cursor = page.next_cursor

    async def _read(
        self, url: str, params: httpx.QueryParams, headers: dict[str, str], *, retry_ok: bool
    ) -> list[bytes] | None:
        """Body chunks of a 200 answer, None for a retryable 5xx, an exception otherwise."""
        async with self.http.stream("GET", url, params=params, headers=headers) as response:
            status = response.status_code
            if status == 429:
                raise BdlQuotaExhausted(
                    "BDL answered HTTP 429", _retry_after(response.headers.get("Retry-After"))
                )
            if status in {502, 503, 504} and retry_ok:
                return None
            if status != 200:
                raise BdlUnavailable(f"BDL answered HTTP {status}")
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise BdlResponseInvalid("response too large")
                chunks.append(chunk)
            return chunks

    async def _get(self, url: str, params: httpx.QueryParams, deadline: Deadline) -> Any:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-ClientId"] = self.api_key
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self.quota.acquire(max_wait_s=deadline.remaining())
            budget = deadline.cap(TIMEOUT_S)
            if budget <= 0:
                raise BdlUnavailable("deadline exhausted")
            try:
                async with asyncio.timeout(budget):
                    chunks = await self._read(url, params, headers, retry_ok=attempt < MAX_ATTEMPTS)
            except (httpx.HTTPError, TimeoutError) as exc:
                if attempt < MAX_ATTEMPTS:
                    await self.sleep(self.rng.uniform(0.5, 1.5))
                    continue
                raise BdlUnavailable(f"BDL unreachable: {type(exc).__name__}") from exc
            if chunks is None:
                await self.sleep(self.rng.uniform(0.5, 1.5))
                continue
            try:
                return json.loads(b"".join(chunks), parse_float=Decimal)
            except ValueError as exc:
                raise BdlResponseInvalid("answer is not JSON") from exc
        raise BdlUnavailable("unreachable")  # pragma: no cover


def _variable_id(value: str) -> str:
    # The id is interpolated into a URL path: only short alphanumerics are accepted.
    if not (1 <= len(value) <= 16 and value.isascii() and value.isalnum()):
        raise ValueError("invalid BDL variable id")
    return value


def _retry_after(header: str | None) -> float:
    """Seconds from `Retry-After`: a number, or the service's own words (`1 sek`, observed 2026-10-20)."""
    match = re.match(r"\s*(\d+(?:\.\d+)?)\s*(?:s|sek|sec|seconds?)?\s*$", header or "", re.I)
    if match is None:
        return 900.0
    return min(max(float(match.group(1)), 0.0), 86_400.0)


# --- validator -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BdlMetricBinding:
    """Reviewed link between one BDL variable and one metric version, built by the caller."""

    variable_id: str
    definition: MetricDefinition
    expected_unit: str
    valid_attr_ids: frozenset[int] = frozenset({1})
    suppressed_attr_ids: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        _variable_id(self.variable_id)
        if self.definition.selection is not SelectionStatus.selected:
            raise ValueError("only a selected metric can be bound (B-023)")
        if self.definition.bdl_variable_id != self.variable_id:
            raise ValueError("binding variable id differs from the metric's reviewed id")
        if self.definition.unit != self.expected_unit:
            raise ValueError("binding unit differs from the metric's unit")


@dataclass(frozen=True)
class ValidationReport:
    observations: tuple[Observation, ...]
    gaps: tuple[Observation, ...]  # the non-measured subset, for reporting


def _digest(variable_id: str, unit_id: str, value: BdlValue) -> str:
    canonical = json.dumps(
        [variable_id, unit_id, value.year, None if value.val is None else str(value.val), value.attr_id],
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _gap_digest(variable_id: str, unit_id: str, year: int, why: str) -> str:
    return hashlib.sha256(json.dumps([variable_id, unit_id, year, why]).encode()).hexdigest()


@dataclass
class BdlObservationValidator:
    bindings: Mapping[str, BdlMetricBinding]

    def check_meta(self, meta: BdlVariableMeta) -> BdlMetricBinding:
        binding = self.bindings.get(meta.id)
        if binding is None:
            raise UnknownVariableError(f"variable {meta.id} has no reviewed binding")
        if meta.unit != binding.expected_unit:
            raise WrongUnitError(f"variable {meta.id} reports unit {meta.unit!r}")
        return binding

    def validate(  # noqa: PLR0912  (one linear pass over pages, years and gaps)
        self,
        meta: BdlVariableMeta,
        pages: tuple[BdlPage, ...],
        *,
        expected: Mapping[TerritoryId, TerritoryRef],
        years: tuple[int, ...],
        strict_gaps: bool = False,
        ignore_unknown_units: bool = False,
    ) -> ValidationReport:
        """Turn the pages of one variable into observations for every expected (territory, year).

        Rejects (raises) unknown variables, wrong units, foreign territories or years and conflicting
        duplicates. Gaps become `missing` / `suppressed` / `invalid_attribute` observations; with
        `strict_gaps` any gap raises `GapError` instead. With `ignore_unknown_units` a row for a unit outside
        `expected` is skipped (BDL lists urban/rural parts, districts and defunct gminas next to the whole
        current ones the reference holds); the caller counts them.
        """
        binding = self.check_meta(meta)
        defn = binding.definition
        wanted = set(years)
        found: dict[tuple[str, int], Observation] = {}
        for page in pages:
            if page.body.variable_id != meta.id:
                raise UnexpectedDataError("page belongs to another variable")
            for unit in page.body.results:
                territory = expected.get(unit.id)
                if territory is None:
                    if ignore_unknown_units:
                        continue
                    raise UnexpectedDataError(f"unexpected territory {unit.id}")
                if territory.level not in defn.published_levels:
                    raise UnexpectedDataError(f"{defn.key} is not published at {territory.level.value}")
                for value in unit.values:
                    if value.year not in wanted:
                        raise UnexpectedDataError(f"unexpected year {value.year}")
                    obs = self._observation(binding, unit.id, value)
                    key = (unit.id, value.year)
                    previous = found.get(key)
                    if previous is not None and previous != obs:
                        raise UnexpectedDataError(f"conflicting duplicate for {unit.id} {value.year}")
                    found[key] = obs
        out: list[Observation] = []
        gaps: list[Observation] = []
        for tid in expected:
            for year in sorted(wanted):
                obs = found.get((tid, year)) or Observation(
                    territory_id=tid,
                    metric_key=defn.key,
                    metric_version=defn.version,
                    year=year,
                    status=ObservationStatus.missing,
                    reason="source returned no row",
                    source_digest=_gap_digest(meta.id, tid, year, "missing"),
                )
                out.append(obs)
                if obs.status is not ObservationStatus.measured:
                    gaps.append(obs)
        if strict_gaps and gaps:
            raise GapError(f"{len(gaps)} expected observations are not measured")
        return ValidationReport(observations=tuple(out), gaps=tuple(gaps))

    @staticmethod
    def _observation(binding: BdlMetricBinding, unit_id: str, value: BdlValue) -> Observation:
        defn = binding.definition
        digest = _digest(binding.variable_id, unit_id, value)

        def make(
            status: ObservationStatus, *, number: Decimal | None = None, reason: str | None = None
        ) -> Observation:
            return Observation(
                territory_id=unit_id,
                metric_key=defn.key,
                metric_version=defn.version,
                year=value.year,
                status=status,
                value=number,
                reason=reason,
                source_digest=digest,
            )

        if value.attr_id in binding.suppressed_attr_ids:
            return make(ObservationStatus.suppressed, reason=f"source attribute {value.attr_id}")
        number = value.val
        if value.attr_id not in binding.valid_attr_ids or number is None or not number.is_finite():
            return make(
                ObservationStatus.invalid_attribute, reason=f"unusable source row (attribute {value.attr_id})"
            )
        if (defn.min_value is not None and number < defn.min_value) or (
            defn.max_value is not None and number > defn.max_value
        ):
            return make(ObservationStatus.invalid_attribute, reason="value outside metric bounds")
        return make(ObservationStatus.measured, number=number)
