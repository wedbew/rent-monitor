"""The typed, bounded listing the engine works on. Money is `Decimal` PLN; no market data here."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


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
