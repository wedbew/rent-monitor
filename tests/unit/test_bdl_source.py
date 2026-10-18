"""BDL source client and validator against hand-built fixtures (test-only metric ids, no network)."""

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal as D
from pathlib import Path

import httpx
import pytest
from rm_contracts.location_context import (
    MetricDefinition,
    ObservationStatus,
    SelectionStatus,
    TerritoryLevel,
)
from rm_core.deadline import Deadline
from rm_worker.clients.bdl import (
    BdlClient,
    BdlCursor,
    BdlPage,
    BdlQuotaExhausted,
    BdlUnavailable,
    BdlValidationError,
    QuotaWindow,
    validate_page,
)

FIX = Path(__file__).parent.parent / "fixtures" / "bdl"
UNITS = frozenset({"T000000000001", "T000000000002", "T000000000003", "T000000000004"})
CURSOR = BdlCursor("TEST-VAR-1", TerritoryLevel.gmina, 2022)


def metric(**kw: object) -> MetricDefinition:
    base: dict[str, object] = {
        "key": "test_only_metric",
        "version": 1,
        "name_pl": "Metryka testowa",
        "unit": "osoba",
        "native_level": TerritoryLevel.gmina,
        "published_levels": frozenset({TerritoryLevel.gmina}),
        "min_value": D(0),
        "selection": SelectionStatus.deferred,
        "bdl_variable_id": "TEST-VAR-1",
    }
    return MetricDefinition.model_validate(base | kw)


def page(name: str) -> BdlPage:
    body = (FIX / name).read_bytes()
    return BdlPage(body, hashlib.sha256(body).hexdigest(), None)


@dataclass
class Slots:
    hosts: list[str] = field(default_factory=lambda: [])

    async def reserve(self, host: str) -> float:
        self.hosts.append(host)
        return 0.0

    async def audit_queue_busy(self) -> bool:
        return False


class Sleeper:
    def __init__(self) -> None:
        self.slept: list[float] = []

    async def __call__(self, s: float) -> None:
        self.slept.append(s)


def make(handler, *, max_requests: int = 10, client_id: str | None = None):
    slots, sleeper = Slots(), Sleeper()
    client = BdlClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        slots,
        QuotaWindow(max_requests),
        client_id=client_id,
        sleep=sleeper,
    )
    return client, slots, sleeper


def ok(name: str) -> httpx.Response:
    return httpx.Response(200, content=(FIX / name).read_bytes())


async def test_walks_pages_with_a_resumable_cursor_and_identifies_itself() -> None:
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        return ok("page_0.json" if r.url.params["page"] == "0" else "page_1.json")

    client, slots, _ = make(handler, client_id="test-client")
    first = await client.fetch_page(CURSOR, deadline=Deadline.after(30))
    assert first.next_cursor == BdlCursor("TEST-VAR-1", TerritoryLevel.gmina, 2022, 1)
    assert first.next_cursor is not None
    second = await client.fetch_page(first.next_cursor, deadline=Deadline.after(30))
    assert second.next_cursor is None
    assert seen[0].url.params["unit-level"] == "6"
    assert seen[0].headers["x-clientid"] == "test-client"
    assert slots.hosts == ["bdl.stat.gov.pl"] * 2
    assert first.digest == hashlib.sha256((FIX / "page_0.json").read_bytes()).hexdigest()


async def test_local_quota_window_stops_before_the_request() -> None:
    calls = 0

    def handler(r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return ok("page_0.json")

    client, _, _ = make(handler, max_requests=1)
    await client.fetch_page(CURSOR, deadline=Deadline.after(30))
    with pytest.raises(BdlQuotaExhausted) as err:
        await client.fetch_page(CURSOR, deadline=Deadline.after(30))
    assert err.value.retry_after_s > 0
    assert calls == 1


async def test_429_waits_the_bounded_retry_after_then_succeeds() -> None:
    answers = [httpx.Response(429, headers={"retry-after": "7"}), ok("page_0.json")]
    client, _, sleeper = make(lambda r: answers.pop(0))
    result = await client.fetch_page(CURSOR, deadline=Deadline.after(60))
    assert result.next_cursor is not None
    assert sleeper.slept == [7.0]


async def test_persistent_429_reports_quota_exhausted() -> None:
    client, _, _ = make(lambda r: httpx.Response(429, headers={"retry-after": "1000"}))
    with pytest.raises(BdlQuotaExhausted) as err:
        await client.fetch_page(CURSOR, deadline=Deadline.after(600))
    assert err.value.retry_after_s == 60.0  # capped


async def test_server_errors_are_retried_a_bounded_number_of_times() -> None:
    calls = 0

    def handler(r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    client, _, _ = make(handler)
    with pytest.raises(BdlUnavailable):
        await client.fetch_page(CURSOR, deadline=Deadline.after(60))
    assert calls == 3


async def test_other_status_and_oversized_answers_fail_without_retry() -> None:
    client, _, _ = make(lambda r: httpx.Response(404))
    with pytest.raises(BdlUnavailable, match="404"):
        await client.fetch_page(CURSOR, deadline=Deadline.after(30))
    big = make(lambda r: httpx.Response(200, content=b"x" * (4 * 1024 * 1024 + 1)))[0]
    with pytest.raises(BdlUnavailable, match="too large"):
        await big.fetch_page(CURSOR, deadline=Deadline.after(30))


async def test_expired_deadline_never_calls_the_network() -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        raise AssertionError("must not be called")

    client, _, _ = make(handler)
    with pytest.raises(BdlUnavailable):
        await client.fetch_page(CURSOR, deadline=Deadline.after(0))


async def test_malformed_body_ends_the_walk_and_fails_validation() -> None:
    client, _, _ = make(lambda r: httpx.Response(200, content=b"not json"))
    result = await client.fetch_page(CURSOR, deadline=Deadline.after(30))
    assert result.next_cursor is None
    with pytest.raises(BdlValidationError):
        validate_page(result, metric(), year=2022, expected_units=UNITS)


def test_validator_maps_values_zero_suppression_and_attributes() -> None:
    p0 = validate_page(page("page_0.json"), metric(), year=2022, expected_units=frozenset(sorted(UNITS)[:2]))
    by_id = {o.territory_id: o for o in p0.observations}
    assert by_id["T000000000001"].status is ObservationStatus.measured
    assert by_id["T000000000001"].value == D(1200)
    assert by_id["T000000000002"].value == D(0)  # a genuine zero is measured
    assert all(o.source_digest == page("page_0.json").digest for o in p0.observations)

    p1 = validate_page(page("page_1.json"), metric(), year=2022, expected_units=frozenset(sorted(UNITS)[2:]))
    by_id = {o.territory_id: o for o in p1.observations}
    assert by_id["T000000000003"].status is ObservationStatus.suppressed
    assert by_id["T000000000004"].status is ObservationStatus.invalid_attribute
    assert all(o.value is None and o.reason for o in p1.observations)


def test_validator_reports_gaps_and_ignores_unrequested_units() -> None:
    result = validate_page(
        page("page_0.json"),
        metric(),
        year=2022,
        expected_units=frozenset({"T000000000001", "T000000000009"}),
    )
    by_id = {o.territory_id: o for o in result.observations}
    assert by_id["T000000000009"].status is ObservationStatus.missing
    assert result.unexpected_units == ("T000000000002",)
    assert "T000000000002" not in by_id


def test_validator_marks_a_year_gap_missing() -> None:
    result = validate_page(
        page("page_0.json"), metric(), year=2021, expected_units=frozenset({"T000000000001"})
    )
    assert result.observations[0].status is ObservationStatus.missing


def test_validator_rejects_unknown_variable_and_wrong_unit() -> None:
    with pytest.raises(BdlValidationError, match="variable"):
        validate_page(
            page("page_0.json"), metric(bdl_variable_id="TEST-VAR-2"), year=2022, expected_units=UNITS
        )
    with pytest.raises(BdlValidationError, match="unit"):
        validate_page(page("page_0.json"), metric(unit="zł"), year=2022, expected_units=UNITS)
    with pytest.raises(BdlValidationError, match="reviewed"):
        validate_page(page("page_0.json"), metric(bdl_variable_id=None), year=2022, expected_units=UNITS)


def test_validator_rejects_duplicates_and_out_of_range_values() -> None:
    raw = json.loads((FIX / "page_0.json").read_text())
    raw["results"].append(raw["results"][0])
    body = json.dumps(raw).encode()
    dup = BdlPage(body, hashlib.sha256(body).hexdigest(), None)
    with pytest.raises(BdlValidationError, match="duplicate"):
        validate_page(dup, metric(), year=2022, expected_units=UNITS)

    result = validate_page(
        page("page_0.json"), metric(max_value=D(100)), year=2022, expected_units=frozenset({"T000000000001"})
    )
    assert result.observations[0].status is ObservationStatus.invalid_attribute
