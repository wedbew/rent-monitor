"""OpenRouter vision client: injectable, budget-gated, capped in flight, bounded retries, typed failures.

LEGAL[images]: sends listing photos and floor plans to a third-party model provider (RM-23).
GDPR[processor]: OpenRouter (and the model vendors behind it) receive images that may show people; EXIF is
already stripped by `rm_worker.images`. Prompts, images and answers are never logged, only counts and cost.
Money: cost is USD as `Decimal`, parsed straight from the JSON text, never through `float`.
"""

import asyncio
import base64
import json
import random
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rm_contracts.problems import ProblemCode
from rm_core.deadline import Deadline

from rm_worker.images import PreparedImage

REQUEST_TIMEOUT_S = 120.0
CONNECT_TIMEOUT_S = 5.0
MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 1.0
BACKOFF_CAP_S = 8.0
MAX_IN_FLIGHT = 4
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
log = structlog.get_logger(__name__)


class VisionUnavailable(Exception):
    """Vision cannot be used for this audit: the audit continues as `succeeded_degraded` (blueprint §2)."""

    code = ProblemCode.VISION_UNAVAILABLE


class VisionDisabled(VisionUnavailable):
    """The monthly AI budget is exhausted or the kill-switch is on."""


@dataclass(frozen=True)
class VisionRequest:
    model: str
    prompt: str
    images: Sequence[PreparedImage]
    system: str | None = None
    max_tokens: int = 1500
    json_mode: bool = False


@dataclass(frozen=True)
class VisionResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal | None  # None when the provider did not report a cost


class BudgetTicket(Protocol):
    async def settle(self, actual_usd: Decimal) -> None: ...

    async def release(self) -> None: ...


class BudgetGate(Protocol):
    async def reserve(self, estimate_usd: Decimal) -> BudgetTicket | None:
        """Atomically reserve `estimate_usd`; None when the budget is exhausted (RM-24 implements this)."""
        ...


class InFlightLimiter(Protocol):
    def slot(self, max_wait_s: float) -> AbstractAsyncContextManager[None]:
        """Hold a box-wide in-flight slot; raise `VisionUnavailable` if none frees within `max_wait_s`."""
        ...


class _Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str | None = None


class _Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: _Message


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)


class _Completion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str = ""
    choices: list[_Choice] = Field(min_length=1)
    usage: _Usage = Field(default_factory=_Usage)


def build_payload(req: VisionRequest) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": req.prompt}]
    for image in req.images:
        encoded = base64.b64encode(image.jpeg).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
    messages: list[dict[str, Any]] = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": content})
    payload: dict[str, Any] = {
        "model": req.model,
        "messages": messages,
        "max_tokens": req.max_tokens,
        "usage": {"include": True},
    }
    if req.json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def parse_completion(body: bytes) -> VisionResult:
    try:
        raw: Any = json.loads(body, parse_float=Decimal)
        parsed = _Completion.model_validate(raw)
    except (ValueError, ValidationError) as exc:
        raise VisionUnavailable("OpenRouter returned an unusable response") from exc
    content = parsed.choices[0].message.content
    if not content:
        raise VisionUnavailable("OpenRouter returned an empty answer")
    return VisionResult(
        content=content,
        model=parsed.model,
        prompt_tokens=parsed.usage.prompt_tokens,
        completion_tokens=parsed.usage.completion_tokens,
        cost_usd=parsed.usage.cost,
    )


async def _read_capped(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise VisionUnavailable("OpenRouter response is too large")
        chunks.append(chunk)
    return b"".join(chunks)


@dataclass
class OpenRouterClient:
    http: httpx.AsyncClient
    api_key: str
    budget: BudgetGate
    limiter: InFlightLimiter
    estimate_usd: Decimal
    base_url: str = "https://openrouter.ai/api/v1"
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    rng: random.Random = field(default_factory=random.Random)

    async def complete(self, req: VisionRequest, *, deadline: Deadline) -> VisionResult:
        if not self.api_key:
            raise VisionDisabled("OPENROUTER_API_KEY is not configured")
        ticket = await self.budget.reserve(self.estimate_usd)
        if ticket is None:
            raise VisionDisabled("AI budget exhausted")
        try:
            async with self.limiter.slot(deadline.remaining()):
                result = await self._with_retries(req, deadline)
        except BaseException:
            await ticket.release()
            raise
        await ticket.settle(result.cost_usd if result.cost_usd is not None else self.estimate_usd)
        log.info(
            "vision_call",
            model=result.model,
            images=len(req.images),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=str(result.cost_usd) if result.cost_usd is not None else "unreported",
        )
        return result

    async def _with_retries(self, req: VisionRequest, deadline: Deadline) -> VisionResult:
        payload = build_payload(req)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            retry_after: float | None = None
            try:
                return await self._once(payload, deadline)
            except _Retryable as exc:
                retry_after = exc.retry_after_s
                if attempt == MAX_ATTEMPTS:
                    raise VisionUnavailable(
                        f"OpenRouter unavailable after {MAX_ATTEMPTS} attempts: {exc}"
                    ) from exc
            delay = max(
                min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** (attempt - 1)) * self.rng.uniform(0.5, 1.0),
                retry_after or 0,
            )
            if delay >= deadline.remaining():
                raise VisionUnavailable("not enough time left to retry OpenRouter")
            await self.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    async def _once(self, payload: dict[str, Any], deadline: Deadline) -> VisionResult:
        budget = deadline.cap(REQUEST_TIMEOUT_S)
        if budget <= 0:
            raise VisionUnavailable("deadline exhausted before the OpenRouter call")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with asyncio.timeout(budget):
                async with self.http.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=httpx.Timeout(budget, connect=min(CONNECT_TIMEOUT_S, budget)),
                ) as response:
                    status = response.status_code
                    retry_after = _retry_after(response.headers.get("retry-after"))
                    if status in RETRYABLE_STATUSES:
                        raise _Retryable(f"HTTP {status}", retry_after)
                    if status != 200:
                        log.error("openrouter_rejected", status=status)  # 401/402 mean the operator must act
                        raise VisionUnavailable(f"OpenRouter rejected the request (HTTP {status})")
                    body = await _read_capped(response)
        except (httpx.TransportError, TimeoutError) as exc:
            raise _Retryable(type(exc).__name__, None) from exc
        return parse_completion(body)


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after_s: float | None) -> None:
        super().__init__(reason)
        self.retry_after_s = retry_after_s


def _retry_after(value: str | None) -> float | None:
    if value and value.strip().isdigit():
        return float(min(int(value.strip()), 3600))
    return None
