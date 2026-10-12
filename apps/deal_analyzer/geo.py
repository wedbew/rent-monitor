"""Distances and nearest points of interest (docs/ENGINE-SPEC.md; blueprint pipeline `context` stage).

Pure and offline: the caller supplies coordinates and POIs (fetched and cached by the worker). Geodesic
maths uses floats
internally because it is trigonometry, not money; every value leaves this module as a `Decimal` rounded
to whole metres.
"""

import math
from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius
MAX_POIS = 500


class PoiCategory(StrEnum):
    TRANSIT = "transit"
    SCHOOL = "school"
    SHOP = "shop"
    PARK = "park"


class Poi(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    category: PoiCategory
    latitude: Decimal = Field(ge=Decimal(-90), le=Decimal(90))
    longitude: Decimal = Field(ge=Decimal(-180), le=Decimal(180))


class NearestPoi(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    category: PoiCategory
    distance_m: Decimal | None  # None when none was found within the search radius
    count_within_radius: int


def distance_m(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
    """Great-circle (haversine) distance in whole metres, half-up. Symmetric; zero for identical points."""
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    d_phi, d_lambda = p2 - p1, math.radians(float(lon2)) - math.radians(float(lon1))
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    meters = 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))
    return Decimal(repr(meters)).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def nearest_by_category(
    latitude: Decimal, longitude: Decimal, pois: Iterable[Poi], radius_m: int
) -> tuple[NearestPoi, ...]:
    """Nearest POI per category within `radius_m`, plus how many lie inside. All categories are always
    reported."""
    best: dict[PoiCategory, Decimal] = {}
    counts: dict[PoiCategory, int] = dict.fromkeys(PoiCategory, 0)
    for poi in list(pois)[:MAX_POIS]:
        d = distance_m(latitude, longitude, poi.latitude, poi.longitude)
        if d > radius_m:
            continue
        counts[poi.category] += 1
        if poi.category not in best or d < best[poi.category]:
            best[poi.category] = d
    return tuple(
        NearestPoi(category=c, distance_m=best.get(c), count_within_radius=counts[c]) for c in PoiCategory
    )


def in_poland(latitude: Decimal, longitude: Decimal) -> bool:
    return Decimal("49.0") <= latitude <= Decimal("55.0") and Decimal("14.0") <= longitude <= Decimal("24.5")


def bounding_box(
    points: Sequence[tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    if not points:
        return None
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    return min(lats), min(lons), max(lats), max(lons)
