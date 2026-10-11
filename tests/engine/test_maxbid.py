"""N-07: Max Bid, hurdle, grade and verdict (docs/ENGINE-SPEC.md rows 9-11)."""

from decimal import Decimal as D

import pytest
from deal_analyzer import (
    Assumptions,
    DealInputs,
    analyse_deal,
    compute_cash_flows,
    grade_for,
    hurdle_rate,
    solve_max_bid,
)
from deal_analyzer.maxbid import DEFAULT_PREMIUM, GRADE_CUTOFFS
from hypothesis import given, settings
from hypothesis import strategies as st

A = Assumptions()


def deal(price: int = 450_000, rent: int = 2_600, **kw: object) -> DealInputs:
    base: dict[str, object] = {
        "price_pln": D(price),
        "area_m2": D(50),
        "monthly_rent_pln": D(rent),
        "admin_fee_monthly_pln": D(500),
        "capex_pln": D(20_000),
        "assumptions": A,
    }
    return DealInputs(**{**base, **kw})  # pyright: ignore[reportArgumentType]


HURDLE = hurdle_rate(D("0.05"))  # 5 % risk-free + 2 % default premium = 7 %


def test_the_hurdle_is_risk_free_plus_a_user_changeable_premium() -> None:
    assert D("0.02") == DEFAULT_PREMIUM
    assert hurdle_rate(D("0.055")) == D("0.075")
    assert hurdle_rate(D("0.055"), D("0.03")) == D("0.085")


# ---- the solver ----
def test_the_irr_at_the_max_bid_equals_the_hurdle() -> None:
    inp = deal()
    max_bid, bounded = solve_max_bid(inp, HURDLE)
    assert max_bid is not None
    assert bounded
    at_bid = compute_cash_flows(inp.model_copy(update={"price_pln": max_bid})).returns.irr
    just_above = compute_cash_flows(inp.model_copy(update={"price_pln": max_bid + D(2_000)})).returns.irr
    assert at_bid is not None
    assert just_above is not None
    assert abs(at_bid - HURDLE) <= D("0.0002")  # within the 4-decimal rounding of the reported IRR
    assert just_above < HURDLE  # paying more than the Max Bid misses the hurdle


@settings(max_examples=40, deadline=None)
@given(rent=st.integers(1_800, 6_000), capex=st.integers(0, 100_000), price=st.integers(200_000, 900_000))
def test_max_bid_is_the_edge_between_meeting_and_missing_the_hurdle(
    rent: int, capex: int, price: int
) -> None:
    inp = deal(price=price, rent=rent, capex_pln=D(capex))
    max_bid, _ = solve_max_bid(inp, HURDLE)
    if max_bid is None:
        return
    below = compute_cash_flows(inp.model_copy(update={"price_pln": max_bid - D(5)})).returns.irr
    above = compute_cash_flows(inp.model_copy(update={"price_pln": max_bid + D(5)})).returns.irr
    assert below is not None
    assert above is not None
    assert below >= HURDLE - D("0.0001")
    assert above <= HURDLE + D("0.0001")


@settings(max_examples=40, deadline=None)
@given(rent=st.integers(1_800, 6_000), bump=st.integers(50, 1_500))
def test_a_higher_rent_never_lowers_the_max_bid(rent: int, bump: int) -> None:
    low, _ = solve_max_bid(deal(rent=rent), HURDLE)
    high, _ = solve_max_bid(deal(rent=rent + bump), HURDLE)
    assert low is not None
    assert high is not None
    assert high >= low


def test_capex_lowers_the_max_bid_and_the_exit_anchor_decides_by_how_much() -> None:
    # Spec default: the exit value follows the purchase price, so a lower bid also lowers the sale
    # value and the Max Bid
    # has to fall by MORE than the CAPEX (about 2 PLN per PLN here).
    base, _ = solve_max_bid(deal(capex_pln=D(0)), HURDLE)
    renovated, _ = solve_max_bid(deal(capex_pln=D(50_000)), HURDLE)
    assert base is not None
    assert renovated is not None
    assert base - renovated > D(50_000)
    # With a market-value anchor the sale value does not depend on the bid, so CAPEX comes off the
    # price about 1:1.
    base_m, _ = solve_max_bid(deal(capex_pln=D(0), market_value_pln=D(450_000)), HURDLE)
    renovated_m, _ = solve_max_bid(deal(capex_pln=D(50_000), market_value_pln=D(450_000)), HURDLE)
    assert base_m is not None
    assert renovated_m is not None
    assert D(40_000) < base_m - renovated_m < D(55_000)


def test_a_higher_hurdle_lowers_the_max_bid() -> None:
    easy, _ = solve_max_bid(deal(), D("0.05"))
    hard, _ = solve_max_bid(deal(), D("0.09"))
    assert easy is not None
    assert hard is not None
    assert hard < easy


def test_max_bid_is_not_capped_at_the_asking_price() -> None:
    result = analyse_deal(
        deal(price=250_000, rent=3_500), HURDLE
    )  # a bargain: the hurdle is reachable far above asking
    assert result.max_bid_pln is not None
    assert result.max_bid_pln > result.asking_price_pln
    assert result.discount_to_asking is not None
    assert result.discount_to_asking > 0
    assert result.verdict == "buy_at_asking"  # the label caps, the number does not


def test_when_even_ten_times_the_asking_price_works_the_result_says_unbounded() -> None:
    inp = deal(price=100_000, rent=20_000, capex_pln=D(0))
    max_bid, bounded = solve_max_bid(inp, D("0.01"))
    assert max_bid == D(1_000_000)
    assert bounded is False
    assert analyse_deal(inp, D("0.01")).max_bid_bounded is False


def test_when_no_price_can_reach_the_hurdle_there_is_no_max_bid() -> None:
    inp = deal(rent=0)
    max_bid, bounded = solve_max_bid(inp, D("0.30"))
    assert max_bid is None
    assert bounded
    result = analyse_deal(inp, D("0.30"))
    assert result.max_bid_pln is None
    assert result.discount_to_asking is None
    assert result.verdict == "pass"


# ---- sensitivity ----
def test_appreciation_sensitivity_brackets_the_max_bid() -> None:
    r = analyse_deal(deal(), HURDLE)
    assert r.max_bid_if_appreciation_minus_1pp_pln is not None
    assert r.max_bid_if_appreciation_plus_1pp_pln is not None
    assert r.max_bid_pln is not None
    assert r.max_bid_if_appreciation_minus_1pp_pln < r.max_bid_pln < r.max_bid_if_appreciation_plus_1pp_pln


# ---- grades ----
@pytest.mark.parametrize(
    ("spread", "grade"),
    [
        ("0.0300", "A"),
        ("0.0299", "B"),
        ("0.0150", "B"),
        ("0.0149", "C"),
        ("0.0000", "C"),
        ("-0.0001", "D"),
        ("-0.0150", "D"),
        ("-0.0151", "E"),
        ("-0.5000", "E"),
        ("0.2", "A"),
    ],
)
def test_grade_cutoffs_are_exact(spread: str, grade: str) -> None:
    assert grade_for(HURDLE + D(spread), HURDLE) == grade


def test_grade_n_means_insufficient_data() -> None:
    assert grade_for(None, HURDLE) == "N"
    assert grade_for(HURDLE + D("0.1"), HURDLE, insufficient_data=True) == "N"
    result = analyse_deal(deal(), HURDLE, insufficient_data=True)
    assert result.grade == "N"
    assert result.verdict == "insufficient_data"


def test_the_cutoffs_are_the_approved_spec_values() -> None:
    assert [(g, str(c)) for g, c in GRADE_CUTOFFS] == [
        ("A", "0.03"),
        ("B", "0.015"),
        ("C", "0"),
        ("D", "-0.015"),
    ]


# ---- verdicts ----
def test_verdict_labels() -> None:
    assert analyse_deal(deal(price=250_000, rent=3_500), HURDLE).verdict == "buy_at_asking"
    near = analyse_deal(deal(), HURDLE)
    assert near.max_bid_pln is not None
    assert near.max_bid_pln < near.asking_price_pln
    assert near.verdict in {"negotiate", "pass"}
    assert analyse_deal(deal(price=900_000, rent=2_000), HURDLE).verdict == "pass"


# ---- invariant 4 and hygiene ----
def test_the_analysis_is_deterministic_and_float_free() -> None:
    first = analyse_deal(deal(), HURDLE)
    second = analyse_deal(deal(), HURDLE)
    assert first.model_dump_json() == second.model_dump_json()
    assert not [v for v in first.model_dump().values() if isinstance(v, float)]


def test_money_is_rounded_for_output() -> None:
    r = analyse_deal(deal(), HURDLE)
    assert r.max_bid_pln == r.max_bid_pln.quantize(D("0.01")) if r.max_bid_pln is not None else True
    assert r.hurdle == D("0.0700")
