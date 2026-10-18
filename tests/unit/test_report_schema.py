"""The committed JSON Schema of `DealAnalysis` (RM-266). Regenerate with `scripts/gen_report_schema.py`."""

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import jsonschema_rs
import pytest
from deal_analyzer import RentInput, analyse_listing, extract_listing
from deal_analyzer.analysis import SCHEMA_VERSION
from deal_analyzer.vision import Condition, PhotoAssessment, PhotoKind, VisionOutput

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from gen_report_schema import ADDITIVE_FIELDS, SCHEMA_PATH, breaking_changes, build_schema, render  # noqa: E402

BASELINES = ROOT / "tests" / "fixtures"
AD: dict[str, Any] = {
    "id": 90000001,
    "title": "Mieszkanie 2 pokoje, Testowo",
    "description": "Jasne mieszkanie na drugim pietrze. Cisza, spokoj, blisko komunikacji.",
    "createdAt": "2026-09-01T10:00:00Z",
    "modifiedAt": "2026-10-01T08:30:00Z",
    "adCategory": {"type": "SELL"},
    "characteristics": [
        {"key": "price", "value": "450000"},
        {"key": "m", "value": "48.5"},
        {"key": "rooms_num", "value": "2"},
        {"key": "rent", "value": "600"},
    ],
    "location": {
        "coordinates": {"latitude": 52.2297, "longitude": 21.0122},
        "address": {"city": {"name": "Testowo"}, "street": {"name": "Przykladowa", "number": "1"}},
    },
}
RENT = RentInput(monthly_rent_pln=Decimal("2600"), basis="asking", comparables=14)


def baseline(version: int) -> dict[str, Any]:
    return json.loads((BASELINES / f"report_schema_v{version}.json").read_text(encoding="utf-8"))


def test_report_schema_is_current() -> None:
    assert SCHEMA_PATH.exists(), "run: uv run python scripts/gen_report_schema.py"
    assert SCHEMA_PATH.read_text(encoding="utf-8") == render(build_schema()), (
        "DealAnalysis changed: run `uv run python scripts/gen_report_schema.py` and commit"
    )


def test_the_schema_is_deterministic_and_names_its_version() -> None:
    assert render(build_schema()) == render(build_schema())
    schema = build_schema()
    assert schema["x-schema-version"] == SCHEMA_VERSION
    assert schema["$id"] == f"urn:rentmonitor:deal-analysis:{SCHEMA_VERSION}"
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert "schema_version" in schema["required"]


def _walk(node: Any, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(node, dict):
        found.append((path, node))
        for key, value in node.items():
            found += _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += _walk(value, f"{path}[{i}]")
    return found


def test_money_is_always_a_string_never_a_number() -> None:
    """agents.md section 3: no float in returned money fields. Serialization mode turns every Decimal into a
    string, so no property anywhere in the schema may be a JSON number."""
    schema = build_schema()
    assert [p for p, n in _walk(schema) if n.get("type") == "number"] == []
    listing = schema["$defs"]["Listing"]["properties"]
    assert listing["price_pln"]["type"] == "string"
    assert listing["area_m2"]["type"] == "string"
    assert schema["properties"]["capex_used_pln"]["type"] == "string"


def test_a_field_that_can_be_not_computed_is_explicitly_nullable() -> None:
    schema = build_schema()
    assert {"type": "null"} in schema["properties"]["vision"]["anyOf"]
    max_bid = schema["$defs"]["MaxBidResult"]["properties"]
    nullable = [name for name, node in max_bid.items() if {"type": "null"} in node.get("anyOf", [])]
    assert nullable, "Max Bid and friends must say they can be null (unknown is not zero)"


def _analyses() -> list[dict[str, Any]]:
    listing = extract_listing(AD)
    vision = VisionOutput(
        condition=Condition.REFRESH,
        photos=(PhotoAssessment(kind=PhotoKind.INTERIOR),),
        capex_adjustment=Decimal("0.05"),
        rent_adjustment=Decimal("-0.02"),
    )
    plain = analyse_listing(listing, rent=RENT, risk_free=Decimal("0.055"))
    seen = analyse_listing(
        listing, rent=RENT, risk_free=Decimal("0.055"), vision=vision, model="m/x", prompt_version="v1"
    )
    thin = analyse_listing(
        listing, rent=RentInput(monthly_rent_pln=Decimal(0), comparables=0), risk_free=Decimal("0.055")
    )
    return [a.model_dump(mode="json") for a in (plain, seen, thin)]


@pytest.mark.parametrize("document", _analyses(), ids=["degraded", "with_vision", "refused_rent"])
def test_real_engine_results_validate_against_the_schema(document: dict[str, Any]) -> None:
    validator = jsonschema_rs.validator_for(build_schema())
    errors = [e.message for e in validator.iter_errors(document)][:5]
    assert errors == []


def test_a_result_of_another_schema_version_does_not_validate() -> None:
    document = copy.deepcopy(_analyses()[0])
    document["schema_version"] = SCHEMA_VERSION + 1
    assert not jsonschema_rs.validator_for(build_schema()).is_valid(document)


# ----------------------------------------------------------------------------------- compatibility
def test_every_released_version_has_a_frozen_baseline() -> None:
    for version in range(1, SCHEMA_VERSION + 1):
        assert (BASELINES / f"report_schema_v{version}.json").exists(), (
            f"add tests/fixtures/report_schema_v{version}.json (a copy of the schema as first released)"
        )
    assert baseline(SCHEMA_VERSION)["x-schema-version"] == SCHEMA_VERSION


def test_schema_version_bumped_on_breaking_change() -> None:
    """Within one `schema_version` the schema may only grow. A removed or renamed field, a narrowed type or
    enum, or a newly required field fails here until `SCHEMA_VERSION` is raised and a new baseline is added
    (docs/REPORT-SCHEMA.md)."""
    assert breaking_changes(baseline(SCHEMA_VERSION), build_schema()) == [], (
        "breaking change to DealAnalysis: bump SCHEMA_VERSION in deal_analyzer.analysis, regenerate, and "
        "add tests/fixtures/report_schema_v<new>.json"
    )


def _mutated(change: Any) -> dict[str, Any]:
    schema = copy.deepcopy(build_schema())
    change(schema)
    return schema


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda s: s["properties"].pop("warnings"), "$.warnings: removed or renamed"),
        (
            lambda s: s["$defs"]["Listing"]["properties"].update(
                price_pln_renamed=s["$defs"]["Listing"]["properties"].pop("price_pln")
            ),
            "$.listing.price_pln: removed or renamed",
        ),
        (
            lambda s: s["$defs"]["Listing"]["properties"]["price_pln"].update(type="integer"),
            "no longer allows",
        ),
        (
            lambda s: s["properties"]["vision"].update(anyOf=[{"$ref": "#/$defs/VisionRecord"}]),
            "no longer allows ['type:null']",
        ),
        (lambda s: s["$defs"]["Confidence"]["enum"].pop(), "enum no longer allows"),
        (
            lambda s: (
                s["properties"].update(extra_required={"type": "string"})
                or s["required"].append("extra_required")
            ),
            "$.extra_required: a new required field",
        ),
    ],
)
def test_breaking_changes_are_detected(change: Any, expected: str) -> None:
    found = breaking_changes(build_schema(), _mutated(change))
    assert any(expected in line for line in found), found


def test_a_field_that_becomes_required_is_breaking() -> None:
    before = copy.deepcopy(build_schema())
    before["required"].remove("warnings")  # as if `warnings` had been optional in the released version
    assert any("$.warnings: became required" in line for line in breaking_changes(before, build_schema()))


def test_every_serialized_field_is_required() -> None:
    """model_dump always writes defaults, so a reader can rely on them (docs/REPORT-SCHEMA.md)."""
    schema = build_schema()
    assert {"warnings", "engine_version", "assumptions_version"} <= set(schema["required"])
    for name, node in schema["$defs"].items():
        if "properties" in node:
            additive = ADDITIVE_FIELDS.get(name, frozenset())  # the only documented exception
            assert sorted(set(node["properties"]) - additive) == node["required"], name


def test_additive_changes_are_not_breaking() -> None:
    def add(schema: dict[str, Any]) -> None:
        schema["properties"]["a_new_optional_field"] = {"type": "string"}
        schema["$defs"]["Confidence"]["enum"].append("brand-new")
        schema["$defs"]["Listing"]["properties"]["another"] = {
            "anyOf": [{"type": "string"}, {"type": "null"}]
        }

    assert breaking_changes(build_schema(), _mutated(add)) == []


def test_g02_fields_are_additive_within_version_1() -> None:
    """RM-387: OCR text and equipment join `VisionRecord` without a version bump: they are optional in the
    schema, so a report stored before them still validates, and the v1 baseline reports nothing breaking."""
    schema = build_schema()
    required = set(schema["$defs"]["VisionRecord"]["required"])
    assert {"floor_plan_text", "notes", "equipment"}.isdisjoint(required)
    assert {"floor_plan_text", "notes", "equipment"} <= set(schema["$defs"]["VisionRecord"]["properties"])
    assert SCHEMA_VERSION == 1
    assert breaking_changes(baseline(1), schema) == []
    old_vision = {
        "model": "m", "prompt_version": "vision-v1", "condition": "good", "photos_total": 1,
        "photos_excluded": 0, "capex": None, "rent": None,
    }  # fmt: skip
    validator = jsonschema_rs.validator_for({"$defs": schema["$defs"], "$ref": "#/$defs/VisionRecord"})
    assert validator.is_valid(old_vision)
    assert not validator.is_valid(
        {**old_vision, "equipment": [{"item": "x"}]}
    )  # observation needs its fields
