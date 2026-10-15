"""Hand-built, anonymised SALE listings for the API smoke test and the sample capture (#263).

Nothing here is a real advert: cities are real names (a place is not personal data), but titles, streets,
sizes and prices are invented, and there is no seller name, phone or photo content. The five `SUCCESS`
listings differ in city, size, price, admin fee and photo count, so five distinct `succeeded` results exist.
"""

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from deal_analyzer.vision import Condition, PhotoAssessment, PhotoKind, VisionOutput

PHOTO_HOST = "https://ireland.apollo.olxcdn.com/v1/files/smoke"


@dataclass(frozen=True)
class SaleListing:
    key: str
    city: str
    area_m2: str
    price_pln: str
    admin_fee_pln: str
    rooms: str
    photos: int
    floor_plans: int
    condition: Condition
    lat: float
    lon: float


SUCCESS: tuple[SaleListing, ...] = (
    SaleListing("warszawa", "Warszawa", "48.5", "890000", "650", "2", 11, 1, Condition.GOOD, 52.23, 21.01),
    SaleListing("krakow", "Kraków", "36.2", "612000", "420", "2", 6, 0, Condition.REFRESH, 50.06, 19.94),
    SaleListing("lodz", "Łódź", "62.0", "395000", "310", "3", 18, 1, Condition.RENOVATION, 51.76, 19.46),
    SaleListing("gdansk", "Gdańsk", "28.4", "445000", "380", "1", 3, 0, Condition.GOOD, 54.35, 18.65),
    SaleListing("torun", "Toruń", "74.9", "520000", "540", "4", 24, 2, Condition.SHELL, 53.01, 18.6),
)


def sale_ad(listing: SaleListing, **overrides: Any) -> dict[str, Any]:
    """The Otodom ad payload the fake source serves for `listing`."""
    ad: dict[str, Any] = {
        "id": 91000000 + len(listing.key),
        "title": f"Mieszkanie {listing.rooms} pok., {listing.city}, {listing.area_m2} m2",
        "description": "Jasne mieszkanie w spokojnej okolicy, blisko komunikacji. Opis wymyslony do testow.",
        "createdAt": "2026-09-01T10:00:00Z",
        "modifiedAt": "2026-10-01T08:30:00Z",
        "adCategory": {"type": "SELL"},
        "characteristics": [
            {"key": "price", "value": listing.price_pln},
            {"key": "m", "value": listing.area_m2},
            {"key": "rooms_num", "value": listing.rooms},
            {"key": "rent", "value": listing.admin_fee_pln},
            {"key": "floor_no", "value": "2"},
            {"key": "building_floors_num", "value": "5"},
            {"key": "build_year", "value": "1998"},
        ],
        "images": [{"large": f"{PHOTO_HOST}/{listing.key}/{n}"} for n in range(listing.photos)],
        "floorPlans": [{"large": f"{PHOTO_HOST}/{listing.key}/plan{n}"} for n in range(listing.floor_plans)],
        "location": {
            "coordinates": {"latitude": listing.lat, "longitude": listing.lon},
            "address": {"city": {"name": listing.city}, "street": {"name": "Przykladowa", "number": "1"}},
        },
    }
    ad.update(deepcopy(overrides))
    return ad


def vision_answer(listing: SaleListing) -> VisionOutput:
    """What the fake vision provider says about `listing`'s photos: a condition and a small, clamped nudge."""
    photos = (PhotoAssessment(kind=PhotoKind.INTERIOR),) * max(listing.photos - 1, 1) + (
        PhotoAssessment(kind=PhotoKind.RENDER),
    )
    return VisionOutput(
        condition=listing.condition,
        photos=photos,
        capex_adjustment=Decimal("0.05"),
        rent_adjustment=Decimal("-0.02"),
    )


# Failure variants: the ad is one of the SUCCESS cities, changed so that the pipeline refuses it.
RENT_AD = sale_ad(SUCCESS[0], adCategory={"type": "RENT"})
FRACTIONAL_AD = sale_ad(SUCCESS[1], title="Sprzedam 1/2 udziału w mieszkaniu, Kraków")
