"""Schemas for `/api/me`, `/api/saved` and `/api/admin/*` (blueprint §2 Route map).

Inbound models forbid unknown fields.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from rm_contracts.auth import MeOut

OtodomId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9]{4,16}$")]
FlagKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
PlanName = Literal["free", "pro"]


class PeriodOut(BaseModel):
    kind: str
    period_end: datetime
    allowance: int
    used: int
    remaining: int


class PlanOut(BaseModel):
    code: PlanName
    is_pro: bool
    subscription_status: str | None
    grace_until: datetime | None
    period: PeriodOut | None


class UpstreamOut(BaseModel):
    """Shown as "Otodom is rate-limiting us, try in N minutes" instead of a spinner (blueprint §2)."""

    otodom_breaker_open: bool
    retry_after_s: int
    reason: str | None


class MeDetailOut(MeOut):
    plan: PlanOut
    credit_balance: int
    flags: dict[str, bool]
    upstream: UpstreamOut


class SavedPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=2000)


class SavedOut(BaseModel):
    """GDPR[personal-data]: `note` is free text written by the user."""

    otodom_id: str
    note: str | None
    latest_audit_id: UUID | None
    created_at: datetime


class FlagOut(BaseModel):
    key: str
    description: str
    enabled_default: bool
    min_plan: str | None
    rollout_pct: int
    overrides: int


class FlagUpdate(BaseModel):
    """Only the fields present are changed; flags themselves are created by the seed, not through the API."""

    model_config = ConfigDict(extra="forbid")
    enabled_default: bool | None = None
    rollout_pct: int | None = Field(default=None, ge=0, le=100)
    min_plan: PlanName | None = None
    clear_min_plan: bool = False


class OverridePut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    reason: str = Field(min_length=3, max_length=200)
    expires_at: datetime | None = None


class OverrideOut(BaseModel):
    flag_key: str
    user_id: str
    enabled: bool
    reason: str
    expires_at: datetime | None
    created_by: str


class CreditAdjust(BaseModel):
    """`idempotency_key` is chosen by the caller; repeating it never adjusts twice."""

    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=64)
    delta: int = Field(ge=-1000, le=1000)
    note: str = Field(min_length=3, max_length=200)
    idempotency_key: UUID


class CreditAdjustOut(BaseModel):
    applied: bool
    balance: int


class JobOut(BaseModel):
    """Metadata only: job arguments are never returned (they can hold addresses and login tokens, L-011)."""

    id: int
    queue: str
    task: str
    status: str
    attempts: int
    scheduled_at: datetime | None


class JobsOut(BaseModel):
    counts: dict[str, dict[str, int]]
    recent: list[JobOut]
