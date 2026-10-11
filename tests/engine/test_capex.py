"""N-05: CAPEX estimate (docs/ENGINE-SPEC.md row 4). The catalog prices are placeholders, so tests
check structure and rules."""

from decimal import Decimal as D

import pytest
from deal_analyzer import Condition, Confidence, apply_vision, estimate_capex, parse_vision_output
from deal_analyzer.capex import CATALOG_PLN_PER_M2, TIER_MULTIPLIER, city_tier


def test_a_good_flat_needs_no_capex() -> None:
    est = estimate_capex(area_m2=D(50), condition=Condition.GOOD, city="Leszno")
    assert est.base_pln == 0
    assert est.low_pln == est.high_pln == 0


def test_capex_scales_with_area_condition_and_tier() -> None:
    small = estimate_capex(area_m2=D(40), condition=Condition.RENOVATION, city="Leszno")
    large = estimate_capex(area_m2=D(80), condition=Condition.RENOVATION, city="Leszno")
    assert large.base_pln == small.base_pln * 2
    costs = [
        estimate_capex(area_m2=D(50), condition=c, city="Leszno").base_pln
        for c in (Condition.GOOD, Condition.REFRESH, Condition.RENOVATION, Condition.SHELL)
    ]
    assert costs == sorted(costs)
    assert len(set(costs)) == 4
    metro = estimate_capex(area_m2=D(50), condition=Condition.RENOVATION, city="Warszawa")
    other = estimate_capex(area_m2=D(50), condition=Condition.RENOVATION, city="Leszno")
    assert metro.base_pln > other.base_pln
    assert metro.base_pln == (
        D(50) * CATALOG_PLN_PER_M2[Condition.RENOVATION] * TIER_MULTIPLIER["metro"]
    ).quantize(D("0.01"))


@pytest.mark.parametrize(
    ("city", "tier"),
    [
        ("Warszawa", "metro"),
        ("WARSZAWA", "metro"),
        ("Kraków", "major"),
        ("Wrocław", "major"),
        ("Łódź", "major"),
        ("Leszno", "other"),
        (None, "other"),
        ("", "other"),
    ],
)
def test_city_tiers_ignore_case_and_accents(city: str | None, tier: str) -> None:
    assert city_tier(city) == tier


def test_an_unknown_condition_assumes_refresh_with_low_confidence() -> None:
    est = estimate_capex(area_m2=D(50), condition=Condition.UNKNOWN, city="Leszno")
    assert est.condition_used is Condition.REFRESH
    assert est.condition_assumed
    assert est.confidence is Confidence.LOW
    assert est.base_pln == estimate_capex(area_m2=D(50), condition=Condition.REFRESH, city="Leszno").base_pln


def test_a_known_condition_in_a_known_city_has_medium_confidence_and_a_range() -> None:
    est = estimate_capex(area_m2=D(50), condition=Condition.RENOVATION, city="Kraków")
    assert est.confidence is Confidence.MEDIUM
    assert est.low_pln < est.base_pln < est.high_pln
    assert est.low_pln == (est.base_pln * D("0.75")).quantize(D("0.01"))
    assert (
        estimate_capex(area_m2=D(50), condition=Condition.RENOVATION, city=None).confidence is Confidence.LOW
    )


def test_prices_are_always_labelled_as_placeholders_until_replaced() -> None:
    est = estimate_capex(area_m2=D(50), condition=Condition.RENOVATION, city="Leszno")
    assert est.prices_are_placeholders is True
    assert est.catalog_version.startswith("placeholder")


def test_no_float_and_deterministic() -> None:
    a = estimate_capex(area_m2=D("48.5"), condition=Condition.REFRESH, city="Gdańsk")
    b = estimate_capex(area_m2=D("48.5"), condition=Condition.REFRESH, city="Gdańsk")
    assert a.model_dump_json() == b.model_dump_json()
    assert not [v for v in a.model_dump().values() if isinstance(v, float)]


def test_the_vision_adjustment_applies_to_the_catalog_base_and_is_clamped() -> None:
    est = estimate_capex(area_m2=D(50), condition=Condition.RENOVATION, city="Leszno")
    out = parse_vision_output('{"condition": "renovation", "capex_adjustment": 3}')
    record = apply_vision(out, model="m", prompt_version="v1", capex_base=est.base_pln, rent_base=None)
    assert record.capex is not None
    assert record.capex.value == est.base_pln * D("1.15")
