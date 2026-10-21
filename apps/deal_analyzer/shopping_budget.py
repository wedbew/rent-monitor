"""Interior shopping basket arithmetic: a known-item subtotal and what it leaves out (RM-448, RM-449).

The only place interior prices are added up (invariant 4: no money maths in the API handlers, the worker,
the LLM or the SPA). A separate figure from every investment-return number: it never feeds CAPEX, IRR or
yield. A line without a price is *excluded and counted*, never treated as zero; a catalogue line whose offer
has expired is excluded and counted as stale (its price is history, not a quote); a catalogue line whose
delivery cost is unknown is counted, never added as zero. The basket is `complete` only when every line is
priced and fresh and no delivery cost is unknown. That means "every listed line is priced", not "this is the
cost of the room": installation, missing items and checkout changes are not modelled.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class BasketLine:
    quantity: int
    unit_price_pln: Decimal | None
    stale: bool = False  # the observed offer has expired or can no longer be bought
    needs_delivery: bool = False  # a bought item (catalogue offer); the person's own items need none
    delivery_pln: Decimal | None = None  # one charge per line when known


@dataclass(frozen=True)
class BasketTotal:
    known_subtotal_pln: Decimal
    priced_lines: int
    unpriced_lines: int
    stale_lines: int
    delivery_known_pln: Decimal
    delivery_unknown_lines: int

    @property
    def complete(self) -> bool:
        return (
            self.unpriced_lines == 0
            and self.stale_lines == 0
            and self.delivery_unknown_lines == 0
            and self.priced_lines > 0
        )


def basket_total(lines: Iterable[BasketLine]) -> BasketTotal:
    subtotal = delivery = Decimal(0)
    priced = unpriced = stale = delivery_unknown = 0
    for line in lines:
        if line.quantity < 1:
            raise ValueError("quantity must be at least 1")
        if line.unit_price_pln is not None and line.unit_price_pln < 0:
            raise ValueError("price must not be negative")
        if line.delivery_pln is not None and line.delivery_pln < 0:
            raise ValueError("delivery must not be negative")
        if line.stale:
            stale += 1
            continue
        if line.unit_price_pln is None:
            unpriced += 1
            continue
        subtotal += line.unit_price_pln * line.quantity
        priced += 1
        if line.needs_delivery:
            if line.delivery_pln is None:
                delivery_unknown += 1
            else:
                delivery += line.delivery_pln
    return BasketTotal(
        subtotal.quantize(CENT, rounding=ROUND_HALF_UP),
        priced,
        unpriced,
        stale,
        delivery.quantize(CENT, rounding=ROUND_HALF_UP),
        delivery_unknown,
    )


def line_total(quantity: int, unit_price_pln: Decimal | None) -> Decimal | None:
    """quantity x price for one line, or None when the price is unknown (never zero)."""
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    if unit_price_pln is None:
        return None
    if unit_price_pln < 0:
        raise ValueError("price must not be negative")
    return (unit_price_pln * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
