"""The pure rules that turn Paddle's adjustments into an effect on a purchase (PADDLE-INTEGRATION.md §6)."""

import pytest
from rm_core.billing_events import decide_effect, net_reversed
from rm_core.paddle import Adjustment

AMOUNT = 4000


def adj(action: str, status: str, total: int | None, ident: str = "a") -> Adjustment:
    return Adjustment(
        id=ident,
        transaction_id="txn",
        action=action,
        type="full",
        status=status,
        currency_code="PLN",
        total_minor=total,
    )


def test_only_approved_cash_reversals_count_and_reversals_undo_them() -> None:
    assert net_reversed([adj("refund", "approved", 4000)]) == (4000, False, False)
    assert net_reversed([adj("refund", "pending_approval", 4000)]) == (
        0,
        True,
        False,
    )  # a request is not a refund
    assert net_reversed([adj("refund", "rejected", 4000)]) == (0, False, False)
    assert net_reversed([adj("credit", "approved", 4000)]) == (
        0,
        False,
        False,
    )  # a credit/tax correction removes nothing
    assert net_reversed(
        [adj("chargeback", "approved", 4000), adj("chargeback_reverse", "approved", 4000, "b")]
    ) == (
        0,
        False,
        False,
    )
    assert net_reversed([adj("chargeback_warning", "approved", None)]) == (0, False, True)


def test_overlapping_refund_and_chargeback_are_one_reversal_not_two() -> None:
    both = [adj("refund", "approved", 4000), adj("chargeback", "approved", 4000, "b")]
    net, _, _ = net_reversed(both)
    assert net >= AMOUNT
    assert (
        decide_effect("granted", None, AMOUNT, net, is_open=False, warned=False, has_owner=True) == "reverse"
    )
    # asked again after it was applied: nothing more happens, so units cannot be revoked twice
    assert decide_effect("refunded", None, AMOUNT, net, is_open=False, warned=False, has_owner=True) == "none"


CASES = [
    # state, error code, net reversed, open request, warning, has owner, expected effect
    ("created", None, 4000, False, False, True, "none"),  # not granted: the grant itself checks adjustments
    ("granted", None, 4000, False, False, True, "reverse"),
    ("granted", None, 4000, False, False, False, "freeze:PARTIAL_REVERSAL"),  # no owner to take units from
    ("granted", None, 1000, False, False, True, "freeze:PARTIAL_REVERSAL"),  # partial: no unit maths
    ("granted", None, 0, True, False, True, "freeze:REFUND_PENDING"),
    ("granted", None, 0, False, True, True, "freeze:CHARGEBACK_WARNING"),
    ("refunded", None, 0, False, False, True, "restore"),  # the chargeback was reversed
    ("refunded", None, 1500, False, False, True, "none"),  # only part of it was undone: wait for zero
    ("review", "PARTIAL_REVERSAL", 0, False, False, True, "clear"),
    (
        "review",
        "WRONG_TOTAL",
        0,
        False,
        False,
        True,
        "none",
    ),  # a review for another reason is not ours to clear
    ("granted", None, 0, False, False, True, "none"),
]


@pytest.mark.parametrize("case", CASES, ids=[f"{c[0]}-{c[2]}-{c[6]}" for c in CASES])
def test_the_effect_follows_the_net_state(case: tuple[str, str | None, int, bool, bool, bool, str]) -> None:
    state, code, net, is_open, warned, has_owner, expected = case
    got = decide_effect(state, code, AMOUNT, net, is_open=is_open, warned=warned, has_owner=has_owner)
    assert got == expected
