"""Audit media manifest: stable identity for every photo and floor plan of one audit (RM-376, G-01a).

Metadata only. No binary storage yet (guide section 7 Stage B is a separate slice). Inbound models forbid
unknown fields; the manifest validates cardinality (at most 25 photos and 2 plans) and identity (unique media
ids and ordinals). Failure and expiry are explicit states, never missing rows.

LEGAL[images]: identifies listing photos and floor plans downloaded for vision analysis (RM-376)
LEGAL[republication]: the manifest echoes third-party image metadata to the tenant who requested it (RM-376)
GDPR[retention]: rows follow the audit; deleted with it and with the account (cascade) (RM-376)
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MEDIA_SCHEMA_VERSION = 1
MAX_PHOTOS = 25  # engine limit per audit (CONTEXT section 7)
MAX_PLANS = 2
MAX_ITEMS = MAX_PHOTOS + MAX_PLANS
MAX_DIMENSION = 20_000  # pixels; a bound on stored metadata, not a processing limit

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class MediaKind(StrEnum):
    photo = "photo"
    plan = "plan"


class MediaSource(StrEnum):
    url = "url"  # fetched from the listing page
    manual = "manual"  # manual-analysis source supplied by the person
    upload = "upload"


class MediaState(StrEnum):
    """Storage state of the prepared image. `expired` is derived on read from `expires_at`."""

    pending = "pending"
    stored = "stored"
    rejected = "rejected"  # refused by a safeguard (size, type, pixels)
    failed = "failed"  # download or decode failed
    expired = "expired"


class AnalysisState(StrEnum):
    """Vision or OCR outcome, kept apart from storage: a stored photo stays viewable when analysis fails."""

    not_requested = "not_requested"
    classified = "classified"
    failed = "failed"


class MediaMime(StrEnum):
    jpeg = "image/jpeg"
    png = "image/png"
    webp = "image/webp"


class MediaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: UUID = Field(default_factory=uuid4, description="Opaque and stable; vision output cites it")
    ordinal: Annotated[int, Field(ge=0, le=MAX_ITEMS - 1)]
    kind: MediaKind
    source_type: MediaSource
    state: MediaState = MediaState.pending
    analysis_state: AnalysisState = AnalysisState.not_requested
    content_digest: Sha256Hex | None = Field(default=None, description="SHA-256 of the prepared bytes")
    width: Annotated[int, Field(ge=1, le=MAX_DIMENSION)] | None = None
    height: Annotated[int, Field(ge=1, le=MAX_DIMENSION)] | None = None
    mime: MediaMime | None = None
    failure_code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")] | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if (self.width is None) != (self.height is None):
            raise ValueError("width and height go together")
        if self.state in (MediaState.stored, MediaState.expired) and (
            self.content_digest is None or self.mime is None
        ):
            raise ValueError("a stored item needs content_digest and mime")
        if self.state in (MediaState.rejected, MediaState.failed) and self.failure_code is None:
            raise ValueError("a rejected or failed item needs failure_code")
        if self.state in (MediaState.pending, MediaState.stored) and self.failure_code is not None:
            raise ValueError("failure_code only on rejected, failed or expired items")
        return self


def check_cardinality(items: list[MediaItem]) -> None:
    """At most 25 photos and 2 plans (so 27 images), unique media ids and ordinals. Raises `ValueError`."""
    photos = sum(1 for i in items if i.kind is MediaKind.photo)
    plans = len(items) - photos
    if photos > MAX_PHOTOS:
        raise ValueError(f"at most {MAX_PHOTOS} photos, got {photos}")
    if plans > MAX_PLANS:
        raise ValueError(f"at most {MAX_PLANS} floor plans, got {plans}")
    if len({i.media_id for i in items}) != len(items):
        raise ValueError("duplicate media_id")
    if len({i.ordinal for i in items}) != len(items):
        raise ValueError("duplicate ordinal")


class MediaManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = MEDIA_SCHEMA_VERSION
    audit_id: UUID
    items: list[MediaItem] = Field(max_length=MAX_ITEMS)
    created_at: datetime | None = Field(default=None, description="None while the manifest is empty")

    @model_validator(mode="after")
    def _bounded(self) -> Self:
        check_cardinality(self.items)
        return self
