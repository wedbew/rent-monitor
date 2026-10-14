"""OpenRouter's public model catalog as a price source for the AI budget hold (RM-246).

GDPR: the request carries nothing about users or listings; it is the public `GET /models` list.
The budget gate reserves money before a call, but the real cost is known only after it. The hold is therefore
priced from the catalog: input tokens times the input price, plus the hard output ceiling (`max_tokens`) times
the output price. The real `usage.cost` replaces the hold when the call settles. An unreachable or odd catalog
yields no price and the caller falls back to the flat `OPENROUTER_CALL_ESTIMATE_USD`.
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import httpx
import structlog

log = structlog.get_logger(__name__)
TTL_S = 3600.0
RETRY_AFTER_FAILURE_S = 60.0  # do not hammer the catalog while it is down
TIMEOUT_S = 10.0
MAX_BYTES = 8 * 1024 * 1024
MAX_PRICE = Decimal("0.01")  # USD per token or per image; anything above is a data error, not a price


@dataclass(frozen=True)
class ModelPrice:
    prompt: Decimal  # USD per input token
    completion: Decimal  # USD per output token
    image: Decimal  # USD per image where the vendor prices images separately (often equals `prompt`)


def _price(value: object) -> Decimal | None:
    if not isinstance(value, str | int):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() and 0 <= number <= MAX_PRICE else None


def parse_catalog(body: bytes) -> dict[str, ModelPrice]:
    """Model id -> price. Models with a missing or implausible prompt or completion price are left out."""
    try:
        raw: Any = json.loads(body)
        items: object = raw["data"]
    except (ValueError, KeyError, TypeError):
        return {}
    prices: dict[str, ModelPrice] = {}
    for item in cast("list[Any]", items) if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        entry = cast("dict[str, Any]", item)
        model, pricing = entry.get("id"), entry.get("pricing")
        if not isinstance(model, str) or not isinstance(pricing, dict):
            continue
        fields = cast("dict[str, Any]", pricing)
        prompt, completion = _price(fields.get("prompt")), _price(fields.get("completion"))
        if prompt is None or completion is None:
            continue
        prices[model] = ModelPrice(prompt, completion, _price(fields.get("image")) or Decimal(0))
    return prices


class PriceCatalog:
    def __init__(
        self, http: httpx.AsyncClient, base_url: str, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._http, self._url, self._clock = http, f"{base_url.rstrip('/')}/models", clock
        self._prices: dict[str, ModelPrice] = {}
        self._valid_until = 0.0
        self._lock = asyncio.Lock()

    async def price(self, model: str) -> ModelPrice | None:
        async with self._lock:  # one fetch at a time, however many audits ask
            if self._clock() >= self._valid_until:
                await self._refresh()
        return self._prices.get(model)

    async def _refresh(self) -> None:
        try:
            async with asyncio.timeout(TIMEOUT_S):
                async with self._http.stream("GET", self._url, timeout=TIMEOUT_S) as response:
                    if response.status_code != 200:
                        raise httpx.HTTPError(f"HTTP {response.status_code}")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise httpx.HTTPError("catalog too large")
                        chunks.append(chunk)
            fresh = parse_catalog(b"".join(chunks))
        except (httpx.HTTPError, TimeoutError) as exc:
            log.warning("openrouter_catalog_unavailable", reason=type(exc).__name__)
            self._valid_until = self._clock() + RETRY_AFTER_FAILURE_S  # keep serving the last good list
            return
        if fresh:
            self._prices = fresh
            self._valid_until = self._clock() + TTL_S
        else:
            log.warning("openrouter_catalog_unusable")
            self._valid_until = self._clock() + RETRY_AFTER_FAILURE_S
