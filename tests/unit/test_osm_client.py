"""Nominatim and Overpass clients against a fake transport: policy, throttling, retries, hostile answers."""

import json
import random
from dataclasses import dataclass, field
from decimal import Decimal as D

import httpx
import pytest
from deal_analyzer.geo import PoiCategory
from rm_core.deadline import Deadline
from rm_worker.clients.osm import (
    GeoUnavailable,
    OsmClient,
    build_overpass_query,
    parse_pois,
)

UA = "RentMonitor/1.0 (ops@example.test)"


@dataclass
class Slots:
    wait: float = 0.0
    hosts: list[str] = field(default_factory=list)

    async def reserve(self, host: str) -> float:
        self.hosts.append(host)
        return self.wait

    async def audit_queue_busy(self) -> bool:
        return False


class Sleeper:
    def __init__(self) -> None:
        self.slept: list[float] = []

    async def __call__(self, s: float) -> None:
        self.slept.append(s)


def make(handler, *, ua: str = UA, wait: float = 0.0):
    nom, ovp, sleeper = Slots(wait=wait), Slots(), Sleeper()
    client = OsmClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ua,
        nom,
        ovp,
        sleep=sleeper,
        rng=random.Random(1),  # noqa: S311
    )
    return client, nom, ovp, sleeper


def hit(lat: str = "52.2297", lon: str = "21.0122") -> httpx.Response:
    return httpx.Response(200, json=[{"lat": lat, "lon": lon, "display_name": "x"}])


async def test_geocode_returns_exact_decimals_and_identifies_itself() -> None:
    seen: list[httpx.Request] = []
    client, nom, _, _ = make(lambda r: seen.append(r) or hit())
    point = await client.geocode("Marszałkowska 1, Warszawa", deadline=Deadline.after(30))
    assert point is not None
    assert (point.latitude, point.longitude) == (D("52.2297"), D("21.0122"))
    assert seen[0].headers["user-agent"] == UA
    assert seen[0].url.params["countrycodes"] == "pl"
    assert seen[0].url.params["limit"] == "1"
    assert nom.hosts == ["nominatim.openstreetmap.org"]  # one shared 1 req/s slot per call


@pytest.mark.parametrize("ua", ["", "   ", "RentMonitor/1.0 (set-an-ops-contact)"])
async def test_the_placeholder_or_empty_user_agent_is_refused_without_any_request(ua: str) -> None:
    calls = []
    client, nom, _, _ = make(lambda r: calls.append(r) or hit(), ua=ua)
    with pytest.raises(GeoUnavailable, match="NOMINATIM_USER_AGENT"):
        await client.geocode("x", deadline=Deadline.after(30))
    with pytest.raises(GeoUnavailable):
        await client.pois(D("52.2"), D("21.0"), 800, deadline=Deadline.after(30))
    assert calls == []
    assert nom.hosts == []


async def test_no_result_and_places_outside_poland_are_none() -> None:
    empty, *_ = make(lambda r: httpx.Response(200, json=[]))
    assert await empty.geocode("nowhere", deadline=Deadline.after(30)) is None
    abroad, *_ = make(lambda r: hit("40.7128", "-74.0060"))
    assert await abroad.geocode("New York", deadline=Deadline.after(30)) is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json={"a": 1}),
        httpx.Response(200, json=[{"lat": "x", "lon": "y"}]),
        httpx.Response(200, json=[{"lat": "1" * 40, "lon": "2"}]),
        httpx.Response(200, json=[{}]),
        httpx.Response(403),
        httpx.Response(200, content=b"x" * (3 * 1024 * 1024)),
    ],
)
async def test_bad_answers_degrade_instead_of_crashing(response: httpx.Response) -> None:
    client, *_ = make(lambda r: response)
    with pytest.raises(GeoUnavailable):
        await client.geocode("x", deadline=Deadline.after(30))


async def test_rate_limits_are_retried_once_then_succeed_or_degrade() -> None:
    replies = iter([httpx.Response(429), hit()])
    client, nom, _, sleeper = make(lambda r: next(replies))
    assert await client.geocode("x", deadline=Deadline.after(30)) is not None
    assert len(nom.hosts) == 2  # each attempt reserved its own slot
    assert sleeper.slept
    always, *_ = make(lambda r: httpx.Response(503))
    with pytest.raises(GeoUnavailable):
        await always.geocode("x", deadline=Deadline.after(30))


async def test_transport_errors_are_retried_then_reported() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    client, *_ = make(boom)
    with pytest.raises(GeoUnavailable, match="unreachable"):
        await client.geocode("x", deadline=Deadline.after(30))


async def test_a_slot_beyond_the_deadline_is_not_waited_for() -> None:
    calls = []
    client, _, _, sleeper = make(lambda r: calls.append(r) or hit(), wait=500.0)
    with pytest.raises(GeoUnavailable, match="slot"):
        await client.geocode("x", deadline=Deadline.after(5))
    assert calls == []
    assert sleeper.slept == []


# ---- Overpass ----
def test_the_overpass_query_contains_only_numbers_and_fixed_tags() -> None:
    q = build_overpass_query(D("52.22971234"), D("21.01221234"), 800)
    assert "(around:800,52.2297,21.0122)" in q
    assert q.startswith("[out:json][timeout:20];")
    assert q.endswith("out center 500;")
    assert "bus_stop" in q
    assert "school" in q
    assert "supermarket" in q
    assert "park" in q


def test_pois_are_parsed_by_tag_with_centers_and_junk_ignored() -> None:
    body = {
        "elements": [
            {"type": "node", "lat": 52.23, "lon": 21.01, "tags": {"highway": "bus_stop"}},
            {"type": "node", "lat": 52.231, "lon": 21.011, "tags": {"railway": "station"}},
            {"type": "way", "center": {"lat": 52.24, "lon": 21.02}, "tags": {"amenity": "school"}},
            {"type": "node", "lat": 52.25, "lon": 21.03, "tags": {"shop": "supermarket"}},
            {"type": "way", "center": {"lat": 52.26, "lon": 21.04}, "tags": {"leisure": "park"}},
            {
                "type": "node",
                "lat": 52.27,
                "lon": 21.05,
                "tags": {"shop": "bakery"},
            },  # not a tracked category
            {"type": "node", "tags": {"highway": "bus_stop"}},  # no coordinates
            {"type": "node", "lat": 999, "lon": 1, "tags": {"highway": "bus_stop"}},  # impossible latitude
            "junk",
            None,
        ]
    }
    pois = parse_pois(body)
    assert [p.category for p in pois] == [
        PoiCategory.TRANSIT,
        PoiCategory.TRANSIT,
        PoiCategory.SCHOOL,
        PoiCategory.SHOP,
        PoiCategory.PARK,
    ]
    assert pois[0].latitude == D("52.23")  # exact via the float's text form


def test_a_poi_answer_without_elements_is_unavailable_and_huge_lists_are_capped() -> None:
    with pytest.raises(GeoUnavailable):
        parse_pois({"remark": "runtime error"})
    many = {"elements": [{"lat": 52.0, "lon": 21.0, "tags": {"highway": "bus_stop"}}] * 900}
    assert len(parse_pois(many)) == 500


async def test_pois_request_goes_to_overpass_with_its_own_slot() -> None:
    seen: list[httpx.Request] = []
    client, nom, ovp, _ = make(lambda r: seen.append(r) or httpx.Response(200, json={"elements": []}))
    assert await client.pois(D("52.2297"), D("21.0122"), 800, deadline=Deadline.after(30)) == ()
    assert ovp.hosts == ["overpass-api.de"]
    assert nom.hosts == []
    assert "around:800" in json.dumps(dict(seen[0].url.params))
