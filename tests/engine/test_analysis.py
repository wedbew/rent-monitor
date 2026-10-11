"""N-09: the canonical DealAnalysis, its assembly (invariant 5 end to end) and the Markdown view
(invariant 6)."""

import json
import re
from decimal import Decimal as D
from typing import Any

import pytest
from conftest import make_ad
from deal_analyzer import FractionalOwnershipError, extract_listing
from deal_analyzer.analysis import DealAnalysis, RentInput, analyse_listing
from deal_analyzer.assumptions import Assumptions
from deal_analyzer.markdown import render_markdown
from deal_analyzer.ownership import Confidence
from deal_analyzer.vision import parse_vision_output

RENT = RentInput(monthly_rent_pln=D(2_600), basis="asking", comparables=25)


def analyse(ad: dict[str, Any] | None = None, **kw: Any) -> DealAnalysis:
    listing = extract_listing(ad or make_ad(description="Pełna własność. Ładne mieszkanie."))
    return analyse_listing(listing, rent=kw.pop("rent", RENT), risk_free=kw.pop("risk_free", D("0.05")), **kw)


# ---- assembly ----
def test_a_complete_analysis_is_assembled_from_the_pieces() -> None:
    a = analyse()
    assert a.schema_version == 1
    assert a.listing.otodom_id == "90000001"
    assert a.ownership.interest == "whole"
    assert a.valuation.grade in {"A", "B", "C", "D", "E"}
    assert a.cash_flow.years
    assert a.rent.basis == "asking"
    assert a.rent.haircut == D("0.03")
    assert a.rent.monthly_after_haircut_pln == D("2522.00")  # 2,600 less the 3 % haircut
    assert a.valuation.max_bid_pln is not None


@pytest.mark.invariant
@pytest.mark.parametrize(
    "description",
    [
        "Sprzedam 1/2 udziału w mieszkaniu.",
        "Oferuję udział w spadku, mieszkanie 50 m2.",
        "Sprzedam połowę mieszkania.",
    ],
)
def test_invariant_fractional_ownership_never_reaches_the_math(description: str) -> None:
    listing = extract_listing(make_ad(description=description))
    with pytest.raises(FractionalOwnershipError):
        analyse_listing(listing, rent=RENT, risk_free=D("0.05"))


def test_fractional_ownership_from_the_portal_value_is_rejected_too() -> None:
    listing = extract_listing(make_ad(chars={"building_ownership": "share"}))
    with pytest.raises(FractionalOwnershipError):
        analyse_listing(listing, rent=RENT, risk_free=D("0.05"))


def test_too_few_comparables_refuse_the_grade_and_say_why() -> None:
    a = analyse(rent=RentInput(monthly_rent_pln=D(2_600), comparables=2))
    assert a.valuation.grade == "N"
    assert a.valuation.verdict == "insufficient_data"
    assert "rent_refused_too_few_comparables" in a.warnings
    assert a.confidence is Confidence.LOW


def test_a_thin_market_lowers_confidence_but_keeps_the_grade() -> None:
    a = analyse(rent=RentInput(monthly_rent_pln=D(2_600), comparables=5))
    assert a.valuation.grade != "N"
    assert "rent_thin_market" in a.warnings


def test_the_asking_basis_is_labelled_and_achieved_rents_get_no_haircut() -> None:
    achieved = analyse(rent=RentInput(monthly_rent_pln=D(2_600), basis="achieved", comparables=25))
    assert achieved.rent.haircut == 0
    assert achieved.rent.monthly_after_haircut_pln == D(2_600)
    assert achieved.rent.basis == "achieved"


def test_vision_is_applied_clamped_and_recorded() -> None:
    vision = parse_vision_output(
        '{"condition": "renovation", "capex_adjustment": 5, "rent_adjustment": -0.5}'
    )
    a = analyse(vision=vision, model="vendor/v1", prompt_version="p1")
    assert a.vision is not None
    assert a.vision.capex is not None
    assert a.vision.capex.clamped
    assert a.capex_used_pln == (a.capex.base_pln * D("1.15")).quantize(D("0.01"))
    assert a.rent.monthly_used_pln == (a.rent.monthly_after_haircut_pln * D("0.85")).quantize(D("0.01"))
    assert a.vision.model == "vendor/v1"
    assert "vision_unavailable" not in a.warnings


def test_without_vision_the_condition_is_assumed_and_the_warning_says_so() -> None:
    a = analyse()
    assert a.vision is None
    assert a.capex.condition_assumed
    assert "vision_unavailable" in a.warnings
    assert "capex_prices_are_placeholders" in a.warnings


def test_vat_sales_and_non_residential_flow_through_the_costs() -> None:
    vat = analyse(make_ad(description="Pełna własność. Cena netto + 8% VAT, faktura VAT."))
    assert vat.legal.legal_class.value == "vat_sale"
    assert vat.cash_flow.purchase.pcc_pln == 0


def test_assumptions_can_be_overridden_per_audit() -> None:
    rich = RentInput(
        monthly_rent_pln=D(12_000), comparables=25
    )  # above the 100k ryczałt threshold for one owner
    one = analyse(rent=rich, assumptions=Assumptions(owners=1))
    two = analyse(rent=rich, assumptions=Assumptions(owners=2))
    assert (
        two.cash_flow.years[0].income_tax_pln < one.cash_flow.years[0].income_tax_pln
    )  # each owner has a threshold


# ---- canonical JSON ----
def test_the_analysis_round_trips_through_its_json_byte_for_byte() -> None:
    a = analyse()
    raw = a.model_dump_json()
    again = DealAnalysis.model_validate_json(raw)
    assert again == a
    assert again.model_dump_json() == raw


def test_the_canonical_json_is_float_free_and_stable() -> None:
    raw = analyse().model_dump_json()
    assert analyse().model_dump_json() == raw
    assert not re.search(r"\d\.\d+e[+-]?\d", raw)  # no float repr artefacts

    def walk(v: object) -> None:
        if isinstance(v, dict):
            [walk(x) for x in v.values()]
        elif isinstance(v, list):
            [walk(x) for x in v]
        else:
            assert not isinstance(v, float)

    walk(json.loads(raw, parse_float=D))


# ---- invariant 6 ----
def _numbers_in_json(raw: str) -> set[D]:
    found: set[D] = set()

    def walk(v: object) -> None:
        if isinstance(v, dict):
            [walk(x) for x in v.values()]
        elif isinstance(v, list):
            [walk(x) for x in v]
        elif isinstance(v, int | D) and not isinstance(v, bool):
            found.add(D(v))
        elif isinstance(v, str):
            for m in re.findall(r"-?\d+(?:\.\d+)?", v):
                found.add(D(m))

    walk(json.loads(raw, parse_float=D))
    return found


def _numbers_in_markdown(md: str, lang: str) -> set[D]:
    out: set[D] = set()
    for token in re.findall(r"-?\d[\d\u00a0,. ]*\d|-?\d", md):
        cleaned = token.replace("\u00a0", "").replace(" ", "")
        cleaned = cleaned.replace(",", "") if lang == "en" else cleaned.replace(",", ".")
        try:
            out.add(D(cleaned))
        except Exception:  # noqa: S112
            continue
    return out


@pytest.mark.invariant
@pytest.mark.parametrize("lang", ["en", "pl"])
def test_invariant_json_is_canonical_markdown_is_a_view(lang: str) -> None:
    """The view is derived from the JSON alone, and every number it prints is a number in the JSON."""
    a = analyse(vision=parse_vision_output('{"condition": "refresh"}'))
    raw = a.model_dump_json()
    from_json = DealAnalysis.model_validate_json(raw)  # the view needs nothing but the JSON
    md = render_markdown(from_json, lang)  # type: ignore[arg-type]
    assert md == render_markdown(a, lang)  # type: ignore[arg-type]
    allowed = _numbers_in_json(raw)
    shown = _numbers_in_markdown(md, lang)
    stray = {n for n in shown if n not in allowed and n not in {D(i) for i in range(0, 11)}}
    assert not stray, f"numbers in the Markdown that are not in the JSON: {sorted(stray)[:10]}"


def test_markdown_shows_the_verdict_max_bid_and_a_row_per_year() -> None:
    en = render_markdown(analyse(), "en")
    assert "Max Bid" in en
    assert "Grade" in en
    assert en.count("\n| ") == 11  # the header row and ten year rows (the separator row starts with "|-")
    pl = render_markdown(analyse(), "pl")
    assert "Werdykt" in pl
    assert "Maksymalna cena" in pl


def test_markdown_warns_loudly_about_placeholder_capex_and_missing_data() -> None:
    en = render_markdown(analyse(), "en")
    assert "placeholders" in en
    assert "Photos were not analysed" in en
    refused = render_markdown(analyse(rent=RentInput(monthly_rent_pln=D(2_600), comparables=1)), "en")
    assert "no grade is given" in refused
    assert "Insufficient data" in refused


def test_markdown_labels_the_rent_as_asking_based_and_formats_numbers_by_language() -> None:
    assert "asking-based" in render_markdown(analyse(), "en")
    assert "450,000.00" in render_markdown(analyse(), "en")
    assert "450\u00a0000,00" in render_markdown(analyse(), "pl")


def test_a_missing_max_bid_is_said_not_hidden() -> None:
    a = analyse(rent=RentInput(monthly_rent_pln=D(0), comparables=25), risk_free=D("0.30"))
    assert a.valuation.max_bid_pln is None
    assert "no price reaches the hurdle" in render_markdown(a, "en")
