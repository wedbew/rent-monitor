"""Architekt wnetrz: bounded contracts for projects, briefs, the person's own items and revisions (RM-448).

Inbound models forbid unknown fields. Money is a `Decimal` with at most two places and is returned as an exact
decimal string; sums are computed server-side in `deal_analyzer.shopping_budget`, never here. A user's
own item needs only a `name`; photo, price and link are optional; an absent price is unknown, never zero.

LEGAL[images]: the person's room photo and item photos are processed and stored for them (RM-448)
GDPR[personal-data]: names, notes and links are free text written by the person; erased with the account and
the project's 30-day lifetime (RM-448)
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer, field_validator

MAX_PROJECTS = 20
MAX_ITEMS_PER_PROJECT = 30
MAX_PRICE_PLN = Decimal("10000000")
MAX_URL_LENGTH = 2048

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Money = Annotated[Decimal, Field(ge=0, le=MAX_PRICE_PLN, max_digits=12, decimal_places=2)]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class RoomType(StrEnum):
    living_room = "living_room"
    bedroom = "bedroom"
    kitchen = "kitchen"
    bathroom = "bathroom"
    hallway = "hallway"
    office = "office"
    other = "other"


class MediaState(StrEnum):
    pending = "pending"
    stored = "stored"
    failed = "failed"


class MediaPurpose(StrEnum):
    source = "source"  # the normalised room photo, never overwritten
    custom_item = "custom_item"  # a photo of the person's own item
    render = "render"  # a generated view (written by the generation slice)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Brief(_In):
    """What the person wants. Saved on the project and snapshotted into every revision."""

    room_type: RoomType
    style: ShortText | None = None
    budget_pln: Money | None = None
    notes: Notes | None = None
    keep: list[ShortText] = Field(default_factory=list, max_length=10)  # things that must stay in the room

    @field_serializer("budget_pln")
    def _money(self, v: Decimal | None) -> str | None:
        return None if v is None else f"{v:.2f}"


class ProjectCreate(_In):
    name: Name
    brief: Brief


def _checked_url(value: str) -> str:
    """A link the person pastes. It is only displayed and followed by their browser, never fetched by us."""
    value = value.strip()
    if len(value) > MAX_URL_LENGTH or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("invalid url")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("url must be http(s) without credentials")
    return value


class CustomItemIn(_In):
    """The person's own item. Only `name` is required."""

    name: Name
    quantity: Annotated[int, Field(ge=1, le=99)] = 1
    price_pln: Money | None = None
    url: str | None = None

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return None if v is None or not v.strip() else _checked_url(v)


class MediaRef(_Out):
    media_id: UUID
    purpose: MediaPurpose
    state: MediaState
    width: int | None
    height: int | None
    content_digest: Sha256Hex | None
    expires_at: datetime


class CustomItemOut(_Out):
    item_id: UUID
    name: str
    quantity: int
    price_pln: str | None = Field(description="exact decimal string; null means the price is unknown")
    url: str | None
    photo: MediaRef | None
    created_at: datetime


class Basket(_Out):
    """Server-computed figures over the person's items. Not a room budget: delivery and missing items are
    not included, and `complete` only says every listed line has a price."""

    known_subtotal_pln: str
    priced_lines: int
    unpriced_lines: int
    complete: bool


class ItemSnapshot(_Out):
    """An item as it was when a revision was saved; later edits to the item do not change it."""

    name: str
    quantity: int
    price_pln: str | None
    url: str | None
    photo_digest: Sha256Hex | None


class RevisionOut(_Out):
    revision_id: UUID
    number: int
    brief: Brief
    source_digest: Sha256Hex | None
    items: list[ItemSnapshot]
    basket: Basket
    created_at: datetime


class ProjectSummary(_Out):
    project_id: UUID
    name: str
    room_type: RoomType
    has_source: bool
    revisions: int
    created_at: datetime
    expires_at: datetime


class ProjectOut(_Out):
    project_id: UUID
    name: str
    brief: Brief
    source: MediaRef | None
    items: list[CustomItemOut]
    basket: Basket
    revisions: list[RevisionOut]
    created_at: datetime
    expires_at: datetime
