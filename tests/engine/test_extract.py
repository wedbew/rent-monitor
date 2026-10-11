"""N-01: bounded, typed extraction of a listing (docs/ENGINE-SPEC.md, blueprint §2 extract stage)."""

import contextlib
import json
from decimal import Decimal
from typing import Any

import pytest
from conftest import make_ad
from deal_analyzer import ExtractionCode, ExtractionError, Listing, RentNotADealError, extract_listing
from hypothesis import given, settings
from hypothesis import strategies as st


def code_of(ad: object) -> ExtractionCode:
    with pytest.raises(ExtractionError) as err:
        extract_listing(ad)
    return err.value.code


# ---- invariant 1 ----
@pytest.mark.invariant
@pytest.mark.parametrize("wire", ["RENT", "rent", " Rent "])
def test_invariant_rent_is_not_a_deal(wire: str) -> None:
    ad = make_ad(adCategory={"type": wire})
    with pytest.raises(RentNotADealError) as err:
        extract_listing(ad)
    assert err.value.otodom_id == "90000001"


@pytest.mark.invariant
def test_invariant_rent_is_rejected_before_any_other_field_is_looked_at() -> None:
    # No price, no area, no description: a rental must still end as RENT_NOT_DEAL, not as a parse failure,
    # so the worker releases the credit with the right reason and never reaches the vision stage.
    with pytest.raises(RentNotADealError):
        extract_listing({"id": "x1", "adCategory": {"type": "RENT"}})


# ---- happy path ----
def test_a_complete_sale_listing_is_extracted_exactly() -> None:
    listing = extract_listing(make_ad())
    assert listing.otodom_id == "90000001"
    assert listing.kind == "SALE"
    assert listing.price_pln == Decimal("450000")
    assert listing.area_m2 == Decimal("48.5")
    assert listing.rooms == 2
    assert listing.admin_fee_pln == Decimal("600")
    assert listing.deposit_pln == Decimal("5000")
    assert (listing.floor, listing.building_floors, listing.build_year) == ("2", 5, 1998)
    assert (listing.building_type, listing.heating, listing.windows) == ("block", "urban", "plastic")
    assert (listing.city, listing.street) == ("Testowo", "Przykładowa")
    assert listing.latitude == Decimal("52.2297")
    assert listing.created_at is not None
    assert listing.created_at.tzinfo is not None
    assert listing.warnings == ()
    assert listing.price_per_m2 == Decimal("450000") / Decimal("48.5")


def test_no_float_survives_in_the_result() -> None:
    dumped = extract_listing(make_ad()).model_dump()
    assert not [k for k, v in dumped.items() if isinstance(v, float)]


def test_extraction_is_deterministic() -> None:
    a, b = extract_listing(make_ad()), extract_listing(make_ad())
    assert a == b
    assert a.model_dump_json() == b.model_dump_json()


def test_the_listing_is_immutable_and_rejects_unknown_fields() -> None:
    listing = extract_listing(make_ad())
    with pytest.raises(Exception, match="frozen"):
        listing.rooms = 3
    with pytest.raises(ValueError, match="extra"):
        Listing(**{**listing.model_dump(), "surprise": 1})


# ---- invariant 3: the admin fee is a cost field, nothing else ----
def test_characteristics_rent_is_the_admin_fee_and_the_model_has_no_income_field() -> None:
    listing = extract_listing(make_ad(chars={"rent": "600"}))
    assert listing.admin_fee_pln == Decimal("600")
    income_like = [
        name for name in Listing.model_fields if "income" in name or name in {"rent", "monthly_rent"}
    ]
    assert income_like == []  # the portal's `rent` key is czynsz; it must never be mistaken for rental income


def test_a_missing_admin_fee_is_none_with_a_warning_not_zero() -> None:
    listing = extract_listing(make_ad(drop=["rent"]))
    assert listing.admin_fee_pln is None
    assert "admin_fee_missing" in listing.warnings


# ---- number parsing ----
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("450000", "450000"),
        ("450 000", "450000"),
        ("450\u00a0000", "450000"),
        ("450000,50", "450000.50"),
        (450000, "450000"),
    ],
)
def test_polish_number_formats(raw: object, expected: str) -> None:
    assert extract_listing(make_ad(chars={"price": raw})).price_pln == Decimal(expected)


@pytest.mark.parametrize(
    "raw",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        "1e9",
        "1E5",
        "0x10",
        "1.234,5",
        "1,2,3",
        "",
        "abc",
        "12 abc",
        "٣٤٥",
        "4" * 40,
    ],
)
def test_hostile_or_ambiguous_numbers_are_rejected(raw: str) -> None:
    assert code_of(make_ad(chars={"price": raw})) == ExtractionCode.INVALID_VALUE


@pytest.mark.parametrize("raw", [True, 1.5, [1], {"a": 1}, float("nan")])
def test_non_text_numbers_are_rejected(raw: object) -> None:
    ad = make_ad()
    ad["attributes"] = {"m": raw}
    with pytest.raises(ExtractionError):
        extract_listing(ad)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("price", "0"),
        ("price", "-5"),
        ("price", "999999999999"),
        ("m", "0"),
        ("m", "5000"),
        ("rooms_num", "0"),
        ("rooms_num", "51"),
        ("rent", "-1"),
    ],
)
def test_implausible_numbers_are_out_of_range(key: str, value: str) -> None:
    assert code_of(make_ad(chars={key: value})) == ExtractionCode.OUT_OF_RANGE


def test_rooms_must_be_a_whole_number() -> None:
    assert code_of(make_ad(chars={"rooms_num": "2.5"})) == ExtractionCode.INVALID_VALUE


@pytest.mark.parametrize("key", ["price", "m", "rooms_num"])
def test_required_numbers_missing_are_errors(key: str) -> None:
    assert code_of(make_ad(drop=[key])) == ExtractionCode.INVALID_VALUE  # absent value is not a number


def test_attributes_take_precedence_over_characteristics() -> None:
    ad = make_ad()
    ad["attributes"] = {"m": "60", "rooms_num": "3"}
    listing = extract_listing(ad)
    assert (listing.area_m2, listing.rooms) == (Decimal("60"), 3)


# ---- structure ----
@pytest.mark.parametrize("payload", [None, [], "ad", 7, 1.5, True])
def test_a_non_object_ad_is_malformed(payload: object) -> None:
    assert code_of(payload) == ExtractionCode.MALFORMED


@pytest.mark.parametrize("ident", [None, "", "   ", "x" * 33])
def test_a_missing_or_oversized_id_is_rejected(ident: object) -> None:
    assert code_of(make_ad(id=ident)) == ExtractionCode.MISSING_FIELD


def test_unknown_or_missing_category_is_rejected() -> None:
    assert code_of(make_ad(adCategory={"type": "SWAP"})) == ExtractionCode.INVALID_VALUE
    assert code_of(make_ad(adCategory={})) == ExtractionCode.MISSING_FIELD
    assert code_of(make_ad(adCategory="SELL")) == ExtractionCode.MISSING_FIELD


def test_characteristics_must_be_a_bounded_list() -> None:
    assert code_of(make_ad(characteristics={"price": "1"})) == ExtractionCode.MALFORMED
    many = [{"key": f"k{i}", "value": "1"} for i in range(501)]
    assert code_of(make_ad(characteristics=many)) == ExtractionCode.OUT_OF_RANGE


def test_junk_entries_inside_characteristics_are_ignored() -> None:
    junk: list[Any] = [
        None,
        5,
        "x",
        {"key": 1, "value": 2},
        {"key": "k" * 200, "value": "1"},
        {"key": "a", "value": {"n": 1}},
    ]
    ad = make_ad()
    ad["characteristics"] = junk + ad["characteristics"]
    assert extract_listing(ad).price_pln == Decimal("450000")


def test_the_first_value_for_a_repeated_key_wins() -> None:
    ad = make_ad()
    ad["characteristics"] = [{"key": "price", "value": "111"}, *ad["characteristics"]]
    assert extract_listing(ad).price_pln == Decimal("111")


def test_description_is_required_text_with_a_size_cap() -> None:
    assert code_of(make_ad(description=None)) == ExtractionCode.MISSING_FIELD
    assert code_of(make_ad(description=["x"])) == ExtractionCode.MISSING_FIELD
    assert code_of(make_ad(description="x" * 200_001)) == ExtractionCode.OUT_OF_RANGE
    assert extract_listing(make_ad(description="x" * 200_000)).description.startswith("xxx")


def test_title_and_url_are_bounded_text() -> None:
    assert code_of(make_ad(title="t" * 301)) == ExtractionCode.OUT_OF_RANGE
    assert code_of(make_ad(url=123)) == ExtractionCode.MALFORMED
    assert extract_listing(make_ad(title=None)).title == ""


# ---- warnings keep doubtful metadata from failing an audit ----
def test_missing_optional_fields_become_warnings() -> None:
    ad = make_ad(
        drop=[
            "floor_no",
            "building_floors_num",
            "build_year",
            "building_type",
            "heating",
            "windows_type",
            "deposit",
        ]
    )
    ad["location"] = {}
    ad.pop("createdAt")
    listing = extract_listing(ad)
    assert {
        "floor_missing",
        "building_floors_missing",
        "build_year_missing",
        "building_type_missing",
        "heating_missing",
        "windows_missing",
        "coordinates_missing",
        "city_missing",
        "street_missing",
        "created_at_missing",
    } <= set(listing.warnings)
    assert listing.deposit_pln is None


def test_implausible_optional_values_warn_instead_of_failing() -> None:
    listing = extract_listing(make_ad(chars={"build_year": "3000", "building_floors_num": "abc"}))
    assert listing.build_year is None
    assert listing.building_floors is None
    assert {"build_year_invalid", "building_floors_invalid"} <= set(listing.warnings)


@pytest.mark.parametrize(
    ("coords", "warning", "kept"),
    [
        ({"latitude": 999, "longitude": 21}, "coordinates_invalid", False),
        ({"latitude": "x", "longitude": 21}, "coordinates_invalid", False),
        ({"latitude": 40.7, "longitude": -74.0}, "coordinates_outside_poland", True),
    ],
)
def test_coordinate_problems(coords: dict[str, Any], warning: str, kept: bool) -> None:
    ad = make_ad()
    ad["location"]["coordinates"] = coords
    listing = extract_listing(ad)
    assert warning in listing.warnings
    assert (listing.latitude is not None) is kept


def test_dates_are_timezone_aware_and_bad_dates_warn() -> None:
    naive = extract_listing(make_ad(createdAt="2026-09-01T10:00:00", modifiedAt="garbage"))
    assert naive.created_at is not None
    assert naive.created_at.utcoffset() is not None
    assert "created_at_assumed_utc" in naive.warnings
    assert naive.modified_at is None
    assert "modified_at_invalid" in naive.warnings


def test_city_prefers_reverse_geocoding_over_the_address() -> None:
    ad = make_ad()
    ad["location"]["reverseGeocoding"] = {
        "locations": [
            {"locationLevel": "district", "name": "X"},
            {"locationLevel": "city_or_village", "name": "Geocodowo"},
        ]
    }
    assert extract_listing(ad).city == "Geocodowo"


# ---- robustness: hostile JSON never escapes as an untyped exception ----
json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(-(10**12), 10**12)
    | st.floats(allow_nan=True, allow_infinity=True)
    | st.text(max_size=40),
    lambda inner: st.lists(inner, max_size=5) | st.dictionaries(st.text(max_size=12), inner, max_size=6),
    max_leaves=25,
)


@settings(max_examples=300, deadline=None)
@given(payload=json_values)
def test_arbitrary_json_only_ever_yields_a_listing_or_a_typed_error(payload: object) -> None:
    try:
        result = extract_listing(payload)
    except (ExtractionError, RentNotADealError):
        return
    assert isinstance(result, Listing)


@settings(max_examples=300, deadline=None)
@given(
    key=st.sampled_from(["price", "m", "rooms_num", "rent", "deposit", "floor_no", "build_year"]),
    value=json_values,
)
def test_hostile_values_in_known_slots_never_crash(key: str, value: object) -> None:
    ad = make_ad()
    ad["characteristics"] = [{"key": key, "value": value}, *ad["characteristics"]]
    ad["attributes"] = {key: value}
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return
    with contextlib.suppress(ExtractionError, RentNotADealError):
        extract_listing(ad)
