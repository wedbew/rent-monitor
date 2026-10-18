"""A NUL character in free text or an address is refused by the contract (422), never by Postgres (a 500).

Found by the Schemathesis run over the real API (#28).
"""

from uuid import UUID

import pytest
from pydantic import ValidationError
from rm_contracts.auth import EmailStart
from rm_contracts.me import BillingHoldClear, CreditAdjust, SavedPut

KEY = UUID(int=7)


@pytest.mark.parametrize("bad", ["a\x00b@example.test", "a\x01@example.test", "a\x7f@example.test"])
def test_control_characters_in_an_address_are_refused(bad: str) -> None:
    with pytest.raises(ValidationError):
        EmailStart(email=bad)


def test_an_ordinary_address_is_still_accepted() -> None:
    assert EmailStart(email="anna@example.test").email == "anna@example.test"


@pytest.mark.parametrize(
    "build",
    [
        lambda: SavedPut(note="a\x00b"),
        lambda: BillingHoldClear(note="five" + "\x00" + "six chars"),
        lambda: CreditAdjust(user_id="u\x00", delta=1, note="abc", idempotency_key=KEY),
        lambda: CreditAdjust(user_id="u", delta=1, note="a\x00c", idempotency_key=KEY),
    ],
)
def test_free_text_that_reaches_the_database_refuses_nul(build: object) -> None:
    with pytest.raises(ValidationError):
        build()  # type: ignore[operator]


def test_line_breaks_in_a_note_are_still_fine() -> None:
    assert SavedPut(note="line one\nline two").note == "line one\nline two"
