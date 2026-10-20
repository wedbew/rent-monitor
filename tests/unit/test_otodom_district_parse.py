"""District of a search tile: taken from the site's reverse geocoding, only under the searched place (RM-439).

Hand-built tiles in the shape seen live on 2026-10-20 (Gdańsk search page):
`location.reverseGeocoding.locations` lists voivodeship, city and, where the site knows one, a
`district` entry with a path id.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from rm_worker.importers.otodom_corpus import parse_search_page

PLACE = "pomorskie/gdansk/gdansk/gdansk"
T = datetime(2026, 10, 20, 6, tzinfo=UTC)


def geocoding(*entries: tuple[str, str, str]) -> dict[str, Any]:
    return {
        "address": {"street": None, "city": None},
        "reverseGeocoding": {
            "locations": [{"id": i, "name": n, "locationLevel": level} for i, n, level in entries]
        },
    }


def tile(offer_id: int, location: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "id": offer_id,
        "estate": "FLAT",
        "transaction": "RENT",
        "href": f"/pl/oferta/x-ID{offer_id}",
        "totalPrice": {"value": 3000, "currency": "PLN"},
        "areaInSquareMeters": 50,
        "roomsNumber": 2,
        "createdAtFirst": "2026-10-19T08:00:00+02:00",
        "location": location,
    }


def parse(*tiles: dict[str, Any], place_path: str | None = PLACE) -> list[Any]:
    page = {"items": list(tiles), "pagination": {"totalPages": 1, "currentPage": 1}}
    return list(
        parse_search_page(page, location_id="gdansk", observed_at=T, place_path=place_path).observations
    )


CITY = (PLACE, "Gdańsk", "city_or_village")


def test_a_district_under_the_searched_place_is_kept_with_its_name() -> None:
    (o,) = parse(tile(1, geocoding(CITY, (f"{PLACE}/srodmiescie", "Śródmieście", "district"))))
    assert (o.district_id, o.district_name) == (f"{PLACE}/srodmiescie", "Śródmieście")


@pytest.mark.parametrize(
    "location",
    [
        None,
        {"reverseGeocoding": None},
        {"reverseGeocoding": {"locations": "nope"}},
        geocoding(CITY),  # a city without a district level: no district, not a guess
        geocoding(CITY, ("pomorskie/gdynia/gdynia/gdynia/oksywie", "Oksywie", "district")),  # another place
        geocoding(CITY, (f"{PLACE}/a/b", "Deep", "district")),  # not a direct child
        geocoding(CITY, (f"{PLACE}/srodmiescie", "", "district")),  # no name
        geocoding(CITY, (f"{PLACE}/srodmiescie", "Bad\u0000name", "district")),
        geocoding(CITY, (f"{PLACE}/srodmiescie", "Śródmieście", "city_or_village")),  # wrong level
        geocoding(CITY, ("pomorskie/gdansk/gdansk/gdansk/SRODMIESCIE", "X", "district")),  # not a path id
    ],
)
def test_anything_that_is_not_a_district_of_this_place_is_no_district(
    location: dict[str, Any] | None,
) -> None:
    (o,) = parse(tile(1, location))
    assert (o.district_id, o.district_name) == (None, None)


def test_without_the_place_path_no_district_is_read() -> None:
    (o,) = parse(
        tile(1, geocoding(CITY, (f"{PLACE}/srodmiescie", "Śródmieście", "district"))), place_path=None
    )
    assert o.district_id is None
