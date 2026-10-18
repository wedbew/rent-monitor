"""Descriptive statistics of original asking rents for the market summaries (RM-395, OTO-04).

Pure, Decimal only, deterministic. The worker and `rm_core.market_history` persist what this returns; they
never derive a figure themselves (invariant 4). Inputs are *asking* values; nothing here knows or blends
deed prices (invariant 2).
"""

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from deal_analyzer.money import engine_math, pln

_Q25 = Decimal("0.25")
_Q50 = Decimal("0.5")
_Q75 = Decimal("0.75")


class AskingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    count: int
    median: Decimal
    p25: Decimal
    p75: Decimal


def _quantile(ordered: Sequence[Decimal], q: Decimal) -> Decimal:
    pos = (len(ordered) - 1) * q
    lower = int(pos)
    if lower + 1 >= len(ordered):
        return ordered[-1]
    return ordered[lower] + (ordered[lower + 1] - ordered[lower]) * (pos - lower)


def summarise_asking(values: Sequence[Decimal]) -> AskingSummary | None:
    """Median and quartiles (linear interpolation), rounded to 0.01. None for an empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    with engine_math():
        return AskingSummary(
            count=len(ordered),
            median=pln(_quantile(ordered, _Q50)),
            p25=pln(_quantile(ordered, _Q25)),
            p75=pln(_quantile(ordered, _Q75)),
        )
