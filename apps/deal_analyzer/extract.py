"""Turn the raw Otodom `ad` object into a `Listing`.

Every value is parsed into a bounded type; unknown containers, oversized lists and out-of-range numbers
are rejected with a typed `ExtractionError`.
Free-text analysis (ownership, VAT) lives in the classifiers (RM-85).
"""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from deal_analyzer.errors import ExtractionCode, ExtractionError, RentNotADealError
from deal_analyzer.listing import Listing
from deal_analyzer.numbers import parse_decimal, parse_int

MAX_CHARACTERISTICS = 500
MAX_DESCRIPTION_CHARS = 200_000
_SALE_WIRE = {"SALE", "SELL"}
_RENT_WIRE = {"RENT"}
# Bounds are plausibility checks for Polish residential flats, not business rules.
PRICE_RANGE = (Decimal("1"), Decimal("500000000"))
AREA_RANGE = (Decimal("1"), Decimal("2000"))
FEE_RANGE = (Decimal("0"), Decimal("1000000"))
POLAND_LAT = (Decimal("49.0"), Decimal("55.0"))
POLAND_LNG = (Decimal("14.0"), Decimal("24.5"))


_LOCATION_ID = re.compile(r"[a-z0-9-]+(/[a-z0-9-]+){0,3}")


def _obj(value: object) -> dict[str, Any] | None:
    """The value as a JSON object, or None. Third-party JSON is untyped, so this is the one place we cast."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def _list(value: object) -> list[Any] | None:
    return cast("list[Any]", value) if isinstance(value, list) else None


def _text(value: object, field: str, *, max_len: int, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ExtractionError(ExtractionCode.MISSING_FIELD, field)
        return None
    if not isinstance(value, str):
        raise ExtractionError(ExtractionCode.MALFORMED, field, "expected text")
    cleaned = value.strip()
    if len(cleaned) > max_len:
        raise ExtractionError(ExtractionCode.OUT_OF_RANGE, field, "text too long")
    return cleaned or None


def _clip(value: object, max_len: int) -> str | None:
    return value.strip()[:max_len] if isinstance(value, str) and value.strip() else None


def _characteristics(ad: dict[str, Any]) -> dict[str, str]:
    raw = ad.get("characteristics")
    if raw is None:
        return {}
    items = _list(raw)
    if items is None:
        raise ExtractionError(ExtractionCode.MALFORMED, "characteristics", "expected a list")
    if len(items) > MAX_CHARACTERISTICS:
        raise ExtractionError(ExtractionCode.OUT_OF_RANGE, "characteristics", "too many entries")
    out: dict[str, str] = {}
    for item in items:
        entry = _obj(item)
        if entry is None:
            continue
        key, value = entry.get("key"), entry.get("value")
        if (
            isinstance(key, str)
            and len(key) <= 64
            and value is not None
            and not isinstance(value, dict | list)
        ):
            out.setdefault(key, str(value)[:500])
    return out


def _kind(ad: dict[str, Any]) -> str:
    category = _obj(ad.get("adCategory")) or {}
    wire = category.get("type")
    if not isinstance(wire, str):
        raise ExtractionError(ExtractionCode.MISSING_FIELD, "adCategory.type")
    return wire.strip().upper()


def _datetime(value: object, field: str, warnings: list[str]) -> datetime | None:
    if value is None:
        warnings.append(f"{field}_missing")
        return None
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        warnings.append(f"{field}_invalid")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)  # the portal publishes UTC; assume it rather than fail the audit
        warnings.append(f"{field}_assumed_utc")
    return parsed


def _coordinates(ad: dict[str, Any], warnings: list[str]) -> tuple[Decimal | None, Decimal | None]:
    coords = _obj((_obj(ad.get("location")) or {}).get("coordinates"))
    if coords is None:
        warnings.append("coordinates_missing")
        return None, None
    try:
        lat = parse_decimal(
            coords.get("latitude"), "latitude", low=Decimal("-90"), high=Decimal("90"), allow_float=True
        )
        lng = parse_decimal(
            coords.get("longitude"), "longitude", low=Decimal("-180"), high=Decimal("180"), allow_float=True
        )
    except ExtractionError:
        warnings.append("coordinates_invalid")
        return None, None
    if not (POLAND_LAT[0] <= lat <= POLAND_LAT[1] and POLAND_LNG[0] <= lng <= POLAND_LNG[1]):
        warnings.append("coordinates_outside_poland")
    return lat, lng


def _city(ad: dict[str, Any]) -> str | None:
    location = _obj(ad.get("location")) or {}
    levels = _list((_obj(location.get("reverseGeocoding")) or {}).get("locations")) or []
    for level in levels[:20]:
        entry = _obj(level)
        if (
            entry is not None
            and entry.get("locationLevel") == "city_or_village"
            and (name := _clip(entry.get("name"), 120))
        ):
            return name
    city = _obj((_obj(location.get("address")) or {}).get("city")) or {}
    return _clip(city.get("name"), 120)


def _location_id(ad: dict[str, Any]) -> str | None:
    """Otodom's path for the listing's city, if it is a safe slug path (appended to a fixed search URL)."""
    location = _obj(ad.get("location")) or {}
    levels = _list((_obj(location.get("reverseGeocoding")) or {}).get("locations")) or []
    for level in levels[:20]:
        entry = _obj(level)
        if entry is not None and entry.get("locationLevel") == "city_or_village":
            value = entry.get("id")
            if isinstance(value, str) and len(value) <= 160 and _LOCATION_ID.fullmatch(value):
                return value
    return None


def _street(ad: dict[str, Any]) -> str | None:
    address = _obj((_obj(ad.get("location")) or {}).get("address")) or {}
    return _clip((_obj(address.get("street")) or {}).get("name"), 160)


def _structured_fields(root: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    """Price, area, rooms (required) and optional building fields (`attributes`, then `characteristics`)."""
    chars = _characteristics(root)
    attrs = _obj(root.get("attributes")) or {}

    def pick(key: str) -> object:
        return attrs.get(key) if attrs.get(key) is not None else chars.get(key)

    def optional_int(key: str, *, low: int, high: int, label: str) -> int | None:
        raw = pick(key)
        if raw is None:
            warnings.append(f"{label}_missing")
            return None
        try:
            return parse_int(raw, label, low=low, high=high)
        except ExtractionError:
            warnings.append(f"{label}_invalid")
            return None

    def optional_text(key: str, label: str, max_len: int) -> str | None:
        raw = pick(key)
        value = _clip(str(raw), max_len) if raw is not None else None
        if value is None:
            warnings.append(f"{label}_missing")
        return value

    admin_fee: Decimal | None = None
    if chars.get("rent") is None:
        warnings.append("admin_fee_missing")
    else:
        admin_fee = parse_decimal(chars["rent"], "admin_fee_pln", low=FEE_RANGE[0], high=FEE_RANGE[1])
    deposit = (
        parse_decimal(chars["deposit"], "deposit_pln", low=FEE_RANGE[0], high=FEE_RANGE[1])
        if chars.get("deposit") is not None
        else None
    )
    return {
        "price_pln": parse_decimal(chars.get("price"), "price", low=PRICE_RANGE[0], high=PRICE_RANGE[1]),
        "area_m2": parse_decimal(pick("m"), "area_m2", low=AREA_RANGE[0], high=AREA_RANGE[1]),
        "rooms": parse_int(pick("rooms_num"), "rooms", low=1, high=50),
        "admin_fee_pln": admin_fee,
        "deposit_pln": deposit,
        "floor": optional_text("floor_no", "floor", 32),
        "building_floors": optional_int("building_floors_num", low=0, high=200, label="building_floors"),
        "build_year": optional_int("build_year", low=1500, high=2100, label="build_year"),
        "building_type": optional_text("building_type", "building_type", 64),
        "heating": optional_text("heating", "heating", 64),
        "windows": optional_text("windows_type", "windows", 64),
        "building_ownership": _clip(pick("building_ownership"), 64),
    }


def extract_listing(ad: object) -> Listing:
    """Parse one `pageProps.ad`. Raises `RentNotADealError` for rentals, `ExtractionError` if unusable."""
    root = _obj(ad)
    if root is None:
        raise ExtractionError(ExtractionCode.MALFORMED, "ad", "expected an object")
    raw_id = root.get("id")
    otodom_id = str(raw_id).strip() if isinstance(raw_id, str | int) and not isinstance(raw_id, bool) else ""
    if not otodom_id or len(otodom_id) > 32:
        raise ExtractionError(ExtractionCode.MISSING_FIELD, "id")

    kind = _kind(root)  # first, so a rental is rejected before any other work (invariant 1)
    if kind in _RENT_WIRE:
        raise RentNotADealError(otodom_id)
    if kind not in _SALE_WIRE:
        raise ExtractionError(ExtractionCode.INVALID_VALUE, "adCategory.type", "unknown category")

    warnings: list[str] = []
    structured = _structured_fields(root, warnings)

    description_raw = root.get("description")
    if not isinstance(description_raw, str):
        raise ExtractionError(ExtractionCode.MISSING_FIELD, "description")
    if len(description_raw) > MAX_DESCRIPTION_CHARS:
        raise ExtractionError(ExtractionCode.OUT_OF_RANGE, "description", "text too long")
    title = _text(root.get("title"), "title", max_len=300) or ""
    url = _text(root.get("url"), "url", max_len=500)
    lat, lng = _coordinates(root, warnings)
    city = _city(root)
    if city is None:
        warnings.append("city_missing")
    street = _street(root)
    if street is None:
        warnings.append("street_missing")

    return Listing(
        otodom_id=otodom_id,
        url=url,
        title=title,
        description=description_raw,
        kind="SALE",
        **structured,
        city=city,
        location_id=_location_id(root),
        street=street,
        latitude=lat,
        longitude=lng,
        created_at=_datetime(root.get("createdAt"), "created_at", warnings),
        modified_at=_datetime(root.get("modifiedAt"), "modified_at", warnings),
        warnings=tuple(warnings),
    )
