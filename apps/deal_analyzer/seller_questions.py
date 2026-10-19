"""Deterministic, grounded questions to ask the seller (G-03, RM-404).

A pure function of a finished `DealAnalysis`: the same analysis always yields the same ordered
questions with the same IDs. Every question names the facts it rests on (`evidence`) and a stable ID derived
from its rule and that evidence key, so a changed fact yields a new ID and an unchanged one keeps it.
No clock, no database, no network, and no money: this module asks, it never computes (invariant 4).
Duplicates collapse on ID.

The question text is Polish, the report language of the product; the stable `rule` code lets the SPA
localise later without re-deriving anything.

LEGAL[republication]: the questions echo listing facts and equipment named from listing photos to the
audit's owner.
LEGAL[images]: equipment items come from vision output on listing photos (RM-387); no image is handled here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from deal_analyzer.analysis import DealAnalysis
from deal_analyzer.vision import Condition, SaleStatus

SELLER_QUESTIONS_VERSION = 1
MAX_EQUIPMENT_QUESTIONS = 10  # a bounded list: the first ones in stable order, never a random sample
_SEP = "\x1e"


class SellerQuestionRule(StrEnum):
    """Rule codes; the order of this enum is NOT the output order (see `_RULE_ORDER`)."""

    ADMIN_FEE_UNKNOWN = "admin_fee_unknown"
    FLOOR_UNKNOWN = "floor_unknown"
    BUILD_YEAR_UNKNOWN = "build_year_unknown"
    CONDITION_UNCLEAR = "condition_unclear"
    FLOOR_PLAN_MISSING = "floor_plan_missing"
    SELLER_STATUS_UNCLEAR = "seller_status_unclear"
    EQUIPMENT_SALE_STATUS = "equipment_sale_status"


_RULE_ORDER: tuple[SellerQuestionRule, ...] = (
    SellerQuestionRule.ADMIN_FEE_UNKNOWN,
    SellerQuestionRule.FLOOR_UNKNOWN,
    SellerQuestionRule.BUILD_YEAR_UNKNOWN,
    SellerQuestionRule.CONDITION_UNCLEAR,
    SellerQuestionRule.FLOOR_PLAN_MISSING,
    SellerQuestionRule.SELLER_STATUS_UNCLEAR,
    SellerQuestionRule.EQUIPMENT_SALE_STATUS,
)


class SellerQuestion(BaseModel):
    """One question. `evidence` names the facts it rests on; it is never empty."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^sq-[0-9a-f]{16}$")
    rule: SellerQuestionRule
    text: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=300)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=20)


class SellerQuestionBlock(BaseModel):
    """The versioned block persisted with the audit. Old audits without it have no questions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(default=SELLER_QUESTIONS_VERSION, ge=1)
    questions: tuple[SellerQuestion, ...] = Field(default=(), max_length=40)


def question_id(rule: SellerQuestionRule, evidence: Iterable[str]) -> str:
    """Stable ID: the same rule over the same facts always hashes to the same value."""
    key = _SEP.join((rule.value, *sorted(evidence)))
    return "sq-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _question(rule: SellerQuestionRule, text: str, reason: str, evidence: tuple[str, ...]) -> SellerQuestion:
    return SellerQuestion(
        id=question_id(rule, evidence), rule=rule, text=text, reason=reason, evidence=evidence
    )


def _equipment_questions(analysis: DealAnalysis) -> list[SellerQuestion]:
    """One question per distinct (item, sale status) that is not known to be included. Items seen in several
    photos collapse into one question; their media ordinals are part of the evidence."""
    if analysis.vision is None:
        return []
    spellings: dict[tuple[str, str], set[str]] = {}
    ordinals: dict[tuple[str, str], set[str]] = {}
    for obs in analysis.vision.equipment:
        if obs.sale_status == SaleStatus.INCLUDED:
            continue
        key = (obs.item.casefold(), obs.sale_status.value)
        spellings.setdefault(key, set()).add(obs.item)
        ordinals.setdefault(key, set()).add(str(obs.media_ordinal) if obs.media_ordinal is not None else "-")
    questions: list[SellerQuestion] = []
    for item_key, status in sorted(spellings):
        # the displayed spelling is the smallest one seen, so the text does not depend on input order
        display = min(spellings[(item_key, status)])
        group_ordinals = ordinals[(item_key, status)]
        if len(questions) == MAX_EQUIPMENT_QUESTIONS:
            break
        evidence = (
            f"equipment:{item_key}",
            f"sale_status:{status}",
            f"media:{','.join(sorted(group_ordinals))}",
        )
        questions.append(
            _question(
                SellerQuestionRule.EQUIPMENT_SALE_STATUS,
                f"Czy „{display}” zostaje w cenie sprzedaży?",
                "Widoczne na zdjęciach, a ogłoszenie nie mówi, czy zostaje z mieszkaniem.",
                evidence,
            )
        )
    return questions


def seller_questions(analysis: DealAnalysis) -> SellerQuestionBlock:
    """The questions for one analysis, in a fixed rule order, de-duplicated by ID."""
    listing = analysis.listing
    vision = analysis.vision
    candidates: dict[SellerQuestionRule, list[SellerQuestion]] = {rule: [] for rule in _RULE_ORDER}

    if listing.admin_fee_pln is None:
        candidates[SellerQuestionRule.ADMIN_FEE_UNKNOWN].append(
            _question(
                SellerQuestionRule.ADMIN_FEE_UNKNOWN,
                "Jaka jest miesięczna opłata administracyjna (czynsz)?",
                "Ogłoszenie nie podaje czynszu; wlicza się on do kosztów, nie do przychodu.",
                ("listing.admin_fee_pln=absent",),
            )
        )
    missing_floor = [
        name
        for name, value in (("floor", listing.floor), ("building_floors", listing.building_floors))
        if value is None
    ]
    if missing_floor:
        candidates[SellerQuestionRule.FLOOR_UNKNOWN].append(
            _question(
                SellerQuestionRule.FLOOR_UNKNOWN,
                "Na którym piętrze jest mieszkanie i ile pięter ma budynek?",
                "Ogłoszenie nie podaje piętra albo liczby pięter.",
                tuple(f"listing.{name}=absent" for name in missing_floor),
            )
        )
    if listing.build_year is None:
        candidates[SellerQuestionRule.BUILD_YEAR_UNKNOWN].append(
            _question(
                SellerQuestionRule.BUILD_YEAR_UNKNOWN,
                "W którym roku zbudowano budynek i czy wykonano w nim termomodernizację?",
                "Ogłoszenie nie podaje roku budowy.",
                ("listing.build_year=absent",),
            )
        )
    if vision is None or vision.condition in (Condition.UNKNOWN, Condition.RENOVATION, Condition.SHELL):
        condition = "absent" if vision is None else vision.condition.value
        candidates[SellerQuestionRule.CONDITION_UNCLEAR].append(
            _question(
                SellerQuestionRule.CONDITION_UNCLEAR,
                "Kiedy ostatnio remontowano mieszkanie i w jakim stanie są instalacje?",
                "Stan wykończenia z ogłoszenia i zdjęć nie jest jednoznaczny.",
                (f"vision.condition={condition}",),
            )
        )
    if not listing.floor_plan_urls:
        candidates[SellerQuestionRule.FLOOR_PLAN_MISSING].append(
            _question(
                SellerQuestionRule.FLOOR_PLAN_MISSING,
                "Czy jest dostępny rzut mieszkania z wymiarami?",
                "Ogłoszenie nie zawiera rzutu.",
                ("listing.floor_plan_urls=0",),
            )
        )
    if "legal_class_needs_review" in analysis.warnings:
        candidates[SellerQuestionRule.SELLER_STATUS_UNCLEAR].append(
            _question(
                SellerQuestionRule.SELLER_STATUS_UNCLEAR,
                "Czy sprzedaje osoba prywatna, czy firma, i czy sprzedaż podlega VAT?",
                "Z ogłoszenia nie wynika jednoznacznie, czy to sprzedaż niemieszkaniowa lub z VAT.",
                ("warning:legal_class_needs_review",),
            )
        )
    candidates[SellerQuestionRule.EQUIPMENT_SALE_STATUS] = _equipment_questions(analysis)

    ordered: dict[str, SellerQuestion] = {}
    for rule in _RULE_ORDER:
        for question in candidates[rule]:
            ordered.setdefault(question.id, question)
    return SellerQuestionBlock(questions=tuple(ordered.values()))


__all__ = [
    "MAX_EQUIPMENT_QUESTIONS",
    "SELLER_QUESTIONS_VERSION",
    "SellerQuestion",
    "SellerQuestionBlock",
    "SellerQuestionRule",
    "question_id",
    "seller_questions",
]
