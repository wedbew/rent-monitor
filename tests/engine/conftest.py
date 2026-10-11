"""Hand-built, anonymised listing payloads for engine tests (no real seller data, nothing from the POC)."""

from copy import deepcopy
from typing import Any

import pytest

BASE_AD: dict[str, Any] = {
    "id": 90000001,
    "title": "Mieszkanie 2 pokoje, Testowo",
    "url": "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-testowo-IDtest01",
    "description": "Jasne mieszkanie na drugim piętrze. Cisza, spokój, blisko komunikacji.",
    "createdAt": "2026-09-01T10:00:00Z",
    "modifiedAt": "2026-10-01T08:30:00Z",
    "adCategory": {"type": "SELL"},
    "characteristics": [
        {"key": "price", "value": "450000"},
        {"key": "m", "value": "48.5"},
        {"key": "rooms_num", "value": "2"},
        {"key": "rent", "value": "600"},
        {"key": "deposit", "value": "5000"},
        {"key": "floor_no", "value": "2"},
        {"key": "building_floors_num", "value": "5"},
        {"key": "build_year", "value": "1998"},
        {"key": "building_type", "value": "block"},
        {"key": "heating", "value": "urban"},
        {"key": "windows_type", "value": "plastic"},
    ],
    "location": {
        "coordinates": {"latitude": 52.2297, "longitude": 21.0122},
        "address": {"city": {"name": "Testowo"}, "street": {"name": "Przykładowa", "number": "1"}},
    },
}


def make_ad(**overrides: Any) -> dict[str, Any]:
    """A valid SALE ad. `chars={...}` replaces characteristic values; `drop=[...]` removes some."""
    ad = deepcopy(BASE_AD)
    chars: dict[str, Any] = overrides.pop("chars", {})
    drop: list[str] = overrides.pop("drop", [])
    items = [c for c in ad["characteristics"] if c["key"] not in drop]
    for key, value in chars.items():
        for item in items:
            if item["key"] == key:
                item["value"] = value
                break
        else:
            items.append({"key": key, "value": value})
    ad["characteristics"] = items
    ad.update(overrides)
    return ad


@pytest.fixture
def ad() -> dict[str, Any]:
    return make_ad()
