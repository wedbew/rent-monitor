"""Seller questions (G-03, RM-404): pure, deterministic, grounded, stable IDs, de-duplicated (offline)."""

import random
from decimal import Decimal

import pytest
from deal_analyzer import DealAnalysis, RentInput, analyse_listing
from deal_analyzer.listing import Listing
from deal_analyzer.seller_questions import (
    MAX_EQUIPMENT_QUESTIONS,
    SellerQuestionBlock,
    SellerQuestionRule,
    question_id,
    seller_questions,
)
from deal_analyzer.vision import Condition, EquipmentObservation, SaleStatus, VisionOutput
from hypothesis import given, settings
from hypothesis import strategies as st
from rm_contracts.audits import SellerQuestionBlock as WireBlock
from rm_contracts.audits import SellerQuestionRuleName

RENT = RentInput(monthly_rent_pln=Decimal("2600"), basis="asking", comparables=14)
RISK_FREE = Decimal("0.055")


def listing(**overrides: object) -> Listing:
    """A hand-built, anonymised SALE listing with every fact the questions look at."""
    fields: dict[str, object] = {
        "otodom_id": "ID00000001",
        "title": "Mieszkanie 2 pokoje, Testowo",
        "description": "Jasne mieszkanie na drugim piętrze.",
        "kind": "SALE",
        "price_pln": Decimal("450000"),
        "area_m2": Decimal("48.5"),
        "rooms": 2,
        "admin_fee_pln": Decimal("600"),
        "floor": "2",
        "building_floors": 5,
        "build_year": 1998,
        "floor_plan_urls": ("https://images.example.test/plan.jpg",),
    }
    fields.update(overrides)
    return Listing.model_validate(fields)


def obs(item: str, ordinal: int | None, status: SaleStatus = SaleStatus.UNKNOWN) -> EquipmentObservation:
    return EquipmentObservation(
        item=item, media_ordinal=ordinal, confidence=Decimal("0.8"), sale_status=status
    )


def analysis(
    lst: Listing | None = None,
    vision: VisionOutput | None = None,
) -> DealAnalysis:
    return analyse_listing(lst or listing(), rent=RENT, risk_free=RISK_FREE, vision=vision)


def rules_of(block: SellerQuestionBlock) -> list[SellerQuestionRule]:
    return [q.rule for q in block.questions]


def test_a_complete_listing_with_a_known_condition_asks_nothing() -> None:
    block = seller_questions(analysis(vision=VisionOutput(condition=Condition.GOOD)))
    assert block.version == 1
    assert block.questions == ()


def test_every_gap_in_the_listing_is_asked_about_in_rule_order() -> None:
    gaps = listing(
        admin_fee_pln=None,
        floor=None,
        building_floors=None,
        build_year=None,
        floor_plan_urls=(),
    )
    block = seller_questions(analysis(gaps))  # no vision: the condition is unknown too
    assert rules_of(block) == [
        SellerQuestionRule.ADMIN_FEE_UNKNOWN,
        SellerQuestionRule.FLOOR_UNKNOWN,
        SellerQuestionRule.BUILD_YEAR_UNKNOWN,
        SellerQuestionRule.CONDITION_UNCLEAR,
        SellerQuestionRule.FLOOR_PLAN_MISSING,
    ]


def test_every_question_names_the_facts_it_rests_on() -> None:
    gaps = listing(admin_fee_pln=None, build_year=None, floor_plan_urls=())
    block = seller_questions(analysis(gaps))
    assert block.questions
    for question in block.questions:
        assert question.evidence
        assert question.text
        assert question.reason
    admin = next(q for q in block.questions if q.rule == SellerQuestionRule.ADMIN_FEE_UNKNOWN)
    assert admin.evidence == ("listing.admin_fee_pln=absent",)


def test_the_same_analysis_gives_the_same_questions_and_ids() -> None:
    a = analysis(listing(admin_fee_pln=None), VisionOutput(condition=Condition.REFRESH))
    again = analysis(listing(admin_fee_pln=None), VisionOutput(condition=Condition.REFRESH))
    assert seller_questions(a).model_dump_json() == seller_questions(again).model_dump_json()


def test_a_changed_fact_gives_a_new_id_and_an_unchanged_one_keeps_it() -> None:
    before = seller_questions(analysis(listing(admin_fee_pln=None), VisionOutput(condition=Condition.GOOD)))
    same_fact = seller_questions(
        analysis(listing(admin_fee_pln=None), VisionOutput(condition=Condition.GOOD))
    )
    changed = seller_questions(
        analysis(listing(admin_fee_pln=None, floor=None), VisionOutput(condition=Condition.GOOD))
    )
    admin_before = next(q for q in before.questions if q.rule == SellerQuestionRule.ADMIN_FEE_UNKNOWN)
    admin_same = next(q for q in same_fact.questions if q.rule == SellerQuestionRule.ADMIN_FEE_UNKNOWN)
    assert admin_before.id == admin_same.id
    assert admin_before.id.startswith("sq-")
    assert len(admin_before.id) == len("sq-") + 16
    floor_new = next(q for q in changed.questions if q.rule == SellerQuestionRule.FLOOR_UNKNOWN)
    assert floor_new.id not in {q.id for q in before.questions}


def test_question_ids_depend_only_on_rule_and_evidence() -> None:
    assert question_id(SellerQuestionRule.FLOOR_UNKNOWN, ("a", "b")) == question_id(
        SellerQuestionRule.FLOOR_UNKNOWN, ("b", "a")
    )
    assert question_id(SellerQuestionRule.FLOOR_UNKNOWN, ("a",)) != question_id(
        SellerQuestionRule.BUILD_YEAR_UNKNOWN, ("a",)
    )


def test_equipment_seen_in_several_photos_is_asked_about_once_with_all_its_photos() -> None:
    vision = VisionOutput(
        condition=Condition.GOOD,
        equipment=(
            obs("Piekarnik", 1, SaleStatus.VISIBLE_ONLY),
            obs("  piekarnik ", 4, SaleStatus.VISIBLE_ONLY),
            obs("Klimatyzacja", 2, SaleStatus.INCLUDED),
        ),
    )
    block = seller_questions(analysis(vision=vision))
    assert rules_of(block) == [SellerQuestionRule.EQUIPMENT_SALE_STATUS]
    question = block.questions[0]
    assert question.text == "Czy „Piekarnik” zostaje w cenie sprzedaży?"
    assert "media:1,4" in question.evidence


def test_equipment_questions_are_bounded_and_stable_under_reordering() -> None:
    items = [obs(f"Sprzęt {i:02d}", i) for i in range(MAX_EQUIPMENT_QUESTIONS + 3)]
    forward = seller_questions(
        analysis(vision=VisionOutput(condition=Condition.GOOD, equipment=tuple(items)))
    )
    backward = seller_questions(
        analysis(vision=VisionOutput(condition=Condition.GOOD, equipment=tuple(reversed(items))))
    )
    assert len(forward.questions) == MAX_EQUIPMENT_QUESTIONS
    assert forward.model_dump_json() == backward.model_dump_json()


@settings(max_examples=60, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["Piekarnik", "piekarnik", "Pralka", "Klimatyzacja", "Szafa", "Winda"]),
            st.one_of(st.none(), st.integers(min_value=0, max_value=20)),
            st.sampled_from([SaleStatus.INCLUDED, SaleStatus.VISIBLE_ONLY, SaleStatus.UNKNOWN]),
        ),
        max_size=12,
    ),
    st.randoms(use_true_random=False),
)
def test_property_order_of_equipment_never_changes_questions_and_ids_are_unique(
    observations: list[tuple[str, int | None, SaleStatus]], rnd: random.Random
) -> None:
    items = [obs(name, ordinal, status) for name, ordinal, status in observations]
    shuffled = list(items)
    rnd.shuffle(shuffled)
    a = seller_questions(analysis(vision=VisionOutput(condition=Condition.GOOD, equipment=tuple(items))))
    b = seller_questions(analysis(vision=VisionOutput(condition=Condition.GOOD, equipment=tuple(shuffled))))
    assert a.model_dump_json() == b.model_dump_json()
    ids = [q.id for q in a.questions]
    assert len(ids) == len(set(ids))
    assert len(a.questions) <= MAX_EQUIPMENT_QUESTIONS


def test_the_pure_function_is_idempotent_on_its_own_output_inputs() -> None:
    a = analysis(listing(admin_fee_pln=None), VisionOutput(condition=Condition.SHELL))
    once = seller_questions(a).model_dump_json()
    assert seller_questions(a).model_dump_json() == once


def test_the_contract_mirror_has_the_same_rules_and_the_same_wire_shape() -> None:
    engine_rules = {r.value for r in SellerQuestionRule}
    assert engine_rules == {r.value for r in SellerQuestionRuleName}
    gaps = listing(admin_fee_pln=None, floor=None, building_floors=None, build_year=None, floor_plan_urls=())
    dumped = seller_questions(analysis(gaps, VisionOutput(condition=Condition.UNKNOWN))).model_dump(
        mode="json"
    )
    parsed = WireBlock.model_validate(dumped)  # the API reads the stored block through this model
    assert parsed.model_dump(mode="json") == dumped


@pytest.mark.parametrize("bad", [{"id": "x"}, {"rule": "unknown_rule"}])
def test_wire_model_refuses_malformed_questions(bad: dict[str, object]) -> None:
    question = {
        "id": "sq-0123456789abcdef",
        "rule": "admin_fee_unknown",
        "text": "t",
        "reason": "r",
        "evidence": ["e"],
    } | bad
    with pytest.raises(ValueError, match=r"validation error"):
        WireBlock.model_validate({"version": 1, "questions": [question]})
