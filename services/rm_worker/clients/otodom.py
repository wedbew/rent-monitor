"""Otodom listing fetcher: injectable transport, 1 req/s shared slots, bounded retries, circuit breaker.

LEGAL[scraping]: fetches Otodom listing pages with browser TLS impersonation; ToS exposure (RM-22).
LEGAL[url-analysis]: only ever requests a URL built from a validated short id or location slug path, never a
user-supplied URL.
GDPR[personal-data]: the returned ad may contain seller names or phones; stored as a snapshot (RM-30).
Tests inject a fake transport; nothing here is exercised against the live site in CI.
"""

import asyncio
import json
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlencode, urlsplit

from rm_contracts.problems import ProblemCode
from rm_core.deadline import Deadline
from rm_core.snapshots import FetchedListing, content_hash
from rm_core.throttle import OTODOM_HOST

HOST = OTODOM_HOST
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 60.0
CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 30.0
_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(?P<json>.*?)</script>', re.DOTALL
)
_CHALLENGE_MARKERS = ("captcha", "cf-challenge", "just a moment", "datadome", "access denied")
Priority = Literal["interactive", "batch"]
LOCATION_PATH = re.compile(r"[a-z0-9-]+(/[a-z0-9-]+){0,3}")
MAX_SEARCH_PAGE = 400  # 2026-10-20 probes: Warsaw page 107 of 107 (limit 72) and page 51 (limit 36) answered
SEARCH_PAGE_SIZES = (24, 36, 72)  # the sizes the site offers; any other value silently falls back to 36


class FetchError(Exception):
    """Base for typed fetch failures; `code` maps to the blueprint §2 error table."""

    code: ProblemCode = ProblemCode.INTERNAL


class ListingGone(FetchError):
    code = ProblemCode.LISTING_GONE


class UpstreamSchemaDrift(FetchError):
    code = ProblemCode.UPSTREAM_SCHEMA_DRIFT


class UpstreamBlocked(FetchError):
    code = ProblemCode.UPSTREAM_BLOCKED

    def __init__(self, message: str, *, retry_after_s: float | None = None, retryable: bool = True) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s
        self.retryable = retryable


@dataclass(frozen=True)
class RawResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    final_url: str


class HttpTransport(Protocol):
    async def get(self, url: str, *, headers: dict[str, str], total_s: float) -> RawResponse: ...


class SlotReserver(Protocol):
    async def reserve(self, host: str) -> float:
        """Seconds to wait before the reserved slot starts. Must not block while waiting."""
        ...

    async def audit_queue_busy(self) -> bool: ...


class BreakerStore(Protocol):
    async def is_open(self, host: str) -> int | None:
        """Whole seconds until the breaker closes, or None when closed."""
        ...

    async def trip(self, host: str, reason: str) -> None: ...


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(min(int(value), 86_400))
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - (now or datetime.now(UTC))).total_seconds())


def _check_status(raw: RawResponse) -> float | None:
    """Raise the typed error for a non-200 response; otherwise return the Retry-After hint, if any."""
    if raw.status in {404, 410}:
        raise ListingGone(f"HTTP {raw.status}")
    retry_after = parse_retry_after(raw.headers.get("retry-after"))
    if raw.status in {403, 429}:
        raise UpstreamBlocked(f"HTTP {raw.status}", retry_after_s=retry_after)
    if raw.status >= 500:
        raise UpstreamBlocked(f"HTTP {raw.status}", retry_after_s=retry_after)
    if raw.status != 200:
        raise UpstreamBlocked(f"unexpected HTTP {raw.status}", retry_after_s=retry_after)
    return retry_after


def _page_props(raw: RawResponse, retry_after: float | None) -> dict[str, Any]:
    text = raw.body.decode("utf-8", errors="replace")
    match = _NEXT_DATA.search(text)
    if not match:
        lowered = text[:200_000].lower()
        suffix = " (challenge page)" if any(m in lowered for m in _CHALLENGE_MARKERS) else ""
        raise UpstreamBlocked(f"missing __NEXT_DATA__{suffix}", retry_after_s=retry_after)
    try:
        envelope: Any = json.loads(match.group("json"))
        props: Any = envelope["props"]["pageProps"]
    except (ValueError, KeyError, TypeError) as exc:
        raise UpstreamSchemaDrift("page has no props.pageProps") from exc
    if not isinstance(props, dict):
        raise UpstreamSchemaDrift("props.pageProps is not an object")
    return cast("dict[str, Any]", props)


def classify(raw: RawResponse) -> dict[str, Any]:
    """Return the `ad` object or raise the typed error for this response."""
    retry_after = _check_status(raw)
    if "/oferta/" not in urlsplit(raw.final_url).path:
        raise ListingGone("redirected away from the listing")  # expired listings redirect to a search page
    props = _page_props(raw, retry_after)
    ad: Any = props.get("ad")
    if not isinstance(ad, dict) or not cast("dict[str, Any]", ad).get("id"):
        raise UpstreamSchemaDrift("listing ad is not an object with an id")
    return cast("dict[str, Any]", ad)


def classify_search(raw: RawResponse) -> dict[str, Any]:
    """Return `pageProps.data.searchAds` of a search results page or raise the typed error."""
    retry_after = _check_status(raw)
    if "/wyniki/" not in urlsplit(raw.final_url).path:
        raise UpstreamSchemaDrift("search was redirected away from the results page")
    props = _page_props(raw, retry_after)
    data: Any = props.get("data")
    ads: Any = cast("dict[str, Any]", data).get("searchAds") if isinstance(data, dict) else None
    if not isinstance(ads, dict):
        raise UpstreamSchemaDrift("search page has no data.searchAds")
    return cast("dict[str, Any]", ads)


MAX_DAYS_SINCE_CREATED = 3650


@dataclass(frozen=True)
class SearchOptions:
    """The verified wire contract of a corpus search (RM-411, probes of 2026-10-20, L-050).

    - `days_since_created` is Otodom's `daysSinceCreated=N`: only adverts created in the last N x 24 hours
      (a rolling window measured at the server's clock, any integer from 1; absent means no filter). There is
      no upper bound and no absolute-date filter; the importer proves its windows from `createdAtFirst`.
    - `order` is `by=LATEST&direction=DESC|ASC`, which sorts by creation time (`newest` first by default).
    - `page_size` is `limit=24|36|72`; 72 halves the requests of a bootstrap (other values fall back to 36).
    The default listing order promotes pushed-up adverts, so a sweep always sets an explicit order."""

    days_since_created: int | None = None
    order: Literal["newest", "oldest"] = "newest"
    page_size: int = 72

    def __post_init__(self) -> None:
        days = self.days_since_created
        if days is not None and not 1 <= days <= MAX_DAYS_SINCE_CREATED:
            raise ValueError("days_since_created is out of range")
        if self.page_size not in SEARCH_PAGE_SIZES:
            raise ValueError("page_size must be a size the site offers")

    def query(self) -> dict[str, str]:
        out = {
            "limit": str(self.page_size),
            "by": "LATEST",
            "direction": "DESC" if self.order == "newest" else "ASC",
        }
        if self.days_since_created is not None:
            out["daysSinceCreated"] = str(self.days_since_created)
        return out


@dataclass
class OtodomClient:
    transport: HttpTransport
    slots: SlotReserver
    breaker: BreakerStore
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    rng: random.Random = field(default_factory=random.Random)
    base_url: str = "https://www.otodom.pl"

    async def fetch_listing(
        self, short_id: str, *, deadline: Deadline, priority: Priority = "interactive"
    ) -> FetchedListing:
        url = f"{self.base_url}/pl/oferta/{short_id}"
        ad = await self._fetch(url, classify, deadline, priority)
        return FetchedListing(otodom_id=short_id, url=url, ad=ad, content_sha256=content_hash(ad))

    async def fetch_rental_search(
        self, location_id: str, page: int, *, deadline: Deadline, priority: Priority = "batch"
    ) -> dict[str, Any]:
        """One page of flat-for-rent results for an Otodom location path (a validated slug path, never a
        user-supplied URL). Same throttle, breaker and retry rules as listings."""
        if not LOCATION_PATH.fullmatch(location_id) or not 1 <= page <= MAX_SEARCH_PAGE:
            raise ValueError("invalid search location or page")
        url = f"{self.base_url}/pl/wyniki/wynajem/mieszkanie/{location_id}?page={page}"
        return await self._fetch(url, classify_search, deadline, priority)

    async def fetch_corpus_search(
        self,
        location_id: str,
        page: int,
        *,
        options: SearchOptions,
        deadline: Deadline,
        priority: Priority = "batch",
    ) -> dict[str, Any]:
        """One page of flat-for-rent results in an explicit creation-time order, optionally limited to the
        last N days (RM-411, OTO-02/03). Same throttle, breaker and retries as `fetch_rental_search`."""
        if not LOCATION_PATH.fullmatch(location_id) or not 1 <= page <= MAX_SEARCH_PAGE:
            raise ValueError("invalid search location or page")
        query = urlencode({"page": page, **options.query()})
        url = f"{self.base_url}/pl/wyniki/wynajem/mieszkanie/{location_id}?{query}"
        return await self._fetch(url, classify_search, deadline, priority)

    async def _fetch(
        self,
        url: str,
        parse: Callable[[RawResponse], dict[str, Any]],
        deadline: Deadline,
        priority: Priority,
    ) -> dict[str, Any]:
        headers = {"accept": "text/html,application/xhtml+xml", "accept-language": "pl-PL,pl;q=0.9,en;q=0.5"}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self._guard_breaker()
            await self._wait_for_slot(priority, deadline)
            try:
                raw = await self.transport.get(url, headers=headers, total_s=deadline.cap(READ_TIMEOUT_S))
                return parse(raw)
            except UpstreamBlocked as exc:
                delay = self._delay(attempt, exc.retry_after_s)
                if attempt == MAX_ATTEMPTS or not exc.retryable or delay >= deadline.remaining():
                    await self.breaker.trip(HOST, "upstream_blocked")
                    raise
                await self.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    def _delay(self, attempt: int, retry_after_s: float | None) -> float:
        backoff = min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** (attempt - 1))
        jittered = backoff * self.rng.uniform(0.5, 1.0)
        return max(jittered, retry_after_s or 0.0)

    async def _guard_breaker(self) -> None:
        remaining = await self.breaker.is_open(HOST)
        if remaining is not None:
            raise UpstreamBlocked("circuit breaker open", retry_after_s=float(remaining), retryable=False)

    async def _wait_for_slot(self, priority: Priority, deadline: Deadline) -> None:
        while priority == "batch" and await self.slots.audit_queue_busy():
            if deadline.remaining() <= 1.0:
                raise UpstreamBlocked("batch yielded to audits until the deadline", retryable=False)
            await self.sleep(1.0)
        wait = await self.slots.reserve(HOST)
        if wait >= deadline.remaining():
            raise UpstreamBlocked("no request slot before the deadline", retryable=False)
        if wait > 0:
            await self.sleep(wait)
