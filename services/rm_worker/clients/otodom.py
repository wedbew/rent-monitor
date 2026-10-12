"""Otodom listing fetcher: injectable transport, 1 req/s shared slots, bounded retries, circuit breaker.

LEGAL[scraping]: fetches Otodom listing pages with browser TLS impersonation; ToS exposure (RM-22).
LEGAL[url-analysis]: only ever requests a URL built from a validated short id, never a user-supplied URL.
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
from urllib.parse import urlsplit

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


def classify(raw: RawResponse) -> dict[str, Any]:
    """Return the `ad` object or raise the typed error for this response."""
    if raw.status in {404, 410}:
        raise ListingGone(f"HTTP {raw.status}")
    retry_after = parse_retry_after(raw.headers.get("retry-after"))
    if raw.status in {403, 429}:
        raise UpstreamBlocked(f"HTTP {raw.status}", retry_after_s=retry_after)
    if raw.status >= 500:
        raise UpstreamBlocked(f"HTTP {raw.status}", retry_after_s=retry_after)
    if raw.status != 200:
        raise UpstreamBlocked(f"unexpected HTTP {raw.status}", retry_after_s=retry_after)
    if "/oferta/" not in urlsplit(raw.final_url).path:
        raise ListingGone("redirected away from the listing")  # expired listings redirect to a search page
    text = raw.body.decode("utf-8", errors="replace")
    match = _NEXT_DATA.search(text)
    if not match:
        lowered = text[:200_000].lower()
        suffix = " (challenge page)" if any(m in lowered for m in _CHALLENGE_MARKERS) else ""
        raise UpstreamBlocked(f"missing __NEXT_DATA__{suffix}", retry_after_s=retry_after)
    try:
        envelope: Any = json.loads(match.group("json"))
        ad: Any = envelope["props"]["pageProps"]["ad"]
    except (ValueError, KeyError, TypeError) as exc:
        raise UpstreamSchemaDrift("listing payload has no props.pageProps.ad") from exc
    ad_obj = cast("dict[str, Any]", ad)
    if not isinstance(ad, dict) or not ad_obj.get("id"):
        raise UpstreamSchemaDrift("listing ad is not an object with an id")
    return ad_obj


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
        headers = {"accept": "text/html,application/xhtml+xml", "accept-language": "pl-PL,pl;q=0.9,en;q=0.5"}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self._guard_breaker()
            await self._wait_for_slot(priority, deadline)
            try:
                raw = await self.transport.get(url, headers=headers, total_s=deadline.cap(READ_TIMEOUT_S))
                ad = classify(raw)
            except UpstreamBlocked as exc:
                delay = self._delay(attempt, exc.retry_after_s)
                if attempt == MAX_ATTEMPTS or not exc.retryable or delay >= deadline.remaining():
                    await self.breaker.trip(HOST, "upstream_blocked")
                    raise
                await self.sleep(delay)
                continue
            return FetchedListing(otodom_id=short_id, url=url, ad=ad, content_sha256=content_hash(ad))
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
