"""Ownership classification: title form and whether the whole flat or only a share is for sale.

Invariant 5: fractional ownership (`udział`, `1/2 udziału`, `udział w spadku`) is rejected from yield ranking
and audits. A share in the *common parts* (`udział w gruncie`, `w częściach wspólnych`) is normal for a flat
and is NOT fractional.
Deterministic and offline; confidence is a coarse level, never a float score.
"""

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from deal_analyzer.errors import FractionalOwnershipError
from deal_analyzer.text import fold, snippet

TitleForm = Literal["full_ownership", "cooperative_ownership", "cooperative_tenancy", "unknown"]


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OwnershipAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title_form: TitleForm
    interest: Literal["whole", "fractional", "unknown"]
    share_numerator: int | None = Field(default=None, ge=1)
    share_denominator: int | None = Field(default=None, ge=2)
    structured_value: str | None = Field(default=None, max_length=64)
    evidence: tuple[str, ...] = Field(default=(), max_length=6)
    confidence: Confidence

    @property
    def is_fractional(self) -> bool:
        return self.interest == "fractional"


# Patterns run on folded text (ASCII, lower case): see `deal_analyzer.text.fold`.
_FRACTION_BEFORE = re.compile(r"\b(\d{1,3}) ?/ ?(\d{1,3}) udzial[a-z]{0,6}\b")
_FRACTION_AFTER = re.compile(
    r"\budzial[a-z]{0,6} (?:wynosi |wynoszacy |wynoszacym )?(\d{1,3}) ?/ ?(\d{1,3})\b"
)
_FRACTION_OF_FLAT = re.compile(
    r"\b(\d{1,3} ?/ ?\d{1,3}|polowa|polowe|jedna trzecia|jedna czwarta|jedna druga) "
    r"(?:czesc )?(?:mieszkania|lokalu|nieruchomosci)\b"
)
_INTEREST = re.compile(
    r"\budzial[a-z]{0,6} (?:w )?(?:lokalu|mieszkaniu|nieruchomosci|prawie wlasnosci|domu)\b"
)
_INHERITANCE = re.compile(r"\budzial[a-z]{0,6} (?:w )?(?:spadku|spadkowym|spadkowego)\b")
_COMMON_PARTS = re.compile(
    r"\budzial[a-z]{0,6} (?:w )?"
    r"(?:gruncie|gruntu|czesciach wspolnych|czesci wspolnych|nieruchomosci wspolnej)\b"
)
_FULL = re.compile(r"\b(?:pelna|pelnej|odrebna|odrebnej|wyodrebniona|wyodrebnionej) wlasnosc[a-z]{0,3}\b")
_COOP_OWNERSHIP = re.compile(r"\b(?:spoldzielcze|spoldzielczego) wlasnosciowe\b|\bswpdl\b")
_COOP_TENANCY = re.compile(r"\b(?:spoldzielcze|spoldzielczego) lokatorskie\b")
_STRUCTURED_FULL = frozenset({"full_ownership"})
_STRUCTURED_COOP = frozenset({"limited_ownership"})
_STRUCTURED_SHARE = frozenset({"share", "shared"})


def _valid_fraction(num: int, den: int) -> bool:
    return 1 <= num < den <= 1000


def _title_form(text: str, structured: str | None) -> TitleForm:
    if structured in _STRUCTURED_FULL:
        return "full_ownership"
    if structured in _STRUCTURED_COOP:
        return "cooperative_ownership"
    if _COOP_TENANCY.search(text):
        return "cooperative_tenancy"
    if _COOP_OWNERSHIP.search(text):
        return "cooperative_ownership"
    if _FULL.search(text):
        return "full_ownership"
    return "unknown"


def _detect_fraction(text: str, wire: str | None) -> tuple[bool, int | None, int | None, list[str]]:
    """Whether only a share is offered, the parsed fraction if any, and the evidence found."""
    if wire in _STRUCTURED_SHARE:
        return True, None, None, [f"portal ownership value: {wire}"]
    for pattern in (_FRACTION_BEFORE, _FRACTION_AFTER):
        match = pattern.search(text)
        if match and _valid_fraction(int(match.group(1)), int(match.group(2))):
            return True, int(match.group(1)), int(match.group(2)), [snippet(text, match.start(), match.end())]
    for pattern in (_FRACTION_OF_FLAT, _INHERITANCE, _INTEREST):
        match = pattern.search(text)
        if match is None or (pattern is _INTEREST and not _interest_outside_common(text)):
            continue
        return True, None, None, [snippet(text, match.start(), match.end())]
    return False, None, None, []


def classify_ownership(*, title: str, description: str, structured: str | None = None) -> OwnershipAssessment:
    """Classify from the portal's structured value (preferred) and the seller's text."""
    text = fold(f"{title}\n{description}")
    wire = structured.strip().lower() if structured else None
    fractional, numerator, denominator, evidence = _detect_fraction(text, wire)
    form = _title_form(text, wire)
    structured_whole = wire in (_STRUCTURED_FULL | _STRUCTURED_COOP)
    if form != "unknown" and not structured_whole:
        evidence.append(f"title form from text: {form}")
    interest: Literal["whole", "fractional", "unknown"]
    if fractional:
        interest = "fractional"
    elif form != "unknown" or structured_whole:
        interest = "whole"
    else:
        interest = "unknown"
    if structured_whole or wire in _STRUCTURED_SHARE:
        confidence = Confidence.HIGH
    else:
        confidence = Confidence.MEDIUM if evidence else Confidence.LOW
    return OwnershipAssessment(
        title_form=form,
        interest=interest,
        share_numerator=numerator,
        share_denominator=denominator,
        structured_value=wire[:64] if wire else None,
        evidence=tuple(evidence[:6]),
        confidence=confidence,
    )


def _interest_outside_common(text: str) -> bool:
    """True when an interest phrase appears somewhere other than inside a common-parts phrase."""
    stripped = _COMMON_PARTS.sub(" ", text)
    return _INTEREST.search(stripped) is not None


def require_whole_ownership(assessment: OwnershipAssessment, otodom_id: str) -> None:
    """Invariant 5: reject fractional ownership. The worker maps it to `rejected / FRACTIONAL_OWNERSHIP`."""
    if assessment.is_fractional:
        raise FractionalOwnershipError(otodom_id, assessment.evidence)
