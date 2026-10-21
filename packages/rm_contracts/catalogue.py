"""Architekt wnetrz catalogue: products, exact variants and observed seller offers (RM-449, #284).

An `Offer` is one observation of one seller's price for one exact variant of one product. It carries its
provenance (provider, ids, product URL), when it was seen, when it stops being trustworthy, and what the
source allows us to do with its photo. Nothing here is estimated: an unknown price is `None`, never zero,
and a generic search link is not an offer. Money is a `Decimal` returned as an exact string; sums are
computed server-side in `deal_analyzer.shopping_budget`.

LEGAL[third-party-data]: merchant product data (titles, prices, URLs, photos) from a licensed source (RM-449)
LEGAL[republication]: the offers are shown to the signed-in person who searched (RM-449)
LEGAL[images]: `ImageRights` records what the source permits for each product photo (RM-449)
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MAX_SELECTIONS_PER_PROJECT = 30
MAX_CANDIDATES = 24

Id = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(ge=0, le=Decimal("10000000"), max_digits=12, decimal_places=2)]


class Availability(StrEnum):
    in_stock = "in_stock"
    out_of_stock = "out_of_stock"
    unknown = "unknown"


class OfferState(StrEnum):
    """Derived on read from the clock and the stored observation; never stored."""

    fresh = "fresh"
    expired = "expired"  # past `expires_at`: the price is history, not a quote
    unavailable = "unavailable"  # the source says it cannot be bought now


class ImageRights(BaseModel):
    """What the source permits for a product photo; display, storage and generation are separate rights."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    display: bool = True  # may be shown by remote link
    cache: bool = False  # may a normalised copy be kept in our bucket
    generation_reference: bool = False  # may it be sent to an image model as a reference


class Dimensions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    width_cm: Annotated[Decimal, Field(gt=0, le=1000, max_digits=7, decimal_places=1)] | None = None
    depth_cm: Annotated[Decimal, Field(gt=0, le=1000, max_digits=7, decimal_places=1)] | None = None
    height_cm: Annotated[Decimal, Field(gt=0, le=1000, max_digits=7, decimal_places=1)] | None = None
    source: Text  # where the numbers come from, e.g. the merchant's specification


class Offer(BaseModel):
    """One observation. Frozen: a changed price is a new observation, not an edit."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: Id
    product_id: Id
    variant_id: Id
    offer_id: Id | None = None
    seller: Text
    title: Text
    product_url: str = Field(max_length=2048, pattern=r"^https?://\S+$")
    category: Id
    attributes: dict[
        Annotated[str, StringConstraints(max_length=40)], Annotated[str, StringConstraints(max_length=80)]
    ] = Field(default_factory=dict, max_length=12)  # exact variant: colour, material, size
    dimensions: Dimensions | None = None
    price_pln: Money | None = None  # None: the source gave no price
    price_is_gross: bool | None = None
    price_conditions: Text | None = None  # promotion, membership, minimum basket
    delivery_pln: Money | None = None
    delivery_known: bool = False
    availability: Availability = Availability.unknown
    observed_at: datetime
    expires_at: datetime
    image_url: str | None = Field(default=None, max_length=2048)
    image_rights: ImageRights = Field(default_factory=ImageRights)
    source_label: Text  # who vouches for the data, e.g. the feed name; a demo source says so


class OfferOut(BaseModel):
    """An `Offer` as the API returns it: money as exact strings, plus the server-derived state."""

    model_config = ConfigDict(extra="forbid")
    provider: str
    product_id: str
    variant_id: str
    offer_id: str | None
    seller: str
    title: str
    product_url: str
    category: str
    attributes: dict[str, str]
    dimensions: Dimensions | None
    price_pln: str | None
    price_is_gross: bool | None
    price_conditions: str | None
    delivery_pln: str | None
    delivery_known: bool
    availability: Availability
    observed_at: datetime
    expires_at: datetime
    state: OfferState
    image_url: str | None
    image_rights: ImageRights
    source_label: str


class CandidateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer: OfferOut
    flags: list[Id] = Field(
        default_factory=list, max_length=8
    )  # stable codes the UI words: price_unknown, ...


class SelectionIn(BaseModel):
    """Pick an exact variant. The server re-fetches the offer from the provider; the client sends no price."""

    model_config = ConfigDict(extra="forbid")
    provider: Id
    product_id: Id
    variant_id: Id
    quantity: Annotated[int, Field(ge=1, le=99)] = 1


class SelectionQuantity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: Annotated[int, Field(ge=1, le=99)]


class SelectionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selection_id: UUID
    quantity: int
    offer: OfferOut
    line_total_pln: str | None = Field(
        description="quantity x price when the offer is fresh and priced, else null"
    )
    checked_at: datetime


class SelectionSnapshot(BaseModel):
    """A selection as a revision saw it."""

    model_config = ConfigDict(extra="forbid")
    quantity: int
    offer: OfferOut


class CatalogueStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    available: bool
    provider: str | None
    source_label: str | None
    is_demo: bool = Field(description="true when the data is a deterministic demo, not a live merchant feed")
