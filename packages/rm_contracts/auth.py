"""Auth request and response schemas (blueprint §2 Auth decision). Inbound models forbid unknown fields."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

# Small and strict on purpose: one `@`, no whitespace or quoting, a dotted domain. Delivery is the real check.
_LOCAL = r"[^@\s<>\"',;()\[\]\\]{1,64}"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
EMAIL_PATTERN = rf"^{_LOCAL}@{_LABEL}(?:\.{_LABEL})+$"
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=254, pattern=EMAIL_PATTERN)]


class GoogleCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=20, max_length=4096)


class EmailStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email


class EmailVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


# Password bounds (docs/PASSWORD-AUTH-SPEC.md section 2). NFKC normalisation, the blocklist and the "contains
# your address" rule run in the route, because they need the account's address and the bundled list.
PASSWORD_MIN_CHARS = 10
PASSWORD_MAX_CHARS = 128
PASSWORD_MAX_BYTES = 256
URLSAFE_PATTERN = r"^[A-Za-z0-9_-]+$"


def _bounded_password(value: str) -> str:
    """Hard upper bound on hashing work; the policy itself is reported as `WEAK_PASSWORD` by the route."""
    if len(value.encode()) > PASSWORD_MAX_BYTES:
        msg = "password is too long"
        raise ValueError(msg)
    return value


NewPassword = Annotated[
    str,
    Field(min_length=PASSWORD_MIN_CHARS, max_length=PASSWORD_MAX_CHARS),
    AfterValidator(_bounded_password),
]
LoginPassword = Annotated[
    str, Field(min_length=1, max_length=PASSWORD_MAX_CHARS), AfterValidator(_bounded_password)
]


class RegisterRequest(BaseModel):
    """GDPR[personal-data]: the address and a password that is hashed before it is stored."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: Email
    password: NewPassword


class RegisterVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128, pattern=URLSAFE_PATTERN)


class ResendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: Email
    password: LoginPassword


class ForgotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    token: str = Field(min_length=20, max_length=128, pattern=URLSAFE_PATTERN)
    password: NewPassword


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    current_password: LoginPassword
    new_password: NewPassword


class Accepted(BaseModel):
    """The body of every non-enumerating 202: identical whatever the address is."""

    model_config = ConfigDict(extra="forbid")


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
