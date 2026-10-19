"""ECB Data Portal client for the risk-free rate (RM-210, ENGINE-SPEC N-12).

LEGAL[third-party-data]: reads one public ECB statistic (IRS, Poland, long-term rate for convergence purposes,
10 years, PLN, monthly). The ECB requires that the source is cited when the data is reproduced; the citation
is
kept with the stored value (`rm_core.risk_free`). Reuse terms: ECB disclaimer page, recorded in
docs/LIMITATIONS.md.
GDPR[processor]: no personal data is sent; the request carries only the series key.

Injectable: callers pass an `httpx.AsyncClient`; tests pass one with a `MockTransport`. The total call is
bounded
by `TOTAL_TIMEOUT_S` on top of the per-request connect/read timeouts. Responses are parsed strictly: exactly
one
observation of the expected series, percent unit, normal status, plausible value. Anything else is rejected.
"""

from __future__ import annotations

import asyncio
import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

import httpx
from rm_core.risk_free import ECB_SERIES_KEY, is_plausible, parse_decimal, percent_to_rate

ECB_BASE_URL: Final = "https://data-api.ecb.europa.eu/service/data"
REQUEST_TIMEOUT: Final = httpx.Timeout(10.0, connect=5.0)
TOTAL_TIMEOUT_S: Final = 20.0
MAX_RESPONSE_BYTES: Final = 64 * 1024
_PERIOD = re.compile(r"^(\d{4})-(\d{2})$")


class MacroError(Exception):
    """Base class for every failure of this module."""


class MacroSourceUnavailable(MacroError):
    """The source could not be read now (network, timeout, 429, 5xx). The previous value stays in use."""


class MacroResponseInvalid(MacroError):
    """The answer is not the documented shape, series or unit. Never partially accepted."""


class MacroValueRejected(MacroError):
    """A parsed value outside the plausible range."""


@dataclass(frozen=True)
class RateObservation:
    series_key: str
    period: date  # first day of the observed month
    rate: Decimal  # annual yield as a fraction, e.g. 0.0623


def parse_latest_csv(text: str, series_key: str = ECB_SERIES_KEY) -> RateObservation:
    """Parse an SDMX-CSV answer for a series requested with lastNObservations=1."""
    reader = csv.DictReader(io.StringIO(text))
    required = {"KEY", "FREQ", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS", "UNIT", "UNIT_MULT"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise MacroResponseInvalid("answer is not the expected SDMX-CSV")
    rows = list(reader)
    if len(rows) != 1:
        raise MacroResponseInvalid(f"expected one observation, got {len(rows)}")
    row = rows[0]
    if row["KEY"] != f"IRS.{series_key}" and row["KEY"] != series_key:
        raise MacroResponseInvalid("answer is for a different series")
    if row["FREQ"] != "M":
        raise MacroResponseInvalid("series is not monthly")
    if row["UNIT"] != "PC" or row["UNIT_MULT"] != "0":
        raise MacroResponseInvalid("unexpected unit; expected percent per annum")
    if row["OBS_STATUS"] != "A":
        raise MacroResponseInvalid("observation is not a normal value")
    match = _PERIOD.match(row["TIME_PERIOD"] or "")
    if match is None:
        raise MacroResponseInvalid("period is not YYYY-MM")
    try:
        period = date(int(match.group(1)), int(match.group(2)), 1)
        percent = parse_decimal(row["OBS_VALUE"] or "")
    except (ValueError, TypeError) as exc:
        raise MacroResponseInvalid("period or value does not parse") from exc
    rate = percent_to_rate(percent)
    if not is_plausible(rate):
        raise MacroValueRejected(f"risk-free rate {rate} is outside the plausible range")
    return RateObservation(series_key=series_key, period=period, rate=rate)


class EcbRateClient:
    """Reads the latest value of one ECB series. Construct once per process with a shared
    `httpx.AsyncClient`."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str = ECB_BASE_URL,
        series_key: str = ECB_SERIES_KEY,
        total_timeout_s: float = TOTAL_TIMEOUT_S,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._series_key = series_key
        self._total_timeout_s = total_timeout_s

    async def latest(self) -> RateObservation:
        try:
            return await asyncio.wait_for(self._fetch(), timeout=self._total_timeout_s)
        except TimeoutError as exc:
            raise MacroSourceUnavailable("ECB request exceeded its total deadline") from exc

    async def _fetch(self) -> RateObservation:
        url = f"{self._base_url}/IRS/{self._series_key}"
        try:
            response = await self._http.get(
                url,
                params={"format": "csvdata", "lastNObservations": "1"},
                headers={"Accept": "text/csv"},
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise MacroSourceUnavailable(f"ECB request failed: {type(exc).__name__}") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise MacroSourceUnavailable(f"ECB answered HTTP {response.status_code}")
        if response.status_code != 200:
            raise MacroResponseInvalid(f"ECB answered HTTP {response.status_code}")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise MacroResponseInvalid("ECB answer is larger than the cap")
        return parse_latest_csv(response.text, self._series_key)
