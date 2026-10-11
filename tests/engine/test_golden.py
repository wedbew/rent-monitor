"""N-10: golden DealAnalysis snapshots and whole-pipeline properties.

Each golden file pins the complete canonical JSON of one hand-built, anonymised deal. A change to any
rule, constant or
assumption shows up here as a diff that the PR must explain (PR template: "Golden DealAnalysis
snapshots unchanged, or each
diff explained"). Regenerate deliberately with `UPDATE_GOLDEN=1 uv run pytest tests/engine/test_golden.py`.
"""

import json
import os
from collections.abc import Callable
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest
from conftest import make_ad
from deal_analyzer import extract_listing
from deal_analyzer.analysis import DealAnalysis, RentInput, analyse_listing
from deal_analyzer.markdown import render_markdown
from deal_analyzer.vision import parse_vision_output
from hypothesis import given, settings
from hypothesis import strategies as st

GOLDEN = Path(__file__).parent / "golden"
RISK_FREE = D("0.055")


def _leszno() -> DealAnalysis:
    ad = make_ad(
        description="Pełna własność, księga wieczysta urządzona. Jasne mieszkanie po remoncie kuchni."
    )
    vision = parse_vision_output(
        '{"condition": "refresh", "photos": [{"kind": "interior"}, {"kind": "interior"}, {"kind": "render"}],'
        ' "capex_adjustment": 0.05, "rent_adjustment": 0.02}'
    )
    return analyse_listing(
        extract_listing(ad),
        rent=RentInput(monthly_rent_pln=D(2_600), comparables=34),
        risk_free=RISK_FREE,
        vision=vision,
        model="vendor/vision-1",
        prompt_version="golden-1",
    )


def _warsaw_thin_market() -> DealAnalysis:
    ad = make_ad(
        id=90000002,
        title="Kawalerka w centrum",
        chars={"price": "780000", "m": "32", "rooms_num": "1", "rent": "850", "build_year": "1935"},
        location={
            "coordinates": {"latitude": 52.2297, "longitude": 21.0122},
            "address": {"city": {"name": "Warszawa"}},
        },
        description="Odrębna własność. Kamienica, wysoki standard.",
    )
    return analyse_listing(
        extract_listing(ad), rent=RentInput(monthly_rent_pln=D(3_900), comparables=6), risk_free=RISK_FREE
    )


def _vat_new_build() -> DealAnalysis:
    ad = make_ad(
        id=90000003,
        title="Nowe mieszkanie od dewelopera",
        chars={"price": "520000", "m": "55", "rooms_num": "3", "rent": "450", "build_year": "2026"},
        description="Pełna własność. Cena netto + 8% VAT, faktura VAT. Stan deweloperski.",
    )
    return analyse_listing(
        extract_listing(ad), rent=RentInput(monthly_rent_pln=D(3_300), comparables=18), risk_free=RISK_FREE
    )


def _cooperative_no_data() -> DealAnalysis:
    ad = make_ad(
        id=90000004,
        title="Mieszkanie spółdzielcze",
        chars={"price": "310000", "m": "44", "rooms_num": "2", "building_ownership": "limited_ownership"},
        description="Spółdzielcze własnościowe prawo do lokalu.",
        drop=["rent"],
    )
    return analyse_listing(
        extract_listing(ad), rent=RentInput(monthly_rent_pln=D(2_100), comparables=2), risk_free=RISK_FREE
    )


CASES: dict[str, Callable[[], DealAnalysis]] = {
    "leszno_with_vision": _leszno,
    "warsaw_thin_market": _warsaw_thin_market,
    "vat_new_build": _vat_new_build,
    "cooperative_too_few_comparables": _cooperative_no_data,
}


def _pretty(analysis: DealAnalysis) -> str:
    return (
        json.dumps(json.loads(analysis.model_dump_json()), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )


@pytest.mark.parametrize("name", CASES)
def test_golden_analysis_is_unchanged(name: str) -> None:
    actual = _pretty(CASES[name]())
    path = GOLDEN / f"{name}.json"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(actual, encoding="utf-8")
    assert path.exists(), f"missing golden file {path.name}; run with UPDATE_GOLDEN=1 and review the diff"
    assert actual == path.read_text(encoding="utf-8"), (
        f"{name}: the canonical result changed. If intended, regenerate with UPDATE_GOLDEN=1 "
        "and explain every diff in the PR."
    )


@pytest.mark.parametrize("name", CASES)
def test_golden_markdown_is_unchanged(name: str) -> None:
    actual = render_markdown(CASES[name](), "en")
    path = GOLDEN / f"{name}.md"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(actual, encoding="utf-8")
    assert actual == path.read_text(encoding="utf-8")


def test_the_goldens_cover_the_branches_that_matter() -> None:
    results = {name: build() for name, build in CASES.items()}
    assert results["leszno_with_vision"].vision is not None
    assert results["warsaw_thin_market"].capex.tier == "metro"
    assert results["warsaw_thin_market"].rent.confidence.value == "medium"
    assert results["vat_new_build"].legal.legal_class.value == "vat_sale"
    assert results["vat_new_build"].cash_flow.purchase.pcc_pln == 0
    assert results["cooperative_too_few_comparables"].valuation.grade == "N"
    assert results["cooperative_too_few_comparables"].ownership.title_form == "cooperative_ownership"


# ---- whole-pipeline properties ----
listing_ads = st.builds(
    lambda price, area, rooms, fee: make_ad(
        chars={"price": str(price), "m": str(area), "rooms_num": str(rooms), "rent": str(fee)}
    ),
    price=st.integers(120_000, 1_800_000),
    area=st.integers(18, 140),
    rooms=st.integers(1, 6),
    fee=st.integers(0, 1_500),
)


@settings(max_examples=60, deadline=None)
@given(ad=listing_ads, rent=st.integers(1_000, 9_000), comparables=st.integers(0, 60))
def test_every_valid_input_yields_a_consistent_round_tripping_analysis(
    ad: dict[str, Any], rent: int, comparables: int
) -> None:
    a = analyse_listing(
        extract_listing(ad),
        rent=RentInput(monthly_rent_pln=D(rent), comparables=comparables),
        risk_free=RISK_FREE,
    )
    raw = a.model_dump_json()
    assert DealAnalysis.model_validate_json(raw).model_dump_json() == raw
    assert len(a.cash_flow.years) == 10
    assert (a.valuation.grade == "N") == (comparables < 3)
    if a.valuation.max_bid_pln is not None and a.valuation.verdict == "buy_at_asking":
        assert a.valuation.max_bid_pln >= a.valuation.asking_price_pln
    assert render_markdown(a, "en") == render_markdown(DealAnalysis.model_validate_json(raw), "en")


@settings(max_examples=40, deadline=None)
@given(rent=st.integers(1_500, 7_000), cheaper=st.integers(10_000, 150_000))
def test_a_lower_asking_price_never_gets_a_worse_grade(rent: int, cheaper: int) -> None:
    order = "ABCDE"
    base_ad = make_ad(chars={"price": "600000"})
    low_ad = make_ad(chars={"price": str(600_000 - cheaper)})
    kw: dict[str, Any] = {"rent": RentInput(monthly_rent_pln=D(rent), comparables=40), "risk_free": RISK_FREE}
    base = analyse_listing(extract_listing(base_ad), **kw)
    low = analyse_listing(extract_listing(low_ad), **kw)
    assert order.index(low.valuation.grade) <= order.index(base.valuation.grade)
