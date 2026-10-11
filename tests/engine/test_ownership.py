"""N-02: ownership classification and invariant 5 (fractional ownership is rejected)."""

import time

import pytest
from conftest import make_ad
from deal_analyzer import (
    Confidence,
    FractionalOwnershipError,
    classify_ownership,
    extract_listing,
    require_whole_ownership,
)
from deal_analyzer.text import fold


def assess(description: str, *, title: str = "Mieszkanie", structured: str | None = None):
    return classify_ownership(title=title, description=description, structured=structured)


# ---- invariant 5 ----
@pytest.mark.invariant
@pytest.mark.parametrize(
    "description",
    [
        "Sprzedam 1/2 udziału w mieszkaniu przy ulicy Testowej.",
        "Na sprzedaż udział 1/3 w lokalu mieszkalnym.",
        "Sprzedaż udziału w mieszkaniu, współwłaściciel mieszka na miejscu.",
        "Oferuję udział w spadku po rodzicach, mieszkanie 50 m2.",
        "Udział wynosi 2/5 w prawie własności lokalu.",
        "SPRZEDAM POŁOWĘ MIESZKANIA w centrum",
        "sprzedam 1/2 udzialu w mieszkaniu",  # no diacritics
        "1 / 2 udziału w nieruchomości",
        "<p>Sprzedam <b>1/2</b> udziału w lokalu</p>",  # HTML noise
    ],
)
def test_invariant_fractional_ownership_rejected(description: str) -> None:
    result = assess(description)
    assert result.is_fractional
    assert result.evidence
    with pytest.raises(FractionalOwnershipError) as err:
        require_whole_ownership(result, "ID1")
    assert err.value.otodom_id == "ID1"


@pytest.mark.invariant
def test_invariant_a_structured_share_value_alone_is_enough_to_reject() -> None:
    result = assess("Ładne mieszkanie.", structured="share")
    assert result.is_fractional
    assert result.confidence is Confidence.HIGH
    with pytest.raises(FractionalOwnershipError):
        require_whole_ownership(result, "ID1")


@pytest.mark.invariant
def test_invariant_a_fractional_title_is_caught_even_when_the_description_is_clean() -> None:
    assert assess("Piękny widok.", title="Sprzedam 1/2 udziału w mieszkaniu").is_fractional


def test_the_share_is_parsed_when_it_is_a_valid_fraction() -> None:
    result = assess("Sprzedam 2/5 udziału w mieszkaniu")
    assert (result.share_numerator, result.share_denominator) == (2, 5)


@pytest.mark.parametrize(
    "text", ["Sprzedam 5/2 udziału w mieszkaniu", "0/3 udziału", "3/3 udziału", "1/5000 udziału"]
)
def test_impossible_fractions_are_not_trusted_as_shares(text: str) -> None:
    result = assess(text)
    assert result.share_numerator is None


# ---- must NOT reject normal flats ----
@pytest.mark.parametrize(
    "description",
    [
        "Cena zawiera udział w gruncie oraz udział w częściach wspólnych nieruchomości.",
        "Mieszkanie z udziałem w gruncie, księga wieczysta urządzona, pełna własność.",
        "W cenie udział w nieruchomości wspólnej (części wspólne budynku).",
        "Do mieszkania przynależy udział w gruncie 5/1000.",
        "Udziałowiec spółdzielni nie jest wymagany. Spokojne mieszkanie.",
        "Spółdzielcze własnościowe prawo do lokalu, 3 pokoje.",
        "Mieszkanie 48 m2, 2 pokoje, 1/2 piętra widok na park.",  # 1/2 appears, but not as a share
        "",
    ],
)
def test_normal_flats_are_not_fractional(description: str) -> None:
    result = assess(description)
    assert not result.is_fractional, result.evidence
    require_whole_ownership(result, "ID1")


# ---- title forms ----
@pytest.mark.parametrize(
    ("description", "form"),
    [
        ("Pełna własność, księga wieczysta.", "full_ownership"),
        ("Odrębna własność lokalu.", "full_ownership"),
        ("Spółdzielcze własnościowe prawo do lokalu.", "cooperative_ownership"),
        ("SWPdL, cicha okolica.", "cooperative_ownership"),
        ("Spółdzielcze lokatorskie prawo do lokalu.", "cooperative_tenancy"),
        ("Ładne mieszkanie.", "unknown"),
    ],
)
def test_title_form_from_text(description: str, form: str) -> None:
    assert assess(description).title_form == form


def test_structured_values_win_and_give_high_confidence() -> None:
    result = assess("Spółdzielcze lokatorskie", structured="full_ownership")
    assert (result.title_form, result.interest, result.confidence) == (
        "full_ownership",
        "whole",
        Confidence.HIGH,
    )
    assert assess("x", structured="limited_ownership").title_form == "cooperative_ownership"


def test_unknown_text_means_unknown_interest_with_low_confidence() -> None:
    result = assess("Ładne mieszkanie w dobrej lokalizacji.")
    assert (result.interest, result.title_form, result.confidence) == ("unknown", "unknown", Confidence.LOW)
    assert result.evidence == ()


def test_evidence_is_short_and_bounded() -> None:
    result = assess("Sprzedam 1/2 udziału w mieszkaniu. " * 50)
    assert len(result.evidence) <= 6
    assert all(len(e) <= 120 for e in result.evidence)


def test_classification_works_from_an_extracted_listing() -> None:
    listing = extract_listing(make_ad(description="Sprzedam 1/2 udziału w mieszkaniu."))
    assert classify_ownership(
        title=listing.title, description=listing.description, structured=listing.building_ownership
    ).is_fractional


def test_the_portal_ownership_characteristic_is_extracted() -> None:
    assert extract_listing(make_ad(chars={"building_ownership": "share"})).building_ownership == "share"
    assert extract_listing(make_ad()).building_ownership is None


# ---- folding and robustness ----
def test_fold_removes_html_accents_case_and_extra_space() -> None:
    assert fold("<b>ŁÓDŹ</b>   Śródmieście &amp; okolice") == "lodz srodmiescie & okolice"


@pytest.mark.parametrize("filler", ["udział ", "1/2 ", "udział w ", "/ " * 3, "a" * 50 + " "])
def test_adversarial_long_text_is_classified_quickly(filler: str) -> None:
    text = filler * 20_000  # ~200k characters, the largest description we accept
    started = time.perf_counter()
    assess(text)
    assert time.perf_counter() - started < 2.0
