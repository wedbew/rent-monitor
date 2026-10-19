"""Risk-free rate: the stored latest Polish 10-year government bond yield, its freshness rule and its store
(RM-210, ENGINE-SPEC row 9 / N-12).

LEGAL[third-party-data]: the value is an ECB Data Portal statistic (IRS dataset, convergence-purposes long-
term
interest rate, Polish zloty, 10-year maturity). The ECB asks that the source is cited and the data is not
misrepresented; the reuse notice is recorded in docs/LIMITATIONS.md (RM-210).

Decision (RM-210): the ECB series is used because it is an official, public, machine-readable feed with a
stated
unit, a 10-year maturity and a documented reuse condition (citation). Its values are monthly, so the rule
below
allows one missed monthly publication before the stored value is refused.

GDPR: no personal data. Retention: one row per series, overwritten by newer observations; no history kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Final

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import RiskFreeRate as RiskFreeRow

SOURCE_ECB: Final = "ecb"
# ECB Data Portal key: dataflow IRS, Poland, long-term rate for convergence purposes, 10 years, PLN, monthly.
ECB_SERIES_KEY: Final = "IRS.M.PL.L.L40.CI.0000.PLN.N.Z"
SETTING_SOURCE: Final = "setting:RISK_FREE_RATE"

# Freshness: a monthly series is published with a lag of several weeks, so the newest value is at most roughly
# 75 days old in normal operation (lag plus up to one month). 120 days from the end of the observed month
# tolerates one missed monthly publication before the stored value stops being used (RM-210).
MAX_AGE_DAYS: Final = 120

# Plausibility of an annual yield as a fraction. Below 0.1 % or above 20 % is rejected as a parse or unit
# error,
# not stored. This is a sanity bound, not a market view.
RATE_MIN: Final = Decimal("0.001")
RATE_MAX: Final = Decimal("0.20")
RATE_QUANT: Final = Decimal("0.000001")


@dataclass(frozen=True)
class RiskFreeRate:
    """The rate the engine used and where it came from. `as_of` is the first day of the observed month for a
    stored value and None for the setting (which has no date)."""

    rate: Decimal
    source: str
    as_of: date | None


def percent_to_rate(percent: Decimal) -> Decimal:
    """ECB reports percent per annum (UNIT=PC, UNIT_MULT=0). 6.23 -> 0.0623, exact in Decimal."""
    return (percent / Decimal(100)).quantize(RATE_QUANT)


def parse_decimal(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("not a decimal") from exc
    if not value.is_finite():
        raise ValueError("not finite")
    return value


def is_plausible(rate: Decimal) -> bool:
    return RATE_MIN <= rate <= RATE_MAX


def month_end(period: date) -> date:
    next_month = (period.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


def is_fresh(observation_period: date, today: date) -> bool:
    """Fresh while no more than MAX_AGE_DAYS have passed since the end of the observed month. A future-dated
    observation is never fresh."""
    age = (today - month_end(observation_period)).days
    return 0 <= age <= MAX_AGE_DAYS


def utc_now() -> datetime:
    return datetime.now(UTC)


async def load_stored(session: AsyncSession, series_key: str = ECB_SERIES_KEY) -> RiskFreeRow | None:
    return await session.get(RiskFreeRow, series_key)


async def record_observation(
    session: AsyncSession,
    *,
    observation_period: date,
    rate: Decimal,
    series_key: str = ECB_SERIES_KEY,
    now: datetime | None = None,
) -> bool:
    """Store the observation if it is at least as new as the stored one. Idempotent: the same observation
    twice changes nothing; an older one never overwrites a newer one. Returns True when the row was
    written."""
    if not is_plausible(rate):
        raise ValueError("implausible risk-free rate")
    stamp = now or utc_now()
    row = {
        "series_key": series_key,
        "source": SOURCE_ECB,
        "observation_period": observation_period,
        "rate": rate,
        "fetched_at": stamp,
        "last_attempt_at": stamp,
        "last_failure_code": None,
        "last_failed_at": None,
    }
    stmt = insert(RiskFreeRow).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RiskFreeRow.series_key],
        set_={
            "observation_period": stmt.excluded.observation_period,
            "rate": stmt.excluded.rate,
            "fetched_at": stmt.excluded.fetched_at,
            "last_attempt_at": stmt.excluded.last_attempt_at,
            "last_failure_code": None,
            "last_failed_at": None,
        },
        where=(
            RiskFreeRow.observation_period.is_(None)
            | (stmt.excluded.observation_period >= RiskFreeRow.observation_period)
        ),
    ).returning(RiskFreeRow.series_key)
    written = await session.scalar(stmt)
    return written is not None


async def record_failure(
    session: AsyncSession,
    *,
    code: str,
    series_key: str = ECB_SERIES_KEY,
    now: datetime | None = None,
) -> None:
    """Keep the previous value and record that the refresh failed (RM-210). Never raises for a missing row."""
    stamp = now or utc_now()
    stmt = insert(RiskFreeRow).values(
        series_key=series_key,
        source=SOURCE_ECB,
        last_attempt_at=stamp,
        last_failure_code=code,
        last_failed_at=stamp,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[RiskFreeRow.series_key],
        set_={
            "last_attempt_at": stmt.excluded.last_attempt_at,
            "last_failure_code": stmt.excluded.last_failure_code,
            "last_failed_at": stmt.excluded.last_failed_at,
        },
    )
    await session.execute(stmt)
