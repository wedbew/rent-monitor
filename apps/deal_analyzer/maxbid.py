"""Max Bid, hurdle, grade and verdict (docs/ENGINE-SPEC.md rows 9-11).

Max Bid is the highest price at which the unlevered 10-year IRR after tax, with all purchase costs and
CAPEX included,
still reaches the hurdle. IRR falls as price rises, so the solver is a bisection on price:
deterministic and Decimal-only.
It is reported UNCAPPED (it may exceed the asking price); only the verdict label caps at "buy at asking".
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from deal_analyzer.assumptions import Assumptions
from deal_analyzer.cashflow import DealInputs, compute_flows, compute_with_exact_irr, npv
from deal_analyzer.money import ONE, engine_math, pln, rate

DEFAULT_PREMIUM = Decimal(
    "0.02"
)  # over the risk-free rate; the user may change it (3 % is the conservative option)
PRICE_TOLERANCE = Decimal("0.5")  # PLN
MAX_ITERATIONS = 80
PRICE_CEILING_FACTOR = Decimal(10)  # search up to 10x the asking price
SENSITIVITY_STEP = Decimal("0.01")  # +/- 1 percentage point of yearly appreciation
NEGOTIATE_FLOOR = Decimal(
    "0.85"
)  # PROPOSED: below 85 % of asking, the verdict is "pass" (not in the approved spec)

Grade = Literal["A", "B", "C", "D", "E", "N"]
Verdict = Literal["buy_at_asking", "negotiate", "pass", "insufficient_data"]
# IRR minus hurdle, in percentage points as fractions: A >= +3.0, B >= +1.5, C >= 0, D >= -1.5, else E
# (spec row 11).
GRADE_CUTOFFS: tuple[tuple[Grade, Decimal], ...] = (
    ("A", Decimal("0.03")),
    ("B", Decimal("0.015")),
    ("C", Decimal(0)),
    ("D", Decimal("-0.015")),
)


def hurdle_rate(risk_free: Decimal, premium: Decimal = DEFAULT_PREMIUM) -> Decimal:
    with engine_math():
        return risk_free + premium


def _meets_hurdle(inp: DealInputs, price: Decimal, hurdle: Decimal) -> bool:
    """IRR >= hurdle exactly when the NPV at the hurdle rate is not negative.

    Used instead of solving the IRR: at tiny prices the IRR is astronomically high and outside any
    search range,
    but the NPV test is exact and monotone for conventional cash flows (outflow first, inflows after).
    """
    flows = compute_flows(inp.model_copy(update={"price_pln": price}))
    return npv(hurdle, flows) >= 0


def solve_max_bid(inp: DealInputs, hurdle: Decimal) -> tuple[Decimal | None, bool]:
    """(max price, bounded). None if even a token price misses the hurdle; unbounded if the ceiling
    meets it."""
    with engine_math():
        low, high = Decimal(1), inp.price_pln * PRICE_CEILING_FACTOR
        if not _meets_hurdle(inp, low, hurdle):
            return None, True
        if _meets_hurdle(inp, high, hurdle):
            return high, False
        for _ in range(MAX_ITERATIONS):
            if high - low <= PRICE_TOLERANCE:
                break
            mid = (low + high) / 2
            if _meets_hurdle(inp, mid, hurdle):
                low = mid
            else:
                high = mid
        return low, True


def grade_for(irr: Decimal | None, hurdle: Decimal, *, insufficient_data: bool = False) -> Grade:
    if insufficient_data or irr is None:
        return "N"
    spread = irr - hurdle
    for letter, cutoff in GRADE_CUTOFFS:
        if spread >= cutoff:
            return letter
    return "E"


class MaxBidResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    hurdle: Decimal
    asking_price_pln: Decimal
    max_bid_pln: Decimal | None  # uncapped; None when no price reaches the hurdle
    max_bid_bounded: bool  # False when even 10x the asking price reaches the hurdle
    discount_to_asking: Decimal | None  # max bid / asking - 1 (negative: the deal needs a lower price)
    irr_at_asking: Decimal | None
    max_bid_if_appreciation_minus_1pp_pln: Decimal | None
    max_bid_if_appreciation_plus_1pp_pln: Decimal | None
    grade: Grade
    verdict: Verdict


def _verdict(asking: Decimal, max_bid: Decimal | None, grade: Grade) -> Verdict:
    if grade == "N":
        return "insufficient_data"
    if max_bid is None:
        return "pass"
    if asking <= max_bid:
        return "buy_at_asking"  # the only place a cap applies: the label, never the number
    return "negotiate" if max_bid >= asking * NEGOTIATE_FLOOR else "pass"


def analyse_deal(inp: DealInputs, hurdle: Decimal, *, insufficient_data: bool = False) -> MaxBidResult:
    asking = inp.price_pln
    irr_asking = compute_with_exact_irr(inp)[1]
    max_bid, bounded = solve_max_bid(inp, hurdle)

    def shifted(step: Decimal) -> Decimal | None:
        a: Assumptions = inp.assumptions
        moved = inp.model_copy(
            update={"assumptions": a.model_copy(update={"appreciation_rate": a.appreciation_rate + step})}
        )
        value, _ = solve_max_bid(moved, hurdle)
        return pln(value) if value is not None else None

    grade = grade_for(irr_asking, hurdle, insufficient_data=insufficient_data)
    with engine_math():
        discount = rate(max_bid / asking - ONE) if max_bid is not None else None
    return MaxBidResult(
        hurdle=rate(hurdle),
        asking_price_pln=pln(asking),
        max_bid_pln=pln(max_bid) if max_bid is not None else None,
        max_bid_bounded=bounded,
        discount_to_asking=discount,
        irr_at_asking=rate(irr_asking) if irr_asking is not None else None,
        max_bid_if_appreciation_minus_1pp_pln=shifted(-SENSITIVITY_STEP),
        max_bid_if_appreciation_plus_1pp_pln=shifted(SENSITIVITY_STEP),
        grade=grade,
        verdict=_verdict(asking, max_bid, grade),
    )
