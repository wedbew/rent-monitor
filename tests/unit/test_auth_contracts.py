from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from rm_contracts.auth import (
    PASSWORD_MAX_BYTES,
    PasswordChange,
    PasswordLogin,
    PasswordRegister,
    PasswordReset,
)
from rm_contracts.problems import ProblemCode

GOOD = "correct horse battery"


def _register(password: str) -> PasswordRegister:
    return PasswordRegister(email="a@b.pl", password=SecretStr(password))


def test_register_accepts_the_length_bounds() -> None:
    assert _register("x" * 10).password.get_secret_value() == "x" * 10
    assert len(_register("x" * 128).password.get_secret_value()) == 128


@pytest.mark.parametrize("password", ["x" * 9, "x" * 129])
def test_register_rejects_too_short_and_too_long(password: str) -> None:
    with pytest.raises(ValidationError):
        _register(password)


def test_byte_cap_is_enforced_for_multibyte_passwords() -> None:
    too_many = "€" * (PASSWORD_MAX_BYTES // 3 + 1)  # 3 bytes each, still under 128 characters
    assert len(too_many) <= 128
    with pytest.raises(ValidationError):
        _register(too_many)
    with pytest.raises(ValidationError):
        PasswordReset(token="t" * 32, password=SecretStr(too_many))
    with pytest.raises(ValidationError):
        PasswordChange(new_password=SecretStr(too_many))
    _register("ł" * 128)  # 2 bytes each: exactly 256 bytes, allowed


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PasswordLogin.model_validate({"email": "a@b.pl", "password": GOOD, "remember": True})


def test_login_does_not_apply_the_minimum_length() -> None:
    login = PasswordLogin(email="a@b.pl", password=SecretStr("short"))
    assert login.password.get_secret_value() == "short"


def test_password_is_not_in_repr_or_dump() -> None:
    model = _register(GOOD)
    assert GOOD not in repr(model)
    assert GOOD not in str(model.model_dump())
    assert GOOD not in model.model_dump_json()


def test_change_without_current_password_is_allowed_by_shape() -> None:
    assert PasswordChange(new_password=SecretStr(GOOD)).current_password is None


def test_new_problem_codes_are_listed_in_the_blueprint_error_table() -> None:
    blueprint = (Path(__file__).resolve().parents[2] / "docs" / "BLUEPRINT.md").read_text(encoding="utf-8")
    for code in (
        ProblemCode.INVALID_CREDENTIALS,
        ProblemCode.PASSWORD_POLICY_VIOLATION,
        ProblemCode.VERIFICATION_TOKEN_INVALID,
        ProblemCode.PASSWORD_RESET_TOKEN_INVALID,
        ProblemCode.CURRENT_PASSWORD_INVALID,
    ):
        assert f"| `{code.value}` |" in blueprint
