"""Auth request and response schemas (blueprint §2 Auth decision). Inbound models forbid unknown fields."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator

# Small and strict on purpose: one `@`, no whitespace or quoting, a dotted domain. Delivery is the real check.
_LOCAL = r"[^@\s<>\"',;()\[\]\\]{1,64}"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
EMAIL_PATTERN = rf"^{_LOCAL}@{_LABEL}(?:\.{_LABEL})+$"
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254, pattern=EMAIL_PATTERN)]


# Password shape limits (ADR 0013). Length counts characters; the byte cap bounds Argon2 input. The denylist
# and "contains your email" checks are server-side policy after NFKC (PASSWORD_POLICY_VIOLATION).
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
PASSWORD_MAX_BYTES = 256
B64URL_PATTERN = r"^[A-Za-z0-9_-]+$"


def _bounded_password(value: SecretStr | None) -> SecretStr | None:
    if value is not None and len(value.get_secret_value().encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"password exceeds {PASSWORD_MAX_BYTES} bytes")
    return value


class GoogleCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=20, max_length=4096)


class EmailStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email


class EmailVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class MeOut(BaseModel):
    """GDPR[personal-data]: email, name, avatar_url returned to the owner of the account only."""

    id: str
    email: str
    name: str | None
    avatar_url: str | None
    role: str
    email_verified: bool


class SessionOut(BaseModel):
    """One signed-in browser. GDPR[personal-data]: user_agent and ip belong to the account owner."""

    id: int
    current: bool
    created_hint: datetime = Field(description="last_seen_at; sessions carry no separate creation time")
    expires_at: datetime
    user_agent: str | None
    ip: str | None


class AccountDelete(BaseModel):
    """Account erasure must be confirmed by typing the account's own address (GDPR[erasure])."""

    model_config = ConfigDict(extra="forbid")
    confirm_email: Email


# --- Email + password (ADR 0013). GDPR[personal-data]: never logged or echoed; SecretStr hides it ---


class PasswordRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email
    password: SecretStr = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    _bytes = field_validator("password")(_bounded_password)


class PasswordVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128, pattern=B64URL_PATTERN)


class PasswordResend(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email


class PasswordLogin(BaseModel):
    """Policy applies when setting a password, not when checking one: only emptiness and the caps."""

    model_config = ConfigDict(extra="forbid")
    email: Email
    password: SecretStr = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    _bytes = field_validator("password")(_bounded_password)


class PasswordForgot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128, pattern=B64URL_PATTERN)
    password: SecretStr = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    _bytes = field_validator("password")(_bounded_password)


class PasswordChange(BaseModel):
    """`current_password` is omitted only by a user who has no password yet (fresh session required)."""

    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr | None = Field(default=None, min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: SecretStr = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    _bytes = field_validator("new_password")(_bounded_password)
