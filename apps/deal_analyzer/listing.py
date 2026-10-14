"""The typed, bounded listing the engine works on. Money is `Decimal` PLN; no market data here."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

MAX_MEDIA_URLS = 40
MediaUrl = Annotated[str, StringConstraints(max_length=500)]


class Listing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    otodom_id: str = Field(min_length=1, max_length=32)
    url: str | None = Field(default=None, max_length=500)
    title: str = Field(max_length=300)
    description: str = Field(max_length=200_000)
    kind: Literal["SALE"]  # a RENT listing never becomes a Listing: `RentNotADealError` (invariant 1)
    price_pln: Decimal = Field(gt=0)  # asking price: never a deed price (invariant 2)
    area_m2: Decimal = Field(gt=0)
    rooms: int = Field(ge=1, le=50)
    admin_fee_pln: Decimal | None = Field(default=None, ge=0)  # czynsz: OPEX, never income (invariant 3)
    deposit_pln: Decimal | None = Field(default=None, ge=0)
    floor: str | None = Field(default=None, max_length=32)
    building_floors: int | None = Field(default=None, ge=0, le=200)
    build_year: int | None = Field(default=None, ge=1500, le=2100)
    building_type: str | None = Field(default=None, max_length=64)
    heating: str | None = Field(default=None, max_length=64)
    windows: str | None = Field(default=None, max_length=64)
    building_ownership: str | None = Field(default=None, max_length=64)  # portal's structured ownership value
    city: str | None = Field(default=None, max_length=120)
    # Otodom's own path for the city (e.g. "kujawsko--pomorskie/torun/torun/torun"): lets the market importer
    # find rental comparables. Lower-case slugs only, so it can be appended to a fixed search URL safely.
    location_id: str | None = Field(default=None, max_length=160, pattern=r"^[a-z0-9-]+(/[a-z0-9-]+){0,3}$")
    # Image URLs from the advert (large size, https only, bounded). They are only ever fetched by the worker's
    # image pipeline, which re-validates the host against an allow-list (LEGAL[images]).
    photo_urls: tuple[MediaUrl, ...] = Field(default=(), max_length=MAX_MEDIA_URLS)
    floor_plan_urls: tuple[MediaUrl, ...] = Field(default=(), max_length=MAX_MEDIA_URLS)
    street: str | None = Field(default=None, max_length=160)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    created_at: AwareDatetime | None = None
    modified_at: AwareDatetime | None = None
    warnings: tuple[
        str, ...
    ] = ()  # stable codes for missing or doubtful inputs; they lower confidence downstream

    @property
    def price_per_m2(self) -> Decimal:
        return self.price_pln / self.area_m2


__all__ = ["Listing"]
