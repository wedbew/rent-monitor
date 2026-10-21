"""Architekt wnetrz: a generation operation, its progress and result (RM-450, #284).

One operation turns one saved revision (brief, own items, picked products, the room photo) into an
illustrative picture. The result is a visualisation, never proof of scale, fit or that a pictured object is
the exact product: the product board stays the dependable selection. Money is an exact decimal string.

LEGAL[images]: the room photo and permitted reference images go to an image model (RM-450)
GDPR[processor]: OpenRouter and its model provider process those images (RM-450)
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rm_contracts.interior import MediaRef

PROMPT_VERSION = "interior-render-v1"


class GenerationState(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class GenerationError(StrEnum):
    """Stable reasons a generation ended `failed`; the SPA words them."""

    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"  # the shared AI test budget has no room: nothing was sent
    NO_SOURCE_PHOTO = "NO_SOURCE_PHOTO"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"  # the model refused the request: not billed
    PROVIDER_UNAVAILABLE = (
        "PROVIDER_UNAVAILABLE"  # could not reach the provider: nothing was sent, not billed
    )
    AMBIGUOUS = "AMBIGUOUS"  # sent, no answer: the estimate stays charged against the budget, no auto-retry
    TIMEOUT = "TIMEOUT"
    OUTPUT_REJECTED = "OUTPUT_REJECTED"  # the answer was not a usable image
    STORAGE_FAILED = "STORAGE_FAILED"  # generated but could not be stored: cost was incurred
    INTERNAL = "INTERNAL"


class GenerationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision_id: UUID


class GenerationOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    generation_id: UUID
    revision_id: UUID
    state: GenerationState
    error_code: GenerationError | None
    model: str
    prompt_version: str
    references_used: int = Field(description="photos sent to the model besides the room photo")
    references_skipped: int = Field(
        description="picked or own items whose photo was not sent (no photo or no right)"
    )
    output: MediaRef | None
    cost_usd: str | None = Field(description="provider-reported or, when estimated, the reserved amount")
    cost_estimated: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
