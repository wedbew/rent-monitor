"""Legal class of the property and how the price is stated, from the portal text.

A flat sold with VAT or a non-residential unit changes the purchase costs (no PCC, VAT instead;
docs/ENGINE-SPEC.md row 2), so the engine must know. This module only classifies; the money consequences
are computed in N-06. Folded, offline, deterministic.
"""

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from deal_analyzer.ownership import Confidence
from deal_analyzer.text import fold, snippet


class LegalClass(StrEnum):
    RESIDENTIAL = "residential"
    VAT_SALE = "vat_sale"  # residential-looking unit sold as a VAT transaction (developer / company)
    NON_RESIDENTIAL = "non_residential"


PriceBasis = Literal["gross", "net_plus_vat", "unknown"]


class LegalAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    legal_class: LegalClass
    price_basis: PriceBasis
    evidence: tuple[str, ...] = Field(default=(), max_length=6)
    confidence: Confidence

    @property
    def needs_review(self) -> bool:
        """The class was inferred from weak or conflicting text; downstream lowers confidence."""
        return self.confidence is Confidence.LOW


_NON_RESIDENTIAL = re.compile(
    r"\b(?:lokal(?:u)? (?:uzytkow\w+|uslugow\w+|handlow\w+|biurow\w+|gastronomiczn\w+|komercyjn\w+)|"
    r"(?:pomieszczeni\w+|powierzchni\w+) (?:biurow\w+|uslugow\w+|handlow\w+|komercyjn\w+)|"
    r"gabinet\w* (?:lekarsk\w+|stomatologiczn\w+)|"
    r"przeznaczeni\w+ (?:lokalu)?[: ]*(?:uslugow\w+|uzytkow\w+|komercyjn\w+))\b"
)
_RESIDENTIAL = re.compile(
    r"\b(?:lokal(?:u)? mieszkaln\w+|mieszkani\w+ (?:wlasnosciow\w+|dwupokojow\w+|trzypokojow\w+))\b"
)
_CHANGE_TO_RESIDENTIAL = re.compile(
    r"\b(?:zmian\w+ przeznaczeni\w+|mozliwosc\w* zmiany) \w+ (?:na )?mieszkaln\w+"
)
_NET_PLUS_VAT = re.compile(
    r"\bcena netto\b|\bnetto ?\+ ?vat\b|\b\+ ?(?:23|8) ?% ?vat\b|\bplus vat\b|\b\+ ?vat\b|\bkwota netto\b"
)
_GROSS = re.compile(r"\bcena brutto\b|\bbrutto\b|\bcena zawiera vat\b|\bwraz z vat\b|\bz vat\b")
_VAT_MENTION = re.compile(r"\b(?:podatk\w+ vat|faktur\w+ vat|sprzedaz opodatkowan\w+|opodatkowan\w+ vat)\b")
_VAT_EXEMPT = re.compile(r"\b(?:zwolnion\w+ z (?:podatku )?vat|bez vat|nie podlega vat|nie dotyczy vat)\b")
# A commercial unit mentioned as a neighbour ("blisko lokalu uslugowego") is not the unit for sale.
_NEIGHBOUR_CONTEXT = re.compile(
    r"(?:blisko|obok|w poblizu|sasiedztw\w+|sasiad\w*|w okolicy|dookola|przy|naprzeciw)\W{0,3}(?:\w+ ){0,2}$"
)


def _price_basis(text: str, evidence: list[str]) -> tuple[PriceBasis, re.Match[str] | None]:
    net = _NET_PLUS_VAT.search(text)
    gross = _GROSS.search(text)
    if net is not None and not (
        gross is not None and gross.start() < net.start() and "netto" not in gross.group(0)
    ):
        evidence.append(snippet(text, net.start(), net.end()))
        return "net_plus_vat", net
    if gross is not None:
        evidence.append(snippet(text, gross.start(), gross.end()))
        return "gross", None
    return "unknown", None


def _first_own_non_residential(text: str) -> re.Match[str] | None:
    for match in _NON_RESIDENTIAL.finditer(text):
        if not _NEIGHBOUR_CONTEXT.search(text[max(0, match.start() - 32) : match.start()]):
            return match
    return None


def classify_legal(*, title: str, description: str) -> LegalAssessment:
    text = fold(f"{title}\n{description}")
    evidence: list[str] = []
    price_basis, net = _price_basis(text, evidence)
    residential = _RESIDENTIAL.search(text)
    non_res = _first_own_non_residential(text)

    if non_res is not None and (residential is None or _CHANGE_TO_RESIDENTIAL.search(text)):
        evidence.insert(0, snippet(text, non_res.start(), non_res.end()))
        conflicting = residential is not None or _CHANGE_TO_RESIDENTIAL.search(text) is not None
        return LegalAssessment(
            legal_class=LegalClass.NON_RESIDENTIAL,
            price_basis=price_basis,
            evidence=tuple(evidence[:6]),
            confidence=Confidence.LOW if conflicting else Confidence.HIGH,
        )
    vat = _VAT_MENTION.search(text)
    if (net is not None or vat is not None) and _VAT_EXEMPT.search(text) is None:
        if vat is not None:
            evidence.append(snippet(text, vat.start(), vat.end()))
        return LegalAssessment(
            legal_class=LegalClass.VAT_SALE,
            price_basis=price_basis,
            evidence=tuple(evidence[:6]),
            confidence=Confidence.HIGH if net is not None else Confidence.MEDIUM,
        )
    return LegalAssessment(
        legal_class=LegalClass.RESIDENTIAL,
        price_basis=price_basis,
        evidence=tuple(evidence[:6]),
        confidence=Confidence.HIGH if residential is not None else Confidence.MEDIUM,
    )
