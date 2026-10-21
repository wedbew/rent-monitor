"""Interior basket maths: exact decimals, unknown prices excluded and counted, never zero (RM-448)."""

from decimal import Decimal

import pytest
from deal_analyzer.shopping_budget import BasketLine, basket_total
from hypothesis import given
from hypothesis import strategies as st


def test_subtotal_counts_quantity_and_excludes_unpriced_lines() -> None:
    total = basket_total(
        [BasketLine(2, Decimal("199.99")), BasketLine(1, None), BasketLine(3, Decimal("10.10"))]
    )
    assert total.known_subtotal_pln == Decimal("430.28")
    assert (total.priced_lines, total.unpriced_lines) == (2, 1)
    assert not total.complete


def test_complete_only_when_every_line_is_priced() -> None:
    assert basket_total([BasketLine(1, Decimal("5"))]).complete
    assert not basket_total([]).complete  # an empty basket is not a total
    assert not basket_total([BasketLine(1, None)]).complete


def test_zero_price_is_a_price_but_missing_is_not() -> None:
    free = basket_total([BasketLine(1, Decimal("0"))])
    assert free.priced_lines == 1
    assert free.complete
    assert basket_total([BasketLine(1, None)]).priced_lines == 0


@pytest.mark.parametrize("bad", [BasketLine(0, Decimal("1")), BasketLine(1, Decimal("-1"))])
def test_invalid_lines_raise(bad: BasketLine) -> None:
    with pytest.raises(ValueError, match="must"):
        basket_total([bad])


@given(
    st.lists(
        st.tuples(
            st.integers(1, 99), st.one_of(st.none(), st.decimals(0, 100000, places=2, allow_nan=False))
        ),
        max_size=30,
    )
)
def test_order_does_not_matter_and_unpriced_never_contribute(rows: list[tuple[int, Decimal | None]]) -> None:
    lines = [BasketLine(q, p) for q, p in rows]
    forward = basket_total(lines)
    assert forward == basket_total(list(reversed(lines)))
    assert forward.priced_lines + forward.unpriced_lines == len(lines)
    assert forward.known_subtotal_pln == sum(
        (Decimal(q) * p for q, p in rows if p is not None), Decimal(0)
    ).quantize(Decimal("0.01"))


def test_stale_lines_are_excluded_and_counted_never_priced() -> None:
    total = basket_total([BasketLine(1, Decimal("100"), stale=True), BasketLine(2, Decimal("10"))])
    assert (total.known_subtotal_pln, total.priced_lines, total.stale_lines) == (Decimal("20.00"), 1, 1)
    assert not total.complete


def test_unknown_delivery_is_counted_not_zero_and_blocks_completeness() -> None:
    total = basket_total(
        [
            BasketLine(1, Decimal("100"), needs_delivery=True, delivery_pln=Decimal("19.90")),
            BasketLine(1, Decimal("50"), needs_delivery=True, delivery_pln=None),
            BasketLine(1, Decimal("5")),  # the person's own item: no delivery
        ]
    )
    assert total.delivery_known_pln == Decimal("19.90")
    assert total.delivery_unknown_lines == 1
    assert not total.complete
    done = basket_total([BasketLine(1, Decimal("100"), needs_delivery=True, delivery_pln=Decimal("0"))])
    assert done.complete  # a known free delivery is a fact, unlike a missing one
    assert done.delivery_known_pln == Decimal("0.00")


def test_a_stale_line_does_not_add_its_delivery() -> None:
    total = basket_total(
        [BasketLine(1, Decimal("100"), stale=True, needs_delivery=True, delivery_pln=Decimal("30"))]
    )
    assert total.delivery_known_pln == Decimal("0.00")
