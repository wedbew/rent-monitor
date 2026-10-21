"""Image-generation clients: what each failure means for the money (RM-450)."""

import base64
import io
import json
from decimal import Decimal

import httpx
import pytest
from PIL import Image
from rm_core.deadline import Deadline
from rm_worker.clients.image_gen import (
    FakeImageGenerator,
    ImageRequest,
    OpenRouterImageGenerator,
    OutcomeUnknown,
    ProviderNotReached,
    ProviderRejected,
    build_payload,
    parse_reply,
)


def jpeg(size: tuple[int, int] = (320, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (90, 120, 150)).save(buf, format="JPEG")
    return buf.getvalue()


def req(prompt: str = "make it nice") -> ImageRequest:
    return ImageRequest("google/gemini-3.1-flash-lite-image", prompt, [jpeg(), jpeg((200, 200))])


def png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 20, 30)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def client(handler: httpx.MockTransport) -> OpenRouterImageGenerator:
    return OpenRouterImageGenerator(
        httpx.AsyncClient(transport=handler), "sk-test-key", "https://or.test/api/v1"
    )


async def test_the_payload_puts_the_room_first_and_every_image_as_a_data_url() -> None:
    payload = build_payload(req())
    assert payload["model"] == "google/gemini-3.1-flash-lite-image"
    assert payload["n"] == 1
    refs = payload["input_references"]
    assert len(refs) == 2
    assert all(
        r["type"] == "image_url" and r["image_url"]["url"].startswith("data:image/jpeg;base64,") for r in refs
    )
    assert base64.b64decode(refs[0]["image_url"]["url"].split(",", 1)[1]) == req().images[0]


async def test_a_good_answer_returns_the_image_and_an_exact_decimal_cost() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        item = {"b64_json": png_b64(), "media_type": "image/png"}
        return httpx.Response(200, text='{"data":[' + json.dumps(item) + '],"usage":{"cost":0.0341}}')

    out = await client(httpx.MockTransport(handler)).generate(req(), deadline=Deadline.after(10))
    assert out.media_type == "image/png"
    assert out.cost_usd == Decimal("0.0341")  # parsed from text, never through float
    assert out.data.startswith(b"\x89PNG")
    assert seen["url"] == "https://or.test/api/v1/images"
    assert seen["auth"] == "Bearer sk-test-key"


async def test_a_missing_cost_is_reported_as_none_not_zero() -> None:
    body = f'{{"data":[{{"b64_json":"{png_b64()}"}}]}}'
    out = await client(httpx.MockTransport(lambda r: httpx.Response(200, text=body))).generate(
        req(), deadline=Deadline.after(10)
    )
    assert out.cost_usd is None


@pytest.mark.parametrize("status", [400, 401, 402, 403, 413, 422, 429, 502])
async def test_definite_refusals_are_not_billed(status: int) -> None:
    gen = client(httpx.MockTransport(lambda r: httpx.Response(status, text="{}")))
    with pytest.raises(ProviderRejected):
        await gen.generate(req(), deadline=Deadline.after(10))


@pytest.mark.parametrize("status", [500, 503, 504, 520])
async def test_other_server_errors_leave_the_spend_unknown(status: int) -> None:
    gen = client(httpx.MockTransport(lambda r: httpx.Response(status, text="oops")))
    with pytest.raises(OutcomeUnknown):
        await gen.generate(req(), deadline=Deadline.after(10))


async def test_a_connect_failure_means_nothing_was_sent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(ProviderNotReached):
        await client(httpx.MockTransport(handler)).generate(req(), deadline=Deadline.after(10))
    with pytest.raises(ProviderNotReached):  # no time left before the call
        await client(httpx.MockTransport(handler)).generate(req(), deadline=Deadline.after(0))


@pytest.mark.parametrize("exc", [httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ReadError])
async def test_a_failure_after_the_request_went_out_is_unknown(exc: type[httpx.TransportError]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc("lost", request=request)

    with pytest.raises(OutcomeUnknown):
        await client(httpx.MockTransport(handler)).generate(req(), deadline=Deadline.after(10))


@pytest.mark.parametrize(
    "body",
    [b"not json", b"{}", b'{"data":[]}', b'{"data":[{"b64_json":"%%%"}]}', b'{"data":[{"b64_json":""}]}'],
)
def test_an_unusable_answer_is_unknown_not_a_free_failure(body: bytes) -> None:
    with pytest.raises(OutcomeUnknown):
        parse_reply(body)


async def test_the_fake_is_deterministic_and_its_markers_select_each_failure() -> None:
    fake = FakeImageGenerator()
    a = await fake.generate(req(), deadline=Deadline.after(5))
    b = await fake.generate(req(), deadline=Deadline.after(5))
    assert (a.data, a.cost_usd) == (b.data, Decimal("0.034000"))
    with Image.open(io.BytesIO(a.data)) as picture:
        assert picture.size == (320, 240)
    for marker, expected in (
        ("FAKE_NOT_REACHED", ProviderNotReached),
        ("FAKE_REJECT", ProviderRejected),
        ("FAKE_UNKNOWN", OutcomeUnknown),
    ):
        with pytest.raises(expected):
            await fake.generate(req(f"x {marker}"), deadline=Deadline.after(5))
    assert (await fake.generate(req("FAKE_NO_COST"), deadline=Deadline.after(5))).cost_usd is None
    assert (await fake.generate(req("FAKE_GARBAGE"), deadline=Deadline.after(5))).data == b"not an image"
    assert fake.calls == 7
