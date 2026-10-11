"""The fetch client against a fake transport, fake slots and a fake breaker (no network, no sleeping)."""

import json
import random
from dataclasses import dataclass, field

import pytest
from rm_contracts.problems import ProblemCode
from rm_core.deadline import Deadline
from rm_worker.clients.otodom import (
    MAX_ATTEMPTS,
    FetchError,
    ListingGone,
    OtodomClient,
    RawResponse,
    UpstreamBlocked,
    UpstreamSchemaDrift,
    classify,
    parse_retry_after,
)

OFFER_URL = "https://www.otodom.pl/pl/oferta/x-ID4CpHB"


def page(ad: object, *, wrap: str = "props") -> bytes:
    data = {"props": {"pageProps": {"ad": ad}}} if wrap == "props" else {"other": 1}
    return (
        f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'
    ).encode()


def ok(ad: object | None = None, **kw: object) -> RawResponse:
    return RawResponse(
        200, {}, page(ad if ad is not None else {"id": 1, "title": "Flat"}), str(kw.get("url", OFFER_URL))
    )


@dataclass
class FakeTransport:
    responses: list[RawResponse | Exception]
    calls: int = 0
    timeouts: list[float] = field(default_factory=list)

    async def get(self, url: str, *, headers: dict[str, str], total_s: float) -> RawResponse:
        self.calls += 1
        self.timeouts.append(total_s)
        item = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


@dataclass
class FakeSlots:
    wait: float = 0.0
    busy_polls: int = 0
    reserved: int = 0

    async def reserve(self, host: str) -> float:
        self.reserved += 1
        return self.wait

    async def audit_queue_busy(self) -> bool:
        if self.busy_polls > 0:
            self.busy_polls -= 1
            return True
        return False


@dataclass
class FakeBreaker:
    open_for: int | None = None
    tripped: list[str] = field(default_factory=list)

    async def is_open(self, host: str) -> int | None:
        return self.open_for

    async def trip(self, host: str, reason: str) -> None:
        self.tripped.append(reason)
        self.open_for = 900


class Sleeper:
    def __init__(self) -> None:
        self.slept: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)


def make(
    responses: list[RawResponse | Exception],
    *,
    slots: FakeSlots | None = None,
    breaker: FakeBreaker | None = None,
) -> tuple[OtodomClient, FakeTransport, FakeSlots, FakeBreaker, Sleeper]:
    transport = FakeTransport(responses)
    slots = slots or FakeSlots()
    breaker = breaker or FakeBreaker()
    sleeper = Sleeper()
    client = OtodomClient(transport, slots, breaker, sleep=sleeper, rng=random.Random(1))  # noqa: S311
    return client, transport, slots, breaker, sleeper


# ---- classification ----
@pytest.mark.parametrize("status", [404, 410])
def test_gone_statuses(status: int) -> None:
    with pytest.raises(ListingGone):
        classify(RawResponse(status, {}, b"", OFFER_URL))


def test_redirect_to_a_search_page_means_the_listing_is_gone() -> None:
    with pytest.raises(ListingGone):
        classify(ok(url="https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie"))


@pytest.mark.parametrize("status", [403, 429, 500, 502, 503, 302])
def test_blocking_statuses(status: int) -> None:
    with pytest.raises(UpstreamBlocked) as err:
        classify(RawResponse(status, {"retry-after": "7"}, b"", OFFER_URL))
    assert err.value.retry_after_s == 7.0
    assert err.value.code is ProblemCode.UPSTREAM_BLOCKED


def test_challenge_page_and_missing_next_data_are_blocked() -> None:
    with pytest.raises(UpstreamBlocked, match="challenge"):
        classify(RawResponse(200, {}, b"<html>Just a moment... captcha</html>", OFFER_URL))
    with pytest.raises(UpstreamBlocked, match="__NEXT_DATA__"):
        classify(RawResponse(200, {}, b"<html>hello</html>", OFFER_URL))


@pytest.mark.parametrize("ad", [None, [], "x", {}, {"id": 0}, {"title": "no id"}])
def test_schema_drift_on_a_bad_ad(ad: object) -> None:
    with pytest.raises(UpstreamSchemaDrift):
        classify(RawResponse(200, {}, page(ad), OFFER_URL))


def test_schema_drift_on_wrong_envelope_or_invalid_json() -> None:
    with pytest.raises(UpstreamSchemaDrift):
        classify(RawResponse(200, {}, page({}, wrap="other"), OFFER_URL))
    broken = b'<script id="__NEXT_DATA__" type="application/json">{not json</script>'
    with pytest.raises(UpstreamSchemaDrift):
        classify(RawResponse(200, {}, broken, OFFER_URL))


def test_retry_after_parsing() -> None:
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("soon") is None
    assert parse_retry_after("99999999") == 86_400.0
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0


# ---- client policy ----
async def test_success_returns_a_stable_hash_and_the_validated_url() -> None:
    client, transport, slots, _, _ = make([ok({"id": 1, "b": 2, "a": 1})])
    first = await client.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    client2, *_ = make([ok({"a": 1, "id": 1, "b": 2})])  # same content, different key order
    second = await client2.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    assert first.content_sha256 == second.content_sha256
    assert first.url == "https://www.otodom.pl/pl/oferta/ID4CpHB"
    assert transport.calls == 1
    assert slots.reserved == 1


async def test_blocked_is_retried_with_backoff_then_trips_the_breaker() -> None:
    client, transport, _, breaker, sleeper = make([RawResponse(429, {}, b"", OFFER_URL)])
    with pytest.raises(UpstreamBlocked):
        await client.fetch_listing("ID4CpHB", deadline=Deadline.after(600))
    assert transport.calls == MAX_ATTEMPTS
    assert len(sleeper.slept) == MAX_ATTEMPTS - 1
    assert sleeper.slept == sorted(sleeper.slept)  # exponential growth beats the jitter window
    assert all(1.0 <= s <= 60.0 for s in sleeper.slept)
    assert breaker.tripped == ["upstream_blocked"]


async def test_a_recovering_upstream_succeeds_on_a_later_attempt() -> None:
    client, transport, _, breaker, _ = make([RawResponse(503, {}, b"", OFFER_URL), ok()])
    result = await client.fetch_listing("ID4CpHB", deadline=Deadline.after(600))
    assert result.ad["id"] == 1
    assert transport.calls == 2
    assert breaker.tripped == []


async def test_retry_after_is_honoured() -> None:
    client, _, _, _, sleeper = make([RawResponse(429, {"retry-after": "30"}, b"", OFFER_URL), ok()])
    await client.fetch_listing("ID4CpHB", deadline=Deadline.after(600))
    assert sleeper.slept[0] >= 30.0


async def test_retry_after_longer_than_the_deadline_fails_at_once_and_trips() -> None:
    client, transport, _, breaker, sleeper = make([RawResponse(429, {"retry-after": "3600"}, b"", OFFER_URL)])
    with pytest.raises(UpstreamBlocked):
        await client.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    assert transport.calls == 1
    assert sleeper.slept == []
    assert breaker.tripped == ["upstream_blocked"]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (RawResponse(404, {}, b"", OFFER_URL), ListingGone),
        (RawResponse(200, {}, page({}), OFFER_URL), UpstreamSchemaDrift),
    ],
)
async def test_gone_and_drift_are_not_retried_and_do_not_trip(
    response: RawResponse, error: type[FetchError]
) -> None:
    client, transport, _, breaker, _ = make([response])
    with pytest.raises(error):
        await client.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    assert transport.calls == 1
    assert breaker.tripped == []


async def test_open_breaker_blocks_without_touching_the_network() -> None:
    client, transport, slots, _, _ = make([ok()], breaker=FakeBreaker(open_for=600))
    with pytest.raises(UpstreamBlocked) as err:
        await client.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    assert err.value.retry_after_s == 600.0
    assert transport.calls == 0
    assert slots.reserved == 0


async def test_slot_wait_happens_via_sleep_and_a_slot_beyond_the_deadline_fails() -> None:
    client, _, _, _, sleeper = make([ok()], slots=FakeSlots(wait=2.5))
    await client.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    assert sleeper.slept == [2.5]
    late, transport, *_ = make([ok()], slots=FakeSlots(wait=500.0))
    with pytest.raises(UpstreamBlocked, match="slot"):
        await late.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    assert transport.calls == 0


async def test_batch_yields_to_audits_but_interactive_does_not() -> None:
    batch, _, slots, _, sleeper = make([ok()], slots=FakeSlots(busy_polls=3))
    await batch.fetch_listing("ID4CpHB", deadline=Deadline.after(60), priority="batch")
    assert sleeper.slept == [1.0, 1.0, 1.0]
    assert slots.busy_polls == 0
    interactive, _, slots2, _, sleeper2 = make([ok()], slots=FakeSlots(busy_polls=3))
    await interactive.fetch_listing("ID4CpHB", deadline=Deadline.after(60))
    assert sleeper2.slept == []
    assert slots2.busy_polls == 3


async def test_transport_timeout_is_capped_by_the_remaining_deadline() -> None:
    client, transport, *_ = make([ok()])
    await client.fetch_listing("ID4CpHB", deadline=Deadline.after(7))
    assert transport.timeouts[0] <= 7.0
