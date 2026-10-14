"""The pack catalog, the Paddle client and disabled mode (docs/PADDLE-INTEGRATION.md §1-§3, slice 1)."""

import json
from decimal import Decimal

import httpx
import pytest
from paddle_fake import FakePaddle
from rm_core.billing_catalog import PACK_REPORTS, CatalogError, load_catalog
from rm_core.paddle import (
    CatalogMismatchError,
    HttpPaddleClient,
    PaddleAmbiguousError,
    PaddleError,
    build_paddle_client,
    verify_catalog,
)
from rm_core.settings import Settings

APPROVED = (
    "reports_1=1000,reports_5=4000,reports_10=7000"  # test values only: the owner has not approved prices
)


def settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "test",
        "database_url": "",
        "billing_provider": "paddle",
        "paddle_api_key": "pdl_sdbx_apikey_test",
        "paddle_price_reports_1": "pri_one",
        "paddle_price_reports_5": "pri_five",
        "paddle_price_reports_10": "pri_ten",
        "paddle_approved_amounts": APPROVED,
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


# ------------------------------------------------------------------------------ catalog
def test_paddle_pack_catalog() -> None:
    catalog = load_catalog(settings())
    assert catalog is not None
    assert [(p.code, p.reports) for p in catalog.packs] == [
        ("reports_1", 1),
        ("reports_5", 5),
        ("reports_10", 10),
    ]
    assert dict(PACK_REPORTS) == {"reports_1": 1, "reports_5": 5, "reports_10": 10}
    assert [p.gross_pln for p in catalog.packs] == [
        Decimal(10),
        Decimal(40),
        Decimal(70),
    ]  # from the snapshot
    assert catalog.by_price_id("pri_five") is not None
    assert catalog.by_price_id("pri_five").reports == 5  # type: ignore[union-attr]
    assert catalog.by_price_id("pri_unknown") is None
    assert catalog.environment == "sandbox"


def test_billing_is_off_by_default_and_needs_no_credentials() -> None:
    plain = Settings(app_env="test", database_url="")
    assert plain.billing_provider == "disabled"
    assert load_catalog(plain) is None
    assert build_paddle_client(plain) is None
    assert plain.paddle_approved_amounts == ""  # there is no default price anywhere


@pytest.mark.parametrize(
    "overrides",
    [
        {"paddle_approved_amounts": ""},  # no owner-approved prices
        {"paddle_approved_amounts": "reports_1=1000,reports_5=4000"},  # one pack missing
        {"paddle_approved_amounts": APPROVED + ",reports_20=9000"},  # an unknown pack
        {"paddle_approved_amounts": "reports_1=1000,reports_1=1100,reports_5=4000,reports_10=7000"},
        {"paddle_approved_amounts": "reports_1=0,reports_5=4000,reports_10=7000"},
        {"paddle_approved_amounts": "reports_1=10.00,reports_5=4000,reports_10=7000"},
        {"paddle_price_reports_5": ""},
        {"paddle_price_reports_5": "price_five"},  # not a Paddle price id
        {"paddle_price_reports_5": "pri_one"},  # two packs share a price
    ],
)
def test_an_incomplete_or_inconsistent_catalog_is_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(CatalogError):
        load_catalog(settings(**overrides))


def test_mixed_environments_are_refused() -> None:
    with pytest.raises(PaddleError, match="mixed"):
        build_paddle_client(settings(paddle_environment="live", paddle_api_key="pdl_sdbx_apikey_test"))
    with pytest.raises(PaddleError, match="mixed"):
        build_paddle_client(settings(paddle_environment="sandbox", paddle_api_key="pdl_live_apikey_x"))
    with pytest.raises(PaddleError, match="not set"):
        build_paddle_client(settings(paddle_api_key=""))
    assert build_paddle_client(settings()) is not None


async def test_verify_catalog_accepts_matching_one_time_pln_prices_and_rejects_the_rest() -> None:
    packs = [("reports_1", "pri_one", 1000), ("reports_5", "pri_five", 4000), ("reports_10", "pri_ten", 7000)]
    fake = FakePaddle()
    fake.add_price("pri_one", amount_minor=1000)
    fake.add_price("pri_five", amount_minor=4000)
    fake.add_price("pri_ten", amount_minor=7000)
    await verify_catalog(fake, packs)

    for bad in (
        {"amount_minor": 3900},  # drifted from the approved snapshot
        {"amount_minor": 4000, "currency": "EUR"},
        {"amount_minor": 4000, "one_time": False},  # recurring
    ):
        broken = FakePaddle()
        broken.add_price("pri_one", amount_minor=1000)
        broken.add_price("pri_five", **bad)  # type: ignore[arg-type]
        broken.add_price("pri_ten", amount_minor=7000)
        with pytest.raises(CatalogMismatchError):
            await verify_catalog(broken, packs)


# ------------------------------------------------------------------------------ client
def client_with(handler: httpx.MockTransport, sleeps: list[float] | None = None) -> HttpPaddleClient:
    async def no_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return HttpPaddleClient(
        environment="sandbox",
        api_key="pdl_sdbx_apikey_secret",
        http=httpx.AsyncClient(transport=handler),
        sleep=no_sleep,
    )


TXN = {
    "data": {
        "id": "txn_1",
        "status": "completed",
        "currency_code": "PLN",
        "customer_id": "ctm_1",
        "custom_data": {"purchase": "p1"},
        "items": [{"price": {"id": "pri_one", "product_id": "pro_1"}, "quantity": 1}],
        "details": {"totals": {"total": "1000"}},
    }
}


async def test_the_client_sends_bearer_auth_and_version_and_parses_money_as_minor_units() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=TXN)

    txn = await client_with(httpx.MockTransport(handler)).get_transaction("txn_1")
    assert (txn.id, txn.status, txn.currency_code, txn.total_minor) == ("txn_1", "completed", "PLN", 1000)
    assert [(i.price_id, i.quantity) for i in txn.items] == [("pri_one", 1)]
    assert seen[0].url.host == "sandbox-api.paddle.com"
    assert seen[0].headers["authorization"] == "Bearer pdl_sdbx_apikey_secret"
    assert seen[0].headers["paddle-version"] == "1"


async def test_reads_retry_with_jitter_on_429_and_5xx_and_honour_retry_after() -> None:
    replies = iter(
        [
            httpx.Response(429, headers={"retry-after": "2"}),
            httpx.Response(503),
            httpx.Response(200, json=TXN),
        ]
    )
    sleeps: list[float] = []
    client = client_with(httpx.MockTransport(lambda r: next(replies)), sleeps)
    assert (await client.get_transaction("txn_1")).id == "txn_1"
    assert len(sleeps) == 2
    assert sleeps[0] >= 2.0  # Retry-After wins over the backoff
    assert 0 < sleeps[1] <= 5.0


async def test_reads_give_up_after_a_bounded_number_of_attempts() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(PaddleError):
        await client_with(httpx.MockTransport(handler)).get_transaction("txn_1")
    assert len(calls) == 3


async def test_a_timed_out_creation_is_never_retried_and_is_reported_as_ambiguous() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    client = client_with(httpx.MockTransport(handler))
    with pytest.raises(PaddleAmbiguousError):
        await client.create_transaction(price_id="pri_one", custom_data={"purchase": "p1"})
    assert len(calls) == 1  # no blind second payment
    with pytest.raises(PaddleAmbiguousError):
        await client.create_full_refund(transaction_id="txn_1", reason="support")
    assert len(calls) == 2


async def test_creation_sends_exactly_one_item_of_quantity_one_with_only_our_reference() -> None:
    bodies: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(201, json=TXN)

    await client_with(httpx.MockTransport(handler)).create_transaction(
        price_id="pri_one", custom_data={"purchase": "p1"}
    )
    assert bodies == [{"items": [{"price_id": "pri_one", "quantity": 1}], "custom_data": {"purchase": "p1"}}]


@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(404),
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json={"x": 1}),
        httpx.Response(200, json={"data": {"id": 5}}),
    ],
)
async def test_client_errors_and_malformed_replies_are_definite_failures(reply: httpx.Response) -> None:
    with pytest.raises(PaddleError):
        await client_with(httpx.MockTransport(lambda r: reply)).get_transaction("txn_1")


async def test_prices_and_adjustments_parse_into_typed_results() -> None:
    price = {
        "data": {
            "id": "pri_one",
            "product_id": "pro_1",
            "status": "active",
            "billing_cycle": None,
            "trial_period": None,
            "unit_price": {"amount": "1000", "currency_code": "PLN"},
            "quantity": {"minimum": 1, "maximum": 1},
        }
    }
    adjustments = {
        "data": [
            {
                "id": "adj_1",
                "transaction_id": "txn_1",
                "action": "refund",
                "type": "full",
                "status": "approved",
                "currency_code": "PLN",
                "totals": {"total": "1000"},
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=price if "/prices/" in request.url.path else adjustments)

    client = client_with(httpx.MockTransport(handler))
    p = await client.get_price("pri_one")
    assert (p.amount_minor, p.currency_code, p.one_time, p.quantity_min, p.quantity_max) == (
        1000,
        "PLN",
        True,
        1,
        1,
    )
    adj = (await client.list_adjustments("txn_1"))[0]
    assert (adj.id, adj.status, adj.total_minor) == ("adj_1", "approved", 1000)
