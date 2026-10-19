"""Search-page parsing and the search fetch path, against hand-built pages (no network, no seller data)."""

import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from rm_core.deadline import Deadline
from rm_worker.clients.otodom import (
    OtodomClient,
    RawResponse,
    UpstreamBlocked,
    UpstreamSchemaDrift,
    classify_search,
)
from rm_worker.importers.otodom_rental import parse_offers

LOC = "mazowieckie/warszawa/warszawa/warszawa"
RESULTS = f"https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/{LOC}?page=1"


def offer(offer_id: int = 1, rent: object = 3000, area: object = 50, **over: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": offer_id,
        "estate": "FLAT",
        "transaction": "RENT",
        "hidePrice": False,
        "areaInSquareMeters": area,
        "totalPrice": {"value": rent, "currency": "PLN"},
        "rentPrice": {"value": 700, "currency": "PLN"},  # the admin fee (czynsz): never a comparable rent
        "title": "x",
    }
    return base | over


def page(items: list[Any], total_pages: int = 3) -> RawResponse:
    ads = {"items": items, "pagination": {"totalPages": total_pages}}
    data = {"props": {"pageProps": {"data": {"searchAds": ads}}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    return RawResponse(200, {}, html.encode(), RESULTS)


def test_valid_offers_are_kept_with_decimal_money() -> None:
    found, pages = parse_offers(
        {"items": [offer(1, 3000, 50), offer(2, 4500.5, 60.5)], "pagination": {"totalPages": 7}}
    )
    assert pages == 7
    assert [(i, str(c.monthly_rent_pln), str(c.area_m2)) for i, c in found] == [
        (1, "3000", "50"),
        (2, "4500.5", "60.5"),
    ]


@pytest.mark.parametrize(
    "bad",
    [
        offer(estate="HOUSE"),
        offer(transaction="SELL"),
        offer(hidePrice=True),
        offer(rent=None),
        offer(rent="abc"),
        offer(rent=True),
        offer(area=None),
        offer(area=0),
        offer(area=5000),
        offer(rent=100),  # below the plausibility floor
        offer(rent=3000, area=401),  # above the area bound
        offer(offer_id=True),
        offer(totalPrice={"value": 3000, "currency": "EUR"}),
        offer(totalPrice="3000"),
        offer(totalPrice=None),
        "not an object",
        None,
    ],
)
def test_unusable_offers_are_dropped(bad: object) -> None:
    assert parse_offers({"items": [bad]})[0] == []


def test_price_per_m2_outside_the_engine_range_is_dropped() -> None:
    assert parse_offers({"items": [offer(rent=60_000, area=8)]})[0] == []  # 7500 PLN/m2
    assert parse_offers({"items": [offer(rent=300, area=300)]})[0] == []  # 1 PLN/m2


def test_missing_or_odd_containers_do_not_raise() -> None:
    assert parse_offers({}) == ([], 1)
    assert parse_offers({"items": "x", "pagination": 5}) == ([], 1)
    assert parse_offers({"items": [], "pagination": {"totalPages": True}})[1] == 1
    assert parse_offers({"items": [], "pagination": {"totalPages": 10**9}})[1] == 1000


def test_oversized_pages_are_truncated() -> None:
    found, _ = parse_offers({"items": [offer(i) for i in range(1, 500)]})
    assert len(found) == 100


def test_classify_search_returns_search_ads() -> None:
    assert classify_search(page([offer()]))["items"][0]["id"] == 1


def test_classify_search_rejects_other_pages_and_drift() -> None:
    redirected = RawResponse(200, {}, page([]).body, "https://www.otodom.pl/pl/oferta/x-ID1")
    with pytest.raises(UpstreamSchemaDrift):
        classify_search(redirected)
    no_data = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'
    with pytest.raises(UpstreamSchemaDrift):
        classify_search(RawResponse(200, {}, no_data.encode(), RESULTS))
    with pytest.raises(UpstreamBlocked):
        classify_search(RawResponse(429, {"retry-after": "5"}, b"", RESULTS))
    with pytest.raises(UpstreamBlocked):
        classify_search(RawResponse(200, {}, b"<html>captcha</html>", RESULTS))


@dataclass
class Transport:
    response: RawResponse
    urls: list[str] = field(default_factory=list[str])

    async def get(self, url: str, *, headers: dict[str, str], total_s: float) -> RawResponse:
        self.urls.append(url)
        return self.response


class Slots:
    def __init__(self) -> None:
        self.busy_checks = 0

    async def reserve(self, host: str) -> float:
        return 0.0

    async def audit_queue_busy(self) -> bool:
        self.busy_checks += 1
        return False


class Breaker:
    async def is_open(self, host: str) -> int | None:
        return None

    async def trip(self, host: str, reason: str) -> None:
        raise AssertionError("not expected")


async def test_search_url_is_built_from_a_validated_location_and_defaults_to_batch_priority() -> None:
    transport, slots = Transport(page([offer()])), Slots()
    client = OtodomClient(transport=transport, slots=slots, breaker=Breaker())
    ads = await client.fetch_rental_search(LOC, 2, deadline=Deadline.after(30))
    assert ads["items"][0]["id"] == 1
    assert transport.urls == [f"https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/{LOC}?page=2"]
    assert slots.busy_checks >= 1  # batch priority asks whether audits are waiting


@pytest.mark.parametrize(
    ("location", "page_no"),
    [
        ("../etc/passwd", 1),
        ("a//b", 1),
        ("A/B", 1),
        ("a?x=1", 1),
        ("https://evil.test/", 1),
        ("", 1),
        (LOC, 0),
        (LOC, 401),
    ],
)
async def test_unsafe_location_or_page_is_refused_before_any_request(location: str, page_no: int) -> None:
    transport = Transport(page([]))
    client = OtodomClient(transport=transport, slots=Slots(), breaker=Breaker())
    with pytest.raises(ValueError, match="invalid"):
        await client.fetch_rental_search(location, page_no, deadline=Deadline.after(30))
    assert transport.urls == []


@pytest.mark.invariant
def test_invariant_admin_fee_is_never_a_comparable_rent() -> None:
    """Invariant 3: in search results `rentPrice` is the czynsz and `totalPrice` the advertised rent."""
    found, _ = parse_offers(
        {"items": [offer(1, rent=2000, area=42, rentPrice={"value": 700, "currency": "PLN"})]}
    )
    assert [str(c.monthly_rent_pln) for _, c in found] == ["2000"]
    only_fee = offer(2, area=42, totalPrice=None, rentPrice={"value": 700, "currency": "PLN"})
    assert parse_offers({"items": [only_fee]})[0] == []  # a fee alone must never become a rent
