"""N-04: rent estimate from comparable asking rents (docs/ENGINE-SPEC.md row 5)."""

import random
from decimal import Decimal as D

import pytest
from deal_analyzer import Confidence, RentComparable, estimate_rent
from deal_analyzer.analysis import analyse_listing
from hypothesis import given, settings
from hypothesis import strategies as st

AREA = D(50)


def comps(ppm2: list[int], area: int = 50) -> list[RentComparable]:
    return [RentComparable(monthly_rent_pln=D(p * area), area_m2=D(area)) for p in ppm2]


def test_the_median_ppm2_is_scaled_to_the_flat() -> None:
    est = estimate_rent(AREA, comps([50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70]))
    assert not est.refused
    assert est.ppm2_median == D("60.00")
    assert est.monthly_rent_pln == D("3000.00")  # 60 PLN/m2 x 50 m2
    assert est.low_monthly_pln == D("2750.00")
    assert est.high_monthly_pln == D("3250.00")
    assert est.basis == "asking"


def test_confidence_follows_the_market_depth() -> None:
    assert estimate_rent(AREA, comps([60] * 12)).confidence is Confidence.HIGH
    thin = estimate_rent(AREA, comps([60, 62, 64, 66, 68]))
    assert thin.confidence is Confidence.MEDIUM
    assert "rent_thin_market" in thin.warnings


@pytest.mark.parametrize("n", [0, 1, 2])
def test_fewer_than_three_comparables_refuse_a_number(n: int) -> None:
    est = estimate_rent(AREA, comps([60] * n))
    assert est.refused
    assert est.monthly_rent_pln is None
    assert est.confidence is Confidence.LOW
    assert "rent_refused_too_few_comparables" in est.warnings
    rent_input = est.to_input()
    assert rent_input.monthly_rent_pln == 0
    assert rent_input.comparables == n


def test_exactly_three_comparables_are_enough_but_thin() -> None:
    est = estimate_rent(AREA, comps([58, 60, 62]))
    assert not est.refused
    assert est.confidence is Confidence.MEDIUM


def test_outliers_are_trimmed_in_larger_samples() -> None:
    values = [58, 59, 60, 60, 61, 62, 60, 59, 61, 500]  # one absurd listing
    est = estimate_rent(AREA, comps(values))
    assert est.comparables_used == 9
    assert est.ppm2_median == D("60.00")


def test_small_samples_are_not_trimmed() -> None:
    est = estimate_rent(AREA, comps([40, 60, 80]))
    assert est.comparables_used == 3


def test_implausible_data_is_dropped_and_reported() -> None:
    est = estimate_rent(
        AREA, [*comps([60, 61, 62, 63]), RentComparable(monthly_rent_pln=D(1), area_m2=D(50))]
    )
    assert est.comparables_considered == 4
    assert "comparables_dropped_implausible" in est.warnings


def test_similar_sized_comparables_are_preferred_and_the_window_widens_when_needed() -> None:
    near = comps([60, 61, 62, 63], area=48)
    far = comps([90, 91, 92, 93], area=100)
    est = estimate_rent(AREA, near + far)
    assert est.ppm2_median == D("61.50")
    assert "size_window_widened" not in est.warnings
    only_far = estimate_rent(AREA, far)
    assert "size_window_widened" in only_far.warnings
    assert only_far.ppm2_median == D("91.50")


def test_the_estimate_feeds_the_analysis_with_the_right_comparable_count() -> None:
    est = estimate_rent(AREA, comps([60] * 12))
    rent_input = est.to_input()
    assert rent_input.monthly_rent_pln == D("3000.00")
    assert rent_input.comparables == 12
    assert analyse_listing is not None


def test_the_result_is_deterministic_and_float_free() -> None:
    values = [random.Random(1).randint(40, 90) for _ in range(15)]  # noqa: S311
    a, b = estimate_rent(AREA, comps(values)), estimate_rent(AREA, comps(list(reversed(values))))
    assert a.model_dump_json() == b.model_dump_json()  # input order does not matter
    assert not [v for v in a.model_dump().values() if isinstance(v, float)]


@settings(max_examples=80, deadline=None)
@given(ppm2=st.lists(st.integers(20, 90), min_size=3, max_size=40), factor=st.integers(2, 5))
def test_scaling_all_rents_scales_the_estimate_and_it_stays_inside_the_data(
    ppm2: list[int], factor: int
) -> None:
    base = estimate_rent(AREA, comps(ppm2))
    scaled = estimate_rent(AREA, comps([p * factor for p in ppm2]))
    assert base.monthly_rent_pln is not None
    assert scaled.monthly_rent_pln is not None
    assert abs(scaled.monthly_rent_pln - base.monthly_rent_pln * factor) <= D("0.02") * factor
    assert min(ppm2) * AREA <= base.monthly_rent_pln <= max(ppm2) * AREA
    assert base.low_monthly_pln is not None
    assert base.high_monthly_pln is not None
    assert base.low_monthly_pln <= base.monthly_rent_pln <= base.high_monthly_pln
