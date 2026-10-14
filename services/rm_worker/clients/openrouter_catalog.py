"""OpenRouter model catalog: per-model prices used to size the budget hold before a vision call (#246, L-003).

The hold is a ceiling, not the bill: the real `usage.cost` replaces it when the call settles. When the catalog
is unreachable, malformed or has no price for the model, `price` returns None and the caller falls back to the
flat `OPENROUTER_CALL_ESTIMATE_USD`. Prices are USD per token (or per image / request) as decimal
strings, parsed straight to `Decimal`, never through `float`.
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

CATALOG_TIMEOUT_S = 10.0
CATALOG_TTL_S = 3600.0
FAILURE_TTL_S = 60.0  # do not hammer the catalog while it is down
MAX_CATALOG_BYTES = 8 * 1024 * 1024
IMAGE_TOKENS_CEILING = 2000  # input tokens charged per image when the model has no per-image price
CHARS_PER_TOKEN_FLOOR = 1  # tokens <= characters for any tokenizer, so len(text) is a safe ceiling
log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ModelPrice:
    prompt: Decimal  # USD per input token
    completion: Decimal  # USD per output token
    image: Decimal  # USD per input image; 0 when the model prices images as tokens
    request: Decimal  # USD flat per request

    def hold_usd(self, *, text_chars: int, images: int, max_tokens: int) -> Decimal:
        """Upper bound for one call: every input at its price, output capped by `max_tokens`."""
        input_tokens = text_chars // CHARS_PER_TOKEN_FLOOR
        if self.image == 0:
            input_tokens += images * IMAGE_TOKENS_CEILING
        return self.prompt * input_tokens + self.completion * max_tokens + self.image * images + self.request


class _Pricing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt: Decimal = Field(ge=0, allow_inf_nan=False)  # absent is unknown, not free: required
    completion: Decimal = Field(ge=0, allow_inf_nan=False)
    image: Decimal = Field(default=Decimal(0), ge=0, allow_inf_nan=False)
    request: Decimal = Field(default=Decimal(0), ge=0, allow_inf_nan=False)


class _Entry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    pricing: _Pricing


def parse_catalog(body: bytes) -> dict[str, ModelPrice]:
    """Parse `GET /models`; entries without usable prompt and completion prices are left out."""
    try:
        entries = json.loads(body)["data"]
    except (ValueError, KeyError, TypeError):
        return {}
    if not isinstance(entries, list):
        return {}
    prices: dict[str, ModelPrice] = {}
    for raw in cast("list[object]", entries):
        try:
            entry = _Entry.model_validate(raw)
        except ValidationError:
            continue
        p = entry.pricing
        prices[entry.id] = ModelPrice(p.prompt, p.completion, p.image, p.request)
    return prices


@dataclass
class OpenRouterCatalog:
    http: httpx.AsyncClient
    base_url: str = "https://openrouter.ai/api/v1"
    clock: Callable[[], float] = time.monotonic
    _prices: dict[str, ModelPrice] | None = None
    _expires: float = 0.0

    def __post_init__(self) -> None:
        self._lock = asyncio.Lock()

    async def price(self, model: str) -> ModelPrice | None:
        async with self._lock:
            if self._prices is None or self.clock() >= self._expires:
                await self._refresh()
        return (self._prices or {}).get(model)

    async def _refresh(self) -> None:
        try:
            async with self.http.stream(
                "GET", f"{self.base_url}/models", timeout=httpx.Timeout(CATALOG_TIMEOUT_S, connect=5.0)
            ) as response:
                if response.status_code != 200:
                    raise httpx.HTTPError(f"HTTP {response.status_code}")
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_CATALOG_BYTES:
                        raise httpx.HTTPError("catalog too large")
                    chunks.append(chunk)
        except httpx.HTTPError as exc:
            log.warning("openrouter_catalog_unavailable", reason=type(exc).__name__)
            self._prices = self._prices or {}  # keep the last good prices when we have them
            self._expires = self.clock() + FAILURE_TTL_S
            return
        self._prices = parse_catalog(b"".join(chunks))
        self._expires = self.clock() + CATALOG_TTL_S
