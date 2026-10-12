"""Auth request and response schemas (blueprint §2 Auth decision). Inbound models forbid unknown fields."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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
