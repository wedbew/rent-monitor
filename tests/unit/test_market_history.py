"""Pure parts of the daily asking-rent summaries (RM-395): cohort rules, series separation, freshness.

LEGAL[third-party-data]: hand-built asking figures, no real listings (RM-395).
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from deal_analyzer.market_stats import summarise_asking
from pydantic import ValidationError
from rm_contracts.market import DataStatus
from rm_core.market_history import (
    ALL,
    AskingRentObservation,
    OfferFacts,
    build_rows,
    cohort_keys,
    freshness,
)
from rm_core.settings import Settings

DAY = date(2026, 10, 19)
AS_OF = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)


def offer(
    i: int,
    *,
    rent: str | None = "2000",
    area: str | None = "40",
    rooms: int | None = 2,
    published: datetime | None = None,
    seen: datetime = AS_OF - timedelta(hours=3),
    days_to_expiry: int | None = None,
) -> OfferFacts:
    anchor = published or seen
    expires = (
        anchor + timedelta(days=90) if days_to_expiry is None else AS_OF + timedelta(days=days_to_expiry)
    )
    return OfferFacts(
        i,
        Decimal(rent) if rent else None,
        Decimal(area) if area else None,
        rooms,
        published,
        seen,
        "publication" if published else "first_seen",
        expires,
    )


def rows_of(offers: list[OfferFacts]) -> dict[tuple[str, str], object]:
    rows = build_rows("loc-0", DAY, offers, as_of=AS_OF, summarise=summarise_asking)
    return {(r.series, r.cohort_key): r for r in rows}


def test_summarise_asking_is_exact_decimal() -> None:
    s = summarise_asking([Decimal(v) for v in ("10", "20", "30", "40")])
    assert s is not None
    assert (s.count, s.median, s.p25, s.p75) == (4, Decimal("25.00"), Decimal("17.50"), Decimal("32.50"))
    assert summarise_asking([]) is None


def test_cohort_keys_cover_rooms_and_size_bands() -> None:
    assert cohort_keys(offer(1, rooms=1, area="29.99")) == [ALL, "rooms_1", "size_lt30"]
    assert cohort_keys(offer(1, rooms=5, area="80")) == [ALL, "rooms_4plus", "size_80plus"]
    assert cohort_keys(offer(1, rooms=None, area=None)) == [ALL]


def test_zero_day_still_publishes_an_all_row_per_series() -> None:
    rows = rows_of([])
    assert set(rows) == {("additions", ALL), ("cohort", ALL)}
    r = rows[("additions", ALL)]
    assert (r.observed_count, r.priced_count, r.sufficient, r.median_ppm2) == (0, 0, False, None)  # type: ignore[attr-defined]


def test_additions_and_cohort_are_separate_series() -> None:
    today = offer(1)  # first seen today, no publication time: source date is today
    old = offer(2, published=AS_OF - timedelta(days=30), seen=AS_OF - timedelta(hours=2))  # late discovery
    rows = rows_of([today, old])
    add, coh = rows[("additions", ALL)], rows[("cohort", ALL)]
    assert add.observed_count == 1  # type: ignore[attr-defined]
    assert add.first_observed_count == 2  # type: ignore[attr-defined]  # both were first seen today
    assert coh.observed_count == 2  # type: ignore[attr-defined]
    assert coh.first_observed_count is None  # type: ignore[attr-defined]


def test_cohort_excludes_expired_offers_at_the_exact_boundary() -> None:
    at_boundary = offer(1, seen=AS_OF - timedelta(days=90), days_to_expiry=0)
    alive = offer(2, days_to_expiry=1)
    coh = rows_of([at_boundary, alive])[("cohort", ALL)]
    assert coh.observed_count == 1  # type: ignore[attr-defined]


def test_offers_seen_after_as_of_are_unknown() -> None:
    later = offer(1, seen=AS_OF + timedelta(minutes=1))
    assert rows_of([later])[("cohort", ALL)].observed_count == 0  # type: ignore[attr-defined]


def test_unpriced_offers_count_as_observed_but_not_in_statistics() -> None:
    rows = rows_of([offer(1, rent=None), offer(2, area=None), offer(3)])
    coh = rows[("cohort", ALL)]
    assert (coh.observed_count, coh.priced_count) == (3, 1)  # type: ignore[attr-defined]
    assert coh.median_ppm2 == Decimal("50.00")  # type: ignore[attr-defined]


def test_sufficiency_needs_ten_priced_offers() -> None:
    nine = rows_of([offer(i) for i in range(9)])[("cohort", ALL)]
    ten = rows_of([offer(i) for i in range(10)])[("cohort", ALL)]
    assert (nine.sufficient, ten.sufficient) == (False, True)  # type: ignore[attr-defined]


def test_digest_is_stable_and_series_specific() -> None:
    a = rows_of([offer(1), offer(2)])
    b = rows_of([offer(2), offer(1)])
    assert a[("cohort", ALL)].input_digest == b[("cohort", ALL)].input_digest  # type: ignore[attr-defined]
    assert a[("cohort", ALL)].input_digest != a[("additions", ALL)].input_digest  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("hours", "gap", "expected"),
    [
        (1, False, DataStatus.fresh),
        (36, False, DataStatus.fresh),
        (37, False, DataStatus.delayed),
        (72, False, DataStatus.delayed),
        (73, False, DataStatus.stale),
        (1, True, DataStatus.stale),
    ],
)
def test_freshness_thresholds(hours: int, gap: bool, expected: DataStatus) -> None:
    refresh = AS_OF - timedelta(hours=hours)
    status = freshness(bootstrapped=True, refresh_at=refresh, gap_since=refresh if gap else None, now=AS_OF)
    assert status is expected


def test_freshness_unavailable_without_bootstrap() -> None:
    assert (
        freshness(bootstrapped=False, refresh_at=AS_OF, gap_since=None, now=AS_OF) is DataStatus.unavailable
    )
    assert freshness(bootstrapped=True, refresh_at=None, gap_since=None, now=AS_OF) is DataStatus.unavailable


def test_observation_type_cannot_carry_a_deed_basis() -> None:
    fields = {
        "location_id": "x",
        "summary_date": DAY,
        "series": "cohort",
        "cohort_key": ALL,
        "calc_version": 1,
        "as_of": AS_OF,
        "observed_count": 0,
        "priced_count": 0,
        "first_observed_count": None,
        "median_rent_pln": None,
        "median_ppm2": None,
        "p25_ppm2": None,
        "p75_ppm2": None,
        "sufficient": False,
        "backfilled": False,
    }
    assert AskingRentObservation(**fields).price_basis == "asking"
    with pytest.raises(ValidationError):
        AskingRentObservation(**fields, price_basis="deed")  # type: ignore[arg-type]


def test_market_settings_defaults_and_validation() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.otodom_market_import_enabled is True
    assert (s.otodom_market_fresh_hours, s.otodom_market_stale_hours) == (36, 72)
    assert s.otodom_market_archive_days == 90
    for bad in (
        {"otodom_market_archive_days": 30},
        {"otodom_market_stale_hours": 36},
        {"otodom_market_night_window_end_utc": "5am"},
        {"otodom_market_nightly_cron": "0 1 *"},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **bad)  # type: ignore[call-arg, arg-type]
