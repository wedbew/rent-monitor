"""Request schemas of the email/password routes (docs/PASSWORD-AUTH-SPEC.md sections 1 and 2)."""

import pytest
from pydantic import ValidationError
from rm_contracts.auth import (
    PASSWORD_MAX_CHARS,
    PASSWORD_MIN_CHARS,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetRequest,
)
from rm_contracts.problems import ProblemCode

GOOD = "correct horse battery"


def test_a_reasonable_passphrase_is_accepted_with_no_composition_rules() -> None:
    assert RegisterRequest(email="a@example.pl", password=GOOD).password == GOOD
    assert RegisterRequest(
        email="a@example.pl", password="x" * PASSWORD_MIN_CHARS
    )  # no digit or symbol needed


@pytest.mark.parametrize(
    "password", ["short", "x" * (PASSWORD_MIN_CHARS - 1), "x" * (PASSWORD_MAX_CHARS + 1)]
)
def test_password_length_is_bounded_on_both_ends(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.pl", password=password)


def test_the_byte_bound_limits_hashing_work_for_multibyte_text() -> None:
    wide = "€" * 100  # 100 characters, 300 bytes
    assert len(wide) <= PASSWORD_MAX_CHARS
    with pytest.raises(ValidationError):
        ResetRequest(token="t" * 32, password=wide)


def test_validation_errors_never_echo_the_password() -> None:
    with pytest.raises(ValidationError) as caught:
        RegisterRequest(email="a@example.pl", password="secretvalue" * 20)
    assert "secretvalue" not in str(caught.value)


def test_login_accepts_any_stored_length_but_not_an_empty_or_huge_password() -> None:
    assert LoginRequest(email="a@example.pl", password="x")  # older, shorter passwords must still be tried
    with pytest.raises(ValidationError):
        LoginRequest(email="a@example.pl", password="")
    with pytest.raises(ValidationError):
        LoginRequest(email="a@example.pl", password="x" * (PASSWORD_MAX_CHARS + 1))


def test_unknown_fields_and_malformed_addresses_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest.model_validate({"email": "a@example.pl", "password": GOOD, "role": "admin"})
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-address", password=GOOD)
    with pytest.raises(ValidationError):
        ChangePasswordRequest.model_validate({"current_password": GOOD, "new_password": GOOD, "x": 1})


def test_tokens_must_look_like_our_tokens() -> None:
    with pytest.raises(ValidationError):
        ResetRequest(token="has spaces and is long enough!!", password=GOOD)


def test_the_new_problem_codes_exist_and_are_stable() -> None:
    assert {
        c.value
        for c in (ProblemCode.INVALID_CREDENTIALS, ProblemCode.WEAK_PASSWORD, ProblemCode.AUTH_TOKEN_INVALID)
    } == {
        "INVALID_CREDENTIALS",
        "WEAK_PASSWORD",
        "AUTH_TOKEN_INVALID",
    }
