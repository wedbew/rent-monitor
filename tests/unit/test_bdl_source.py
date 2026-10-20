"""BDL source client and validator (RM-386). Offline: httpx.MockTransport + hand-built fixtures.

Metric keys and the variable id `TESTV1` are TEST-ONLY; the real selection is unapproved (B-023).
"""

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from rm_contracts.location_context import (
    Direction,
    MetricDefinition,
    ObservationStatus,
    SelectionStatus,
    TerritoryLevel,
    TerritoryRef,
)
from rm_core.deadline import Deadline
from rm_worker.clients.bdl import (
    BdlClient,
    BdlCursor,
    BdlMetricBinding,
    BdlObservationValidator,
    BdlPage,
    BdlQuotaExhausted,
    BdlResponseInvalid,
    BdlUnavailable,
    BdlVariableMeta,
    GapError,
    QuotaGate,
    QuotaWindow,
    SlidingWindowQuota,
    UnexpectedDataError,
    UnknownVariableError,
    WrongUnitError,
)

FIX = Path(__file__).parent.parent / "fixtures" / "bdl"
G = TerritoryLevel.gmina


def fixture(name: str) -> str:
    return (FIX / name).read_text()


def defn(**kw: object) -> MetricDefinition:
    base: dict[str, object] = {
        "key": "test_population",
        "version": 1,
        "name_pl": "test",
        "unit": "osoba",
        "native_level": G,
        "published_levels": frozenset({G}),
        "direction": Direction.neutral,
        "selection": SelectionStatus.selected,
        "bdl_variable_id": "TESTV1",
        "min_value": Decimal(0),
    }
    return MetricDefinition.model_validate(base | kw)


def expected() -> dict[str, TerritoryRef]:
    return {
        t: TerritoryRef(territory_id=t, teryt="0201011", name=f"g{t}", level=G, parent_id="P1")
        for t in ("0000000001", "0000000002", "0000000003")
    }


def binding() -> BdlMetricBinding:
    return BdlMetricBinding(
        variable_id="TESTV1", definition=defn(), expected_unit="osoba", suppressed_attr_ids=frozenset({2})
    )


class NoWait:
    async def acquire(self, *, max_wait_s: float) -> None:
        return None


async def no_sleep(_: float) -> None:
    return None


def client(handler: object, *, quota: QuotaGate | None = None, api_key: str | None = None) -> BdlClient:
    transport = handler if isinstance(handler, httpx.MockTransport) else httpx.MockTransport(handler)  # type: ignore[arg-type]
    return BdlClient(
        http=httpx.AsyncClient(transport=transport), quota=quota or NoWait(), api_key=api_key, sleep=no_sleep
    )


CUR = BdlCursor(variable_id="TESTV1", unit_level=6, years=(2022, 2023))


def serve_pages(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/variables/TESTV1"):
            return httpx.Response(200, text=fixture("variable_meta.json"))
        page = request.url.params["page"]
        return httpx.Response(200, text=fixture(f"data_page{page}.json"))

    return httpx.MockTransport(handler)


async def collect(c: BdlClient) -> tuple[BdlVariableMeta, tuple[BdlPage, ...]]:
    dl = Deadline.after(30)
    meta = await c.variable_meta("TESTV1", deadline=dl)
    return meta, tuple([p async for p in c.pages(CUR, deadline=dl)])


# --- client ---------------------------------------------------------------------------------------------


async def test_pages_follow_cursor_and_send_expected_query() -> None:
    seen: list[httpx.Request] = []
    meta, pages = await collect(client(serve_pages(seen), api_key="k"))
    assert [p.cursor.page for p in pages] == [0, 1]
    assert pages[0].next_cursor == CUR.model_copy(update={"page": 1})
    assert pages[1].next_cursor is None
    q = seen[1].url.params
    assert q.get_list("year") == ["2022", "2023"]
    assert q["unit-level"] == "6"
    assert q["page"] == "0"
    assert seen[1].headers["x-clientid"] == "k"
    assert meta.unit == "osoba"


async def test_resume_from_stored_cursor_skips_finished_pages() -> None:
    seen: list[httpx.Request] = []
    c = client(serve_pages(seen))
    stored = CUR.model_copy(update={"page": 1})
    pages = [
        p
        async for p in c.pages(CUR.model_validate_json(stored.model_dump_json()), deadline=Deadline.after(5))
    ]
    assert [p.cursor.page for p in pages] == [1]
    assert len(seen) == 1


async def test_values_are_decimal_never_float() -> None:
    _, pages = await collect(client(serve_pages([])))
    assert pages[0].body.results[0].values[1].val == Decimal("1250.5")
    assert isinstance(pages[0].body.results[0].values[1].val, Decimal)


@pytest.mark.parametrize("bad", ["../x", "a/b", "", "x" * 17, "1;2"])
async def test_variable_id_is_path_safe(bad: str) -> None:
    with pytest.raises(ValueError, match="invalid"):
        await client(lambda r: httpx.Response(200)).variable_meta(bad, deadline=Deadline.after(1))


async def test_http_429_stops_with_retry_after_and_does_not_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "120"})

    with pytest.raises(BdlQuotaExhausted) as ei:
        await client(handler).fetch_page(CUR, deadline=Deadline.after(5))
    assert ei.value.retry_after_s == 120
    assert calls == 1


async def test_5xx_retried_once_then_unavailable() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    with pytest.raises(BdlUnavailable):
        await client(handler).fetch_page(CUR, deadline=Deadline.after(5))
    assert calls == 2


async def test_transient_error_then_success() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, text=fixture("data_page1.json"))

    page = await client(handler).fetch_page(CUR.model_copy(update={"page": 1}), deadline=Deadline.after(5))
    assert page.next_cursor is None


async def test_expired_deadline_makes_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be touched")

    with pytest.raises(BdlUnavailable):
        await client(handler).fetch_page(CUR, deadline=Deadline.after(0))


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"totalRecords":1}',
        # answer for a different variable
        '{"totalRecords":0,"page":0,"pageSize":2,"variableId":"OTHER","results":[]}',
        # answer for a different page
        '{"totalRecords":0,"page":5,"pageSize":2,"variableId":"TESTV1","results":[]}',
        # more rows than the page size
        '{"totalRecords":9,"page":0,"pageSize":1,"variableId":"TESTV1","results":'
        '[{"id":"1","values":[]},{"id":"2","values":[]}]}',
    ],
)
async def test_malformed_pages_are_rejected(text: str) -> None:
    with pytest.raises(BdlResponseInvalid):
        await client(lambda r: httpx.Response(200, text=text)).fetch_page(CUR, deadline=Deadline.after(5))


async def test_oversized_body_is_rejected() -> None:
    big = "x" * (4 * 1024 * 1024 + 10)
    with pytest.raises(BdlResponseInvalid):
        await client(lambda r: httpx.Response(200, text=big)).fetch_page(CUR, deadline=Deadline.after(5))


def test_cursor_rejects_unsafe_and_oversized_values() -> None:
    with pytest.raises(ValidationError):
        BdlCursor(variable_id="a/../b", unit_level=6, years=(2022,))
    with pytest.raises(ValidationError):
        BdlCursor(variable_id="TESTV1", unit_level=6, years=())
    with pytest.raises(ValidationError):
        BdlCursor.model_validate({"variable_id": "TESTV1", "unit_level": 6, "years": [2022], "x": 1})


# --- quota ----------------------------------------------------------------------------------------------


async def test_quota_waits_inside_budget_and_refuses_beyond_it() -> None:
    now = [0.0]
    slept: list[float] = []

    async def sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    q = SlidingWindowQuota(
        windows=(QuotaWindow(2, 10.0), QuotaWindow(100, 1000.0)), clock=lambda: now[0], sleep=sleep
    )
    await q.acquire(max_wait_s=0)
    await q.acquire(max_wait_s=0)
    with pytest.raises(BdlQuotaExhausted) as ei:
        await q.acquire(max_wait_s=5)
    assert ei.value.retry_after_s == pytest.approx(10.0)
    await q.acquire(max_wait_s=10)
    assert slept == [pytest.approx(10.0)]


def test_quota_windows_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        SlidingWindowQuota(windows=())
    with pytest.raises(ValueError, match="positive"):
        SlidingWindowQuota(windows=(QuotaWindow(0, 1.0),))


async def test_quota_exhaustion_blocks_the_request() -> None:
    class Closed:
        async def acquire(self, *, max_wait_s: float) -> None:
            raise BdlQuotaExhausted("closed", 60.0)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request without a quota slot")

    with pytest.raises(BdlQuotaExhausted):
        await client(handler, quota=Closed()).fetch_page(CUR, deadline=Deadline.after(5))


# --- validator ------------------------------------------------------------------------------------------


async def test_validator_turns_fixtures_into_observations_with_provenance() -> None:
    meta, pages = await collect(client(serve_pages([])))
    rep = BdlObservationValidator({"TESTV1": binding()}).validate(
        meta, pages, expected=expected(), years=(2022, 2023)
    )
    by = {(o.territory_id, o.year): o for o in rep.observations}
    assert len(rep.observations) == 6
    assert by["0000000001", 2023].value == Decimal("1250.5")
    assert by["0000000001", 2023].status is ObservationStatus.measured
    assert by["0000000002", 2022].value == Decimal(0)  # a genuine zero stays measured
    assert by["0000000002", 2023].status is ObservationStatus.suppressed
    assert by["0000000003", 2023].status is ObservationStatus.missing
    assert {(o.territory_id, o.year) for o in rep.gaps} == {("0000000002", 2023), ("0000000003", 2023)}
    assert all(len(o.source_digest) == 64 for o in rep.observations)
    assert all(o.metric_key == "test_population" and o.metric_version == 1 for o in rep.observations)


async def test_digest_is_stable_and_value_sensitive() -> None:
    meta, pages = await collect(client(serve_pages([])))
    v = BdlObservationValidator({"TESTV1": binding()})
    a = v.validate(meta, pages, expected=expected(), years=(2022, 2023)).observations
    b = v.validate(meta, pages, expected=expected(), years=(2022, 2023)).observations
    assert a == b
    assert a[0].source_digest != a[1].source_digest


async def test_unknown_variable_and_wrong_unit_are_rejected() -> None:
    meta, pages = await collect(client(serve_pages([])))
    with pytest.raises(UnknownVariableError):
        BdlObservationValidator({}).validate(meta, pages, expected=expected(), years=(2022,))
    wrong = BdlVariableMeta.model_validate({"id": "TESTV1", "measureUnitName": "tys. osób"})
    with pytest.raises(WrongUnitError):
        BdlObservationValidator({"TESTV1": binding()}).validate(
            wrong, pages, expected=expected(), years=(2022,)
        )


async def test_strict_mode_rejects_gaps() -> None:
    meta, pages = await collect(client(serve_pages([])))
    with pytest.raises(GapError):
        BdlObservationValidator({"TESTV1": binding()}).validate(
            meta, pages, expected=expected(), years=(2022, 2023), strict_gaps=True
        )


async def test_foreign_year_and_territory_are_rejected() -> None:
    meta, pages = await collect(client(serve_pages([])))
    v = BdlObservationValidator({"TESTV1": binding()})
    with pytest.raises(UnexpectedDataError, match="year"):
        v.validate(meta, pages, expected=expected(), years=(2022,))
    partial = {k: t for k, t in expected().items() if k != "0000000003"}
    with pytest.raises(UnexpectedDataError, match="territory"):
        v.validate(meta, pages, expected=partial, years=(2022, 2023))


async def test_conflicting_duplicates_rejected_identical_tolerated() -> None:
    meta, pages = await collect(client(serve_pages([])))
    v = BdlObservationValidator({"TESTV1": binding()})
    v.validate(meta, (pages[0], pages[0], pages[1]), expected=expected(), years=(2022, 2023))
    dup = json.loads(fixture("data_page1.json"))
    dup["results"][0]["values"][0]["val"] = 901.0
    other = await client(lambda r: httpx.Response(200, text=json.dumps(dup))).fetch_page(
        CUR.model_copy(update={"page": 1}), deadline=Deadline.after(5)
    )
    with pytest.raises(UnexpectedDataError, match="duplicate"):
        v.validate(meta, (pages[0], pages[1], other), expected=expected(), years=(2022, 2023))


async def test_bad_attribute_and_out_of_bounds_values_are_not_measured() -> None:
    body = {
        "totalRecords": 1, "page": 0, "pageSize": 5, "variableId": "TESTV1",
        "results": [{"id": "0000000001", "values": [
            {"year": "2022", "val": -5, "attrId": 1}, {"year": "2023", "val": 7, "attrId": 9}]}],
    }  # fmt: skip
    page = await client(lambda r: httpx.Response(200, text=json.dumps(body))).fetch_page(
        CUR, deadline=Deadline.after(5)
    )
    meta = BdlVariableMeta.model_validate({"id": "TESTV1", "measureUnitName": "osoba"})
    one = {"0000000001": expected()["0000000001"]}
    rep = BdlObservationValidator({"TESTV1": binding()}).validate(
        meta, (page,), expected=one, years=(2022, 2023)
    )
    assert [o.status for o in rep.observations] == [ObservationStatus.invalid_attribute] * 2
    assert all(o.value is None and o.reason for o in rep.observations)


def test_binding_refuses_unselected_or_mismatched_metrics() -> None:
    with pytest.raises(ValueError, match="selected"):
        BdlMetricBinding("TESTV1", defn(selection=SelectionStatus.deferred), "osoba")
    with pytest.raises(ValueError, match="id"):
        BdlMetricBinding("OTHER", defn(), "osoba")
    with pytest.raises(ValueError, match="unit"):
        BdlMetricBinding("TESTV1", defn(), "tys.")


async def test_territory_at_unpublished_level_is_rejected() -> None:
    meta, pages = await collect(client(serve_pages([])))
    powiat = {
        "0000000001": TerritoryRef(
            territory_id="0000000001", teryt="0201", name="p", level=TerritoryLevel.powiat, parent_id="W"
        )
    }
    with pytest.raises(UnexpectedDataError, match="published"):
        BdlObservationValidator({"TESTV1": binding()}).validate(
            meta, pages, expected=powiat, years=(2022, 2023)
        )


@pytest.mark.parametrize(
    ("header", "seconds"),
    [
        ("1 sek", 1.0),
        ("2", 2.0),
        ("30 s", 30.0),
        ("0", 0.0),
        (None, 900.0),
        ("tomorrow", 900.0),
        ("999999", 86_400.0),
    ],
)
def test_retry_after_understands_the_services_own_words(header: str | None, seconds: float) -> None:
    from rm_worker.clients.bdl import _retry_after  # noqa: PLC0415

    assert _retry_after(header) == seconds


def test_quota_windows_cap_the_burst_the_service_refuses() -> None:
    from rm_worker.clients.bdl_quota import quota_windows  # noqa: PLC0415

    per_second, per_minute = quota_windows(5, 60)
    assert (per_second.limit, per_second.seconds) == (5, 1.0)  # the service answers 429 above 10 per second
    assert (per_minute.limit, per_minute.seconds) == (60, 60.0)
