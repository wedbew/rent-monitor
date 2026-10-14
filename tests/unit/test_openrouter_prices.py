"""The price catalog and the budget hold priced from it (RM-246). Offline: a mock HTTP transport only."""

import json
from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest
from rm_worker.clients.openrouter import (
    IMAGE_TOKENS_CEILING,
    TEXT_TOKENS_BASE,
    VisionRequest,
    estimate_cost,
)
from rm_worker.clients.openrouter_prices import (
    RETRY_AFTER_FAILURE_S,
    TTL_S,
    ModelPrice,
    PriceCatalog,
    parse_catalog,
)
from rm_worker.images import PreparedImage

IMG = PreparedImage("https://olxcdn.com/a.jpg", b"jpeg", 10, 10, 1)
FLASH = {
    "id": "google/flash",
    "pricing": {"prompt": "0.0000001", "completion": "0.0000004", "image": "0.0000001"},
}


def body(*models: object) -> bytes:
    return json.dumps({"data": list(models)}).encode()


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def catalog(handler: Callable[[httpx.Request], httpx.Response], clock: Clock | None = None) -> PriceCatalog:
    return PriceCatalog(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        "https://openrouter.test/api/v1/",
        clock=clock or Clock(),
    )


def test_prices_are_parsed_as_decimals() -> None:
    got = parse_catalog(body(FLASH))["google/flash"]
    assert got == ModelPrice(Decimal("0.0000001"), Decimal("0.0000004"), Decimal("0.0000001"))


@pytest.mark.parametrize(
    "pricing",
    [
        {"prompt": "abc", "completion": "0.1"},
        {"prompt": "-1", "completion": "0.000001"},
        {"prompt": "NaN", "completion": "0.000001"},
        {"prompt": "5", "completion": "0.000001"},  # 5 USD per token is a data error
        {"prompt": "0.000001"},
        {"prompt": None, "completion": "0.000001"},
        "free",
    ],
)
def test_implausible_or_incomplete_prices_leave_the_model_out(pricing: object) -> None:
    assert parse_catalog(body({"id": "m/x", "pricing": pricing})) == {}


@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b'{"data": 5}', b'{"data": [1, "x", null]}'])
def test_a_malformed_catalog_is_empty_not_an_error(raw: bytes) -> None:
    assert parse_catalog(raw) == {}


async def test_one_fetch_serves_many_lookups_until_the_ttl() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=body(FLASH))

    clock = Clock()
    c = catalog(handler, clock)
    assert (await c.price("google/flash")) is not None
    assert (await c.price("google/flash")) is not None
    assert await c.price("unknown/model") is None
    assert calls == ["https://openrouter.test/api/v1/models"]
    clock.now += TTL_S + 1
    await c.price("google/flash")
    assert len(calls) == 2


async def test_a_down_catalog_gives_no_price_and_is_not_hammered() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    clock = Clock()
    c = catalog(handler, clock)
    assert await c.price("google/flash") is None
    assert await c.price("google/flash") is None
    assert len(calls) == 1  # backing off
    clock.now += RETRY_AFTER_FAILURE_S + 1
    await c.price("google/flash")
    assert len(calls) == 2


async def test_the_last_good_prices_survive_a_later_outage() -> None:
    state = {"ok": True}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body(FLASH)) if state["ok"] else httpx.Response(500)

    clock = Clock()
    c = catalog(handler, clock)
    assert await c.price("google/flash") is not None
    state["ok"] = False
    clock.now += TTL_S + 1
    assert await c.price("google/flash") is not None


async def test_a_transport_error_is_swallowed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    assert await catalog(handler).price("google/flash") is None


def req(images: int, max_tokens: int = 1800) -> VisionRequest:
    return VisionRequest(model="google/flash", prompt="x" * 300, images=[IMG] * images, max_tokens=max_tokens)


def test_the_hold_is_input_price_times_tokens_plus_the_output_ceiling() -> None:
    price = ModelPrice(Decimal("0.0000001"), Decimal("0.0000004"), Decimal("0.0000001"))
    tokens_in = TEXT_TOKENS_BASE + 100 + 11 * IMAGE_TOKENS_CEILING
    expected = tokens_in * price.prompt + 11 * price.image + 1800 * price.completion
    got = estimate_cost(req(11), price)
    assert got >= expected
    assert got - expected < Decimal("0.000001")  # rounded up to a micro-dollar, nothing more


def test_the_hold_covers_the_measured_real_cost_with_room() -> None:
    """The first live call (11 photos, 3258 prompt and 175 completion tokens) cost 0.0003958 USD."""
    price = ModelPrice(Decimal("0.0000001"), Decimal("0.0000004"), Decimal("0.0000001"))
    hold = estimate_cost(req(11), price)
    assert Decimal("0.0003958") < hold < Decimal("0.005")  # a ceiling, but not the old 0.02 guess


def test_more_images_and_a_pricier_model_cost_more() -> None:
    cheap = ModelPrice(Decimal("0.0000001"), Decimal("0.0000004"), Decimal(0))
    dear = ModelPrice(Decimal("0.000003"), Decimal("0.000015"), Decimal("0.0048"))
    assert estimate_cost(req(25), cheap) > estimate_cost(req(1), cheap)
    assert estimate_cost(req(5), dear) > estimate_cost(req(5), cheap) * 10
