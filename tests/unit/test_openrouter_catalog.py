import json
import random
from contextlib import asynccontextmanager
from decimal import Decimal

import httpx
import pytest
from rm_core.deadline import Deadline
from rm_worker.clients.openrouter import OpenRouterClient, VisionRequest
from rm_worker.clients.openrouter_catalog import (
    CATALOG_TTL_S,
    FAILURE_TTL_S,
    IMAGE_TOKENS_CEILING,
    ModelPrice,
    OpenRouterCatalog,
    parse_catalog,
)
from rm_worker.images import PreparedImage

IMG = PreparedImage("https://olxcdn.com/a.jpg", b"\xff\xd8jpegbytes", 10, 10, 1)
OK_BODY = {
    "model": "vendor/vision-1",
    "choices": [{"message": {"role": "assistant", "content": "{}"}}],
    "usage": {"prompt_tokens": 120, "completion_tokens": 30, "cost": 0.00014},
}


class Ticket:
    settled: Decimal | None = None

    async def settle(self, actual_usd: Decimal, usage: object = None) -> None:
        self.settled = actual_usd

    async def release(self) -> None:
        pass


class Gate:
    def __init__(self) -> None:
        self.ticket = Ticket()
        self.estimates: list[Decimal] = []

    async def reserve(self, estimate_usd: Decimal) -> Ticket:
        self.estimates.append(estimate_usd)
        return self.ticket


class Limiter:
    @asynccontextmanager
    async def slot(self, max_wait_s: float):
        yield


async def _no_sleep(s: float) -> None:
    return None


CATALOG = {
    "data": [
        {
            "id": "vendor/vision-1",
            "pricing": {"prompt": "0.0000001", "completion": "0.0000004", "image": "0", "request": "0"},
        },
        {
            "id": "vendor/per-image",
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000002",
                "image": "0.001",
                "request": "0.0005",
            },
        },
        {"id": "vendor/no-completion", "pricing": {"prompt": "0.000001"}},
        {"id": "vendor/bad", "pricing": {"prompt": "abc", "completion": "1"}},
        {"id": "vendor/negative", "pricing": {"prompt": "-1", "completion": "1"}},
    ]
}


def test_parse_keeps_exact_decimals_and_drops_unusable_entries() -> None:
    prices = parse_catalog(json.dumps(CATALOG).encode())
    assert set(prices) == {"vendor/vision-1", "vendor/per-image"}
    assert prices["vendor/vision-1"].prompt == Decimal("0.0000001")


@pytest.mark.parametrize("body", [b"", b"nope", b"{}", b'{"data": 3}', b'{"data": [1, "x"]}'])
def test_parse_garbage_is_empty(body: bytes) -> None:
    assert parse_catalog(body) == {}


def test_hold_prices_input_and_caps_output_by_max_tokens() -> None:
    price = ModelPrice(Decimal("0.000001"), Decimal("0.000002"), Decimal(0), Decimal(0))
    hold = price.hold_usd(text_chars=100, images=2, max_tokens=1500)
    assert hold == Decimal("0.000001") * (100 + 2 * IMAGE_TOKENS_CEILING) + Decimal("0.000002") * 1500


def test_hold_uses_the_per_image_price_when_present() -> None:
    price = ModelPrice(Decimal("0.000001"), Decimal("0.000002"), Decimal("0.001"), Decimal("0.0005"))
    hold = price.hold_usd(text_chars=10, images=3, max_tokens=100)
    assert hold == Decimal("0.00001") + Decimal("0.0002") + Decimal("0.003") + Decimal("0.0005")


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_catalog_is_cached_until_the_ttl_and_refetched_after() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=json.dumps(CATALOG).encode())

    clock = Clock()
    catalog = OpenRouterCatalog(httpx.AsyncClient(transport=httpx.MockTransport(handler)), clock=clock)
    assert await catalog.price("vendor/vision-1") is not None
    assert await catalog.price("vendor/unknown") is None
    assert calls == 1
    clock.now = CATALOG_TTL_S + 1
    await catalog.price("vendor/vision-1")
    assert calls == 2


async def test_failure_returns_none_keeps_old_prices_and_backs_off() -> None:
    responses = iter([httpx.Response(200, content=json.dumps(CATALOG).encode()), httpx.Response(503)])
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return next(responses)

    clock = Clock()
    catalog = OpenRouterCatalog(httpx.AsyncClient(transport=httpx.MockTransport(handler)), clock=clock)
    await catalog.price("vendor/vision-1")
    clock.now = CATALOG_TTL_S + 1
    assert await catalog.price("vendor/vision-1") is not None  # last good price survives the outage
    assert await catalog.price("vendor/vision-1") is not None
    assert calls == 2  # backed off, no second retry inside FAILURE_TTL_S
    assert FAILURE_TTL_S > 0


async def test_unreachable_catalog_yields_no_price() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    catalog = OpenRouterCatalog(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await catalog.price("vendor/vision-1") is None


def _client(catalog: OpenRouterCatalog | None, gate: Gate) -> OpenRouterClient:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=json.dumps(OK_BODY).encode()))
    )
    return OpenRouterClient(
        http,
        "k",
        gate,
        Limiter(),
        Decimal("0.02"),
        sleep=_no_sleep,
        rng=random.Random(3),  # noqa: S311
        prices=catalog,
    )


def _catalog() -> OpenRouterCatalog:
    return OpenRouterCatalog(
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=json.dumps(CATALOG).encode()))
        )
    )


async def test_the_hold_comes_from_the_catalog_and_the_real_cost_replaces_it() -> None:
    gate = Gate()
    req = VisionRequest(model="vendor/vision-1", prompt="classify", images=[IMG], max_tokens=1000)
    await _client(_catalog(), gate).complete(req, deadline=Deadline.after(60))
    expected = ModelPrice(Decimal("0.0000001"), Decimal("0.0000004"), Decimal(0), Decimal(0)).hold_usd(
        text_chars=len("classify"), images=1, max_tokens=1000
    )
    assert gate.estimates == [expected]
    assert expected != Decimal("0.02")
    assert gate.ticket.settled == Decimal("0.00014")


async def test_a_model_missing_from_the_catalog_falls_back_to_the_flat_estimate() -> None:
    gate = Gate()
    req = VisionRequest(model="vendor/other", prompt="p", images=[IMG])
    await _client(_catalog(), gate).complete(req, deadline=Deadline.after(60))
    assert gate.estimates == [Decimal("0.02")]


async def test_without_a_catalog_the_flat_estimate_is_held() -> None:
    gate = Gate()
    await _client(None, gate).complete(
        VisionRequest(model="vendor/vision-1", prompt="p", images=[IMG]), deadline=Deadline.after(60)
    )
    assert gate.estimates == [Decimal("0.02")]


def test_unused_import_guard() -> None:
    assert PreparedImage
