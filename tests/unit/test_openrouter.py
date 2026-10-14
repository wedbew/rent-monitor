import asyncio
import base64
import json
import random
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from rm_core.ai_budget import CallUsage
from rm_core.deadline import Deadline
from rm_worker.clients.openrouter import (
    MAX_ATTEMPTS,
    OpenRouterClient,
    VisionDisabled,
    VisionRequest,
    VisionUnavailable,
    build_payload,
    estimate_cost,
    parse_completion,
)
from rm_worker.clients.openrouter_prices import ModelPrice
from rm_worker.images import PreparedImage

IMG = PreparedImage("https://olxcdn.com/a.jpg", b"\xff\xd8jpegbytes", 10, 10, 1)
OK_BODY = {
    "model": "vendor/vision-1",
    "choices": [{"message": {"role": "assistant", "content": '{"condition": "good"}'}}],
    "usage": {"prompt_tokens": 120, "completion_tokens": 30, "cost": 0.00014},
}


class Ticket:
    def __init__(self) -> None:
        self.settled: Decimal | None = None
        self.usage: CallUsage | None = None
        self.released = False

    async def settle(self, actual_usd: Decimal, usage: CallUsage | None = None) -> None:
        self.settled = actual_usd
        self.usage = usage

    async def release(self) -> None:
        self.released = True


class Gate:
    def __init__(self, *, open_: bool = True) -> None:
        self.open_ = open_
        self.ticket = Ticket()
        self.estimates: list[Decimal] = []

    async def reserve(self, estimate_usd: Decimal) -> Ticket | None:
        self.estimates.append(estimate_usd)
        return self.ticket if self.open_ else None


class Limiter:
    def __init__(self) -> None:
        self.entered = 0
        self.active = 0

    @asynccontextmanager
    async def slot(self, max_wait_s: float):
        self.entered += 1
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1


class Sleeper:
    def __init__(self) -> None:
        self.slept: list[float] = []

    async def __call__(self, s: float) -> None:
        self.slept.append(s)


def make(
    handler, *, gate: Gate | None = None, key: str = "k-test"
) -> tuple[OpenRouterClient, Gate, Limiter, Sleeper]:
    gate = gate or Gate()
    limiter, sleeper = Limiter(), Sleeper()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = OpenRouterClient(
        http,
        key,
        gate,
        limiter,
        Decimal("0.02"),
        sleep=sleeper,
        rng=random.Random(3),  # noqa: S311
    )
    return client, gate, limiter, sleeper


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=json.dumps(OK_BODY).encode())


REQ = VisionRequest(
    model="vendor/vision-1", prompt="classify", images=[IMG], system="you are strict", json_mode=True
)


# ---- payload and parsing ----
def test_payload_carries_system_prompt_images_and_json_mode() -> None:
    payload = build_payload(REQ)
    assert payload["model"] == "vendor/vision-1"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0] == {"role": "system", "content": "you are strict"}
    parts = payload["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": "classify"}
    url = parts[1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == IMG.jpeg


def test_cost_is_parsed_as_an_exact_decimal() -> None:
    result = parse_completion(json.dumps(OK_BODY).encode())
    assert result.cost_usd == Decimal("0.00014")
    assert isinstance(result.cost_usd, Decimal)
    assert (result.prompt_tokens, result.completion_tokens) == (120, 30)


def test_missing_cost_is_none_not_zero() -> None:
    body = {**OK_BODY, "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    assert parse_completion(json.dumps(body).encode()).cost_usd is None


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not json",
        b"{}",
        b'{"choices": []}',
        b'{"choices":[{"message":{"content":""}}]}',
        b'{"choices":[{"message":{}}]}',
        b'{"choices":[{"message":{"content":"x"}}],"usage":{"cost":-1}}',
    ],
)
def test_unusable_responses_degrade_instead_of_crashing(body: bytes) -> None:
    with pytest.raises(VisionUnavailable):
        parse_completion(body)


# ---- budget ----
async def test_exhausted_budget_makes_no_http_call() -> None:
    calls = []
    client, gate, limiter, _ = make(lambda r: calls.append(r) or ok(r), gate=Gate(open_=False))
    with pytest.raises(VisionDisabled):
        await client.complete(REQ, deadline=Deadline.after(60))
    assert calls == []
    assert limiter.entered == 0
    assert gate.estimates == [Decimal("0.02")]


async def test_missing_api_key_disables_vision() -> None:
    client, gate, *_ = make(ok, key="")
    with pytest.raises(VisionDisabled):
        await client.complete(REQ, deadline=Deadline.after(60))
    assert gate.estimates == []


async def test_success_settles_the_actual_cost() -> None:
    client, gate, limiter, _ = make(ok)
    result = await client.complete(REQ, deadline=Deadline.after(60))
    assert result.content == '{"condition": "good"}'
    assert gate.ticket.settled == Decimal("0.00014")
    assert gate.ticket.released is False
    assert limiter.entered == 1
    assert limiter.active == 0


async def test_settle_receives_model_tokens_and_the_audit_id() -> None:
    audit = uuid4()
    client, gate, *_ = make(ok)
    await client.complete(
        VisionRequest(model="vendor/vision-1", prompt="p", images=[IMG], audit_id=audit),
        deadline=Deadline.after(60),
    )
    assert gate.ticket.usage == CallUsage(
        model="vendor/vision-1", prompt_tokens=120, completion_tokens=30, estimated=False, audit_id=audit
    )


async def test_an_unreported_cost_is_marked_as_estimated_in_the_usage() -> None:
    body = {**OK_BODY, "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    client, gate, *_ = make(lambda r: httpx.Response(200, content=json.dumps(body).encode()))
    await client.complete(REQ, deadline=Deadline.after(60))
    assert gate.ticket.usage is not None
    assert gate.ticket.usage.estimated is True


async def test_unreported_cost_settles_the_estimate() -> None:
    body = {**OK_BODY, "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    client, gate, *_ = make(lambda r: httpx.Response(200, content=json.dumps(body).encode()))
    await client.complete(REQ, deadline=Deadline.after(60))
    assert gate.ticket.settled == Decimal("0.02")


async def test_request_carries_bearer_key_and_never_logs_it(caplog: pytest.LogCaptureFixture) -> None:
    seen: list[httpx.Request] = []
    client, *_ = make(lambda r: seen.append(r) or ok(r), key="sk-or-secret-value")
    await client.complete(REQ, deadline=Deadline.after(60))
    assert seen[0].headers["authorization"] == "Bearer sk-or-secret-value"
    assert str(seen[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert "sk-or-secret-value" not in caplog.text


# ---- retries and failures ----
async def test_rate_limit_then_success_retries_and_settles_once() -> None:
    responses = iter([httpx.Response(429, headers={"retry-after": "5"}), httpx.Response(503), None])

    def handler(request: httpx.Request) -> httpx.Response:
        nxt = next(responses)
        return nxt if nxt is not None else ok(request)

    client, gate, _, sleeper = make(handler)
    result = await client.complete(REQ, deadline=Deadline.after(120))
    assert result.model == "vendor/vision-1"
    assert len(sleeper.slept) == 2
    assert sleeper.slept[0] >= 5.0  # Retry-After honoured
    assert gate.ticket.settled is not None


async def test_three_failures_become_vision_unavailable_and_release_the_reservation() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(502)

    client, gate, limiter, _ = make(handler)
    with pytest.raises(VisionUnavailable, match="3 attempts"):
        await client.complete(REQ, deadline=Deadline.after(120))
    assert calls == MAX_ATTEMPTS
    assert gate.ticket.released is True
    assert gate.ticket.settled is None
    assert limiter.active == 0


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
async def test_client_errors_are_not_retried(status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"error": {"code": status, "message": "nope"}})

    client, gate, *_ = make(handler)
    with pytest.raises(VisionUnavailable, match=str(status)):
        await client.complete(REQ, deadline=Deadline.after(60))
    assert calls == 1
    assert gate.ticket.released is True


async def test_transport_errors_and_timeouts_are_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("boom", request=request)
        return ok(request)

    client, *_ = make(handler)
    assert (await client.complete(REQ, deadline=Deadline.after(60))).content
    assert calls == 2


async def test_a_retry_after_longer_than_the_deadline_fails_at_once() -> None:
    client, gate, _, sleeper = make(lambda r: httpx.Response(429, headers={"retry-after": "3000"}))
    with pytest.raises(VisionUnavailable, match="time left"):
        await client.complete(REQ, deadline=Deadline.after(60))
    assert sleeper.slept == []
    assert gate.ticket.released is True


async def test_oversized_responses_are_refused() -> None:
    client, gate, *_ = make(lambda r: httpx.Response(200, content=b"x" * (3 * 1024 * 1024)))
    with pytest.raises(VisionUnavailable, match="too large"):
        await client.complete(REQ, deadline=Deadline.after(60))
    assert gate.ticket.released is True


async def test_cancellation_releases_the_reservation_and_the_slot() -> None:
    started = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.sleep(30)
        return ok(request)

    client, gate, limiter, _ = make(handler)
    task = asyncio.create_task(client.complete(REQ, deadline=Deadline.after(120)))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert gate.ticket.released is True
    assert limiter.active == 0


async def test_an_expired_deadline_makes_no_call() -> None:
    calls = []
    client, gate, *_ = make(lambda r: calls.append(r) or ok(r))
    with pytest.raises(VisionUnavailable):
        await client.complete(REQ, deadline=Deadline.after(0))
    assert calls == []
    assert gate.ticket.released is True


# ---- the hold comes from the price catalog (RM-246) ----
class Prices:
    def __init__(self, price: "ModelPrice | None") -> None:
        self._price = price

    async def price(self, model: str) -> "ModelPrice | None":
        return self._price


async def test_the_budget_hold_is_priced_from_the_catalog_and_settles_at_the_real_cost() -> None:
    client, gate, _, _ = make(ok)
    client.prices = Prices(ModelPrice(Decimal("0.0000001"), Decimal("0.0000004"), Decimal("0.0000001")))
    await client.complete(REQ, deadline=Deadline.after(30))
    (hold,) = gate.estimates
    assert Decimal("0.0003") < hold < Decimal("0.01")  # not the flat 0.02
    assert hold == estimate_cost(REQ, client.prices._price)  # type: ignore[attr-defined]
    assert gate.ticket.settled == Decimal("0.00014")  # the provider's real cost replaces the hold


async def test_without_a_catalog_price_the_flat_fallback_is_held() -> None:
    client, gate, _, _ = make(ok)
    client.prices = Prices(None)
    await client.complete(REQ, deadline=Deadline.after(30))
    assert gate.estimates == [Decimal("0.02")]


async def test_when_the_provider_reports_no_cost_the_priced_hold_is_what_is_recorded() -> None:
    body_no_cost = {**OK_BODY, "usage": {"prompt_tokens": 120, "completion_tokens": 30}}
    client, gate, _, _ = make(lambda r: httpx.Response(200, content=json.dumps(body_no_cost).encode()))
    client.prices = Prices(ModelPrice(Decimal("0.0000001"), Decimal("0.0000004"), Decimal(0)))
    await client.complete(REQ, deadline=Deadline.after(30))
    assert gate.ticket.settled == gate.estimates[0]
    assert gate.ticket.usage is not None
    assert gate.ticket.usage.estimated is True
