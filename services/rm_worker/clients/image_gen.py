"""Image-generation clients for the interior architect (RM-450): protocol, offline fake, OpenRouter.

The one thing the caller needs from a failure is whether money may have been spent, so there are three
distinct errors. `ProviderNotReached`: the request never left (connect failure): nothing billed, release
the reservation. `ProviderRejected`: a definite refusal (4xx, 402, or 502 which the provider documents as
"failed, not billed"): release. `OutcomeUnknown`: the request was sent and no usable answer came back
(timeout, dropped connection, odd 5xx, unparseable body): the spend is unknown, so the caller keeps the
estimate charged and does not retry on its own.

Prompts, images and answers are never logged, only sizes and cost. Cost is parsed from JSON text straight
into `Decimal`, never through `float`.

LEGAL[images]: sends the person's room photo and permitted reference images to an image model (RM-450)
GDPR[processor]: OpenRouter and the model provider behind it receive those images (RM-450); the image
API's data-retention controls are undocumented (L-100), so no retention claim is made
"""

import asyncio
import base64
import binascii
import io
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rm_core.deadline import Deadline

log = structlog.get_logger(__name__)
MAX_RESPONSE_BYTES = 24 * 1024 * 1024  # base64 of a 12 MB image plus headroom
CONNECT_TIMEOUT_S = 5.0


class ProviderNotReached(Exception):
    """The request was never sent. Not billed."""


class ProviderRejected(Exception):
    """A definite refusal. Not billed."""


class OutcomeUnknown(Exception):
    """Sent, but no usable answer. The spend is unknown."""


@dataclass(frozen=True)
class ImageRequest:
    model: str
    prompt: str
    images: list[bytes]  # JPEG; the first is the room photo, the rest are references


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    media_type: str
    cost_usd: Decimal | None  # None when the provider did not report a cost


class ImageGenerator(Protocol):
    async def generate(self, request: ImageRequest, *, deadline: Deadline) -> GeneratedImage: ...


# ------------------------------------------------------------------------------------------- fake
@dataclass
class FakeImageGenerator:
    """Deterministic offline fake: returns the room photo tinted with a caption bar. Failure modes are chosen
    by a marker in the prompt, so a browser test can provoke each one with ordinary text in the brief notes:
    `FAKE_NOT_REACHED`, `FAKE_REJECT`, `FAKE_UNKNOWN`, `FAKE_SLOW`, `FAKE_NO_COST`, `FAKE_GARBAGE`."""

    cost_usd: Decimal = Decimal("0.034000")
    calls: int = 0
    requests: list[ImageRequest] = field(default_factory=lambda: [])

    async def generate(self, request: ImageRequest, *, deadline: Deadline) -> GeneratedImage:
        self.calls += 1
        self.requests.append(request)
        prompt = request.prompt
        if "FAKE_NOT_REACHED" in prompt:
            raise ProviderNotReached("fake: not reached")
        if "FAKE_REJECT" in prompt:
            raise ProviderRejected("fake: refused")
        if "FAKE_UNKNOWN" in prompt:
            raise OutcomeUnknown("fake: no answer")
        if "FAKE_SLOW" in prompt:
            await asyncio.sleep(deadline.remaining() + 5)
            raise OutcomeUnknown("fake: too slow")
        if "FAKE_GARBAGE" in prompt:
            return GeneratedImage(b"not an image", "image/png", self.cost_usd)
        from PIL import Image, ImageDraw  # noqa: PLC0415

        with Image.open(io.BytesIO(request.images[0])) as source:
            picture = source.convert("RGB")
        tint = Image.new("RGB", picture.size, (200, 170, 120))
        picture = Image.blend(picture, tint, 0.35)
        draw = ImageDraw.Draw(picture)
        draw.rectangle((0, picture.height - 28, picture.width, picture.height), fill=(255, 255, 255))
        draw.text(
            (8, picture.height - 22), f"SYMULACJA (fake) +{len(request.images) - 1} ref", fill=(20, 20, 20)
        )
        out = io.BytesIO()
        picture.save(out, format="PNG")
        return GeneratedImage(
            out.getvalue(), "image/png", None if "FAKE_NO_COST" in prompt else self.cost_usd
        )


# ------------------------------------------------------------------------------------- OpenRouter
class _Item(BaseModel):
    model_config = ConfigDict(extra="ignore")
    b64_json: str = Field(min_length=1)
    media_type: str = "image/png"


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cost: Decimal | None = Field(default=None, ge=0)


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: list[_Item] = Field(min_length=1)
    usage: _Usage = Field(default_factory=_Usage)


def build_payload(request: ImageRequest) -> dict[str, Any]:
    refs = [
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(i).decode("ascii")},
        }
        for i in request.images
    ]
    return {"model": request.model, "prompt": request.prompt, "n": 1, "input_references": refs}


def parse_reply(body: bytes) -> GeneratedImage:
    try:
        raw: Any = json.loads(body, parse_float=Decimal)
        reply = _Reply.model_validate(raw)
        data = base64.b64decode(reply.data[0].b64_json, validate=True)
    except (ValueError, ValidationError, binascii.Error) as exc:
        raise OutcomeUnknown("unusable response") from exc
    return GeneratedImage(data, reply.data[0].media_type, reply.usage.cost)


@dataclass
class OpenRouterImageGenerator:
    http: httpx.AsyncClient
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"

    async def generate(self, request: ImageRequest, *, deadline: Deadline) -> GeneratedImage:
        budget = deadline.remaining()
        if budget <= 0:
            raise ProviderNotReached("deadline exhausted before the call")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with asyncio.timeout(budget):
                async with self.http.stream(
                    "POST",
                    f"{self.base_url}/images",
                    json=build_payload(request),
                    headers=headers,
                    timeout=httpx.Timeout(budget, connect=min(CONNECT_TIMEOUT_S, budget)),
                ) as response:
                    status = response.status_code
                    if status == 200:
                        body = await _read_capped(response)
                    elif status in (400, 401, 402, 403, 404, 413, 422, 429, 502):
                        # 402/401 mean the operator must act; 502 is documented as "failed, not billed"
                        log.error("openrouter_image_rejected", status=status)
                        raise ProviderRejected(f"HTTP {status}")
                    else:
                        log.error("openrouter_image_unexpected", status=status)
                        raise OutcomeUnknown(f"HTTP {status}")
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise ProviderNotReached(type(exc).__name__) from exc
        except (httpx.TransportError, TimeoutError) as exc:
            raise OutcomeUnknown(type(exc).__name__) from exc
        return parse_reply(body)


async def _read_capped(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise OutcomeUnknown("response too large")
        chunks.append(chunk)
    return b"".join(chunks)
