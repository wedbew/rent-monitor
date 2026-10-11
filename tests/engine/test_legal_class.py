"""N-02: residential / VAT sale / non-residential classification and how the price is stated."""

import time

import pytest
from deal_analyzer import Confidence, LegalClass, classify_legal


def legal(description: str, title: str = "Lokal"):
    return classify_legal(title=title, description=description)


@pytest.mark.parametrize(
    "description",
    [
        "Lokal użytkowy 45 m2, parter, wejście od ulicy.",
        "Lokal usługowy w centrum miasta, idealny pod gabinet.",
        "Pomieszczenie biurowe 60 m2, klimatyzacja.",
        "Lokal handlowy z witryną, ruchliwa ulica.",
        "Przeznaczenie lokalu: usługowe.",
        "LOKAL UŻYTKOWY, cena do negocjacji",
        "lokal uzytkowy bez diakrytykow",
    ],
)
def test_non_residential_units(description: str) -> None:
    result = legal(description)
    assert result.legal_class is LegalClass.NON_RESIDENTIAL
    assert result.confidence is Confidence.HIGH
    assert result.evidence


def test_a_non_residential_unit_with_a_residential_change_option_is_flagged_with_low_confidence() -> None:
    result = legal("Lokal użytkowy z możliwością zmiany przeznaczenia na mieszkalny.")
    assert result.legal_class is LegalClass.NON_RESIDENTIAL
    assert result.confidence is Confidence.LOW
    assert result.needs_review


@pytest.mark.parametrize(
    "description",
    [
        "Cena netto 450 000 zł + 8% VAT.",
        "Cena 500 000 zł + 23% VAT, faktura VAT.",
        "Kwota netto, plus VAT, sprzedaż opodatkowana.",
        "Sprzedaż podlega podatkowi VAT, deweloper.",
    ],
)
def test_vat_sales(description: str) -> None:
    assert legal(description).legal_class is LegalClass.VAT_SALE


def test_price_basis_net_plus_vat_vs_gross() -> None:
    assert legal("Cena netto 450 000 zł + 8% VAT.").price_basis == "net_plus_vat"
    assert legal("Cena brutto 480 000 zł.").price_basis == "gross"
    assert legal("Mieszkanie, cena 480 000 zł.").price_basis == "unknown"


@pytest.mark.parametrize(
    "description",
    [
        "Cena brutto, mieszkanie własnościowe, bez prowizji.",
        "Lokal mieszkalny 50 m2, cena zawiera VAT.",
        "Dwupokojowe mieszkanie, zwolnione z podatku VAT, rynek wtórny.",
        "Sprzedaż bez VAT, osoba prywatna.",
        "Ładne mieszkanie, dwa pokoje, balkon.",
        "Mieszkanie blisko lokalu usługowego i sklepu.",  # nearby shops are not the unit itself
        "",
    ],
)
def test_ordinary_residential_listings(description: str) -> None:
    assert legal(description).legal_class is LegalClass.RESIDENTIAL


def test_residential_text_beats_a_stray_commercial_word() -> None:
    result = legal("Lokal mieszkalny na parterze, obok lokal usługowy sąsiada.")
    assert result.legal_class is LegalClass.RESIDENTIAL


def test_evidence_is_bounded() -> None:
    result = legal("Cena netto + VAT. " * 100)
    assert len(result.evidence) <= 6
    assert all(len(e) <= 120 for e in result.evidence)


@pytest.mark.parametrize("filler", ["lokal ", "netto + ", "+ vat ", "przeznaczenie lokalu ", "zwolniony z "])
def test_adversarial_long_text_is_classified_quickly(filler: str) -> None:
    started = time.perf_counter()
    legal(filler * 30_000)
    assert time.perf_counter() - started < 2.0
