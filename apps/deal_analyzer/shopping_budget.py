"""Interior shopping basket arithmetic: a known-item subtotal and what it leaves out (RM-448).

The only place interior prices are added up (invariant 4: no money maths in the API handlers, the worker, the
LLM or the SPA). This is a separate figure from every investment-return number: it never feeds CAPEX, IRR or
yield. An item without a price is *excluded and counted*, never treated as zero, so the basket is `complete`
only when every line has a price. Delivery, installation and missing items are not modelled here at all, so
`complete` means "every listed line is priced", not "this is the cost of the room".
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class BasketLine:
    quantity: int
    unit_price_pln: Decimal | None


@dataclass(frozen=True)
class BasketTotal:
    known_subtotal_pln: Decimal
    priced_lines: int
    unpriced_lines: int

    @property
    def complete(self) -> bool:
        return self.unpriced_lines == 0 and self.priced_lines > 0


def basket_total(lines: Iterable[BasketLine]) -> BasketTotal:
    subtotal = Decimal(0)
    priced = unpriced = 0
    for line in lines:
        if line.quantity < 1:
            raise ValueError("quantity must be at least 1")
        if line.unit_price_pln is None:
            unpriced += 1
            continue
        if line.unit_price_pln < 0:
            raise ValueError("price must not be negative")
        subtotal += line.unit_price_pln * line.quantity
        priced += 1
    return BasketTotal(subtotal.quantize(CENT, rounding=ROUND_HALF_UP), priced, unpriced)
