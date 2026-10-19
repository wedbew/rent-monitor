"""ECB risk-free client and parser, offline (RM-210). No test reaches the network: every call goes through an
`httpx.MockTransport`. The CSV shape follows the ECB SDMX-CSV answer for the series (captured 2026-10-19)."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

import httpx
import pytest
from macro_csv import csv_of, row
from rm_core.risk_free import ECB_SERIES_KEY, is_fresh, is_plausible, month_end, percent_to_rate
from rm_worker.clients.macro import (
    EcbRateClient,
    MacroResponseInvalid,
    MacroSourceUnavailable,
    MacroValueRejected,
    parse_latest_csv,
)


def client_with(handler: httpx.MockTransport | object, *, total_timeout_s: float = 5.0) -> EcbRateClient:
    http = httpx.AsyncClient(transport=handler)  # type: ignore[arg-type]
    return EcbRateClient(http, base_url="https://ecb.test/service/data", total_timeout_s=total_timeout_s)


def respond(status: int = 200, body: str = "") -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body, headers={"Content-Type": "text/csv"})

    return httpx.MockTransport(handle)


# --- percent to rate and the plausibility bound -----------------------------------------------------------


def test_percent_is_converted_exactly_to_a_fraction() -> None:
    assert percent_to_rate(Decimal("6.23")) == Decimal("0.062300")
    assert percent_to_rate(Decimal("5.5")) == Decimal("0.055000")


@pytest.mark.parametrize(
    ("rate", "ok"),
    [(Decimal("0.0009"), False), (Decimal("0.001"), True), (Decimal("0.20"), True), (Decimal("0.21"), False)],
)
def test_plausible_range_is_a_sanity_bound(rate: Decimal, ok: bool) -> None:
    assert is_plausible(rate) is ok


# --- strict parsing ---------------------------------------------------------------------------------------


def test_parses_the_latest_observation() -> None:
    obs = parse_latest_csv(csv_of(row()))
    assert obs.series_key == ECB_SERIES_KEY
    assert obs.period == date(2026, 9, 1)
    assert obs.rate == Decimal("0.062300")


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("<html>maintenance</html>", MacroResponseInvalid),  # not the CSV at all
        (csv_of(), MacroResponseInvalid),  # no observation
        (csv_of(row(), row(period="2026-08")), MacroResponseInvalid),  # more than one observation
        (csv_of(row(key="IRS.M.PL.L.L40.CI.0000.EUR.N.Z")), MacroResponseInvalid),  # wrong series
        (csv_of(row(freq="Q")), MacroResponseInvalid),  # not monthly
        (csv_of(row(unit="USD")), MacroResponseInvalid),  # wrong unit
        (csv_of(row(mult="6")), MacroResponseInvalid),  # wrong multiplier
        (csv_of(row(status="M")), MacroResponseInvalid),  # missing value, not a number
        (csv_of(row(period="2026-9")), MacroResponseInvalid),  # malformed period
        (csv_of(row(value="n/a")), MacroResponseInvalid),  # value does not parse
        (csv_of(row(value="NaN")), MacroResponseInvalid),  # not finite
        (csv_of(row(value="25.0")), MacroValueRejected),  # implausible: 25 % a year
        (csv_of(row(value="0.05")), MacroValueRejected),  # implausible: a fraction written as percent
    ],
)
def test_malformed_or_implausible_answers_are_rejected(text: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        parse_latest_csv(text)


# --- the injectable client --------------------------------------------------------------------------------


async def test_client_returns_the_observation_and_sends_explicit_query() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=csv_of(row()))

    obs = await client_with(httpx.MockTransport(handle)).latest()
    assert obs.rate == Decimal("0.062300")
    assert seen[0].url.path == f"/service/data/IRS/{ECB_SERIES_KEY}"
    assert seen[0].url.params["lastNObservations"] == "1"
    assert seen[0].url.params["format"] == "csvdata"


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_throttling_and_server_errors_are_unavailable(status: int) -> None:
    with pytest.raises(MacroSourceUnavailable):
        await client_with(respond(status)).latest()


async def test_client_error_status_is_an_invalid_answer() -> None:
    with pytest.raises(MacroResponseInvalid):
        await client_with(respond(404, "not found")).latest()


async def test_transport_failure_is_unavailable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connect timed out", request=request)

    with pytest.raises(MacroSourceUnavailable):
        await client_with(httpx.MockTransport(handle)).latest()


async def test_a_stalled_answer_hits_the_total_deadline() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return httpx.Response(200, text=csv_of(row()))

    with pytest.raises(MacroSourceUnavailable):
        await client_with(httpx.MockTransport(handle), total_timeout_s=0.05).latest()


async def test_an_oversized_answer_is_refused() -> None:
    big = csv_of(row()) + ("x" * (65 * 1024))
    with pytest.raises(MacroResponseInvalid):
        await client_with(respond(200, big)).latest()


# --- freshness --------------------------------------------------------------------------------------------


def test_month_end_handles_leap_february_and_december() -> None:
    assert month_end(date(2028, 2, 1)) == date(2028, 2, 29)
    assert month_end(date(2026, 2, 1)) == date(2026, 2, 28)
    assert month_end(date(2026, 12, 1)) == date(2026, 12, 31)


def test_freshness_window_is_120_days_after_the_observed_month() -> None:
    period = date(2026, 9, 1)  # month end 2026-09-30
    assert is_fresh(period, date(2026, 9, 30))
    assert is_fresh(period, date(2027, 1, 28))  # exactly 120 days after the month end
    assert not is_fresh(period, date(2027, 1, 29))  # 121 days
    assert not is_fresh(period, date(2026, 9, 29))  # a future-dated observation is never fresh
