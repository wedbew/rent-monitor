"""Write the JSON Schema of the canonical result to `docs/deal-analysis.schema.json` (RM-266, FE-A3).

`DealAnalysis` is what `GET /api/audits/{id}` returns in `result`; the OpenAPI document keeps that field
opaque on purpose (it holds whichever `schema_version` the audit was made with), so the report page types it
from this file instead. The schema is generated in *serialization* mode: money and other `Decimal` values
are JSON **strings**, never numbers, and a field the engine could not compute is explicitly nullable.

Run `uv run python scripts/gen_report_schema.py` after changing `deal_analyzer`'s output models. A test fails
when the committed file and the models disagree, and another when the change is breaking but `SCHEMA_VERSION`
did not move (compatibility rule: `docs/REPORT-SCHEMA.md`).
"""

import json
import sys
from pathlib import Path
from typing import Any

from deal_analyzer.analysis import SCHEMA_VERSION, DealAnalysis

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "docs" / "deal-analysis.schema.json"
SCHEMA_ID = "urn:rentmonitor:deal-analysis"
Schema = dict[str, Any]


def build_schema() -> Schema:
    schema = DealAnalysis.model_json_schema(mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"{SCHEMA_ID}:{SCHEMA_VERSION}"
    schema["x-schema-version"] = SCHEMA_VERSION
    version = schema["properties"]["schema_version"]
    version["const"] = SCHEMA_VERSION  # a document validates against the schema of its own version only
    schema["required"] = sorted({*schema.get("required", []), "schema_version"})
    return schema


def render(schema: Schema) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------------------------ compatibility
def _resolve(schema: Schema, node: Schema) -> Schema:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return schema["$defs"][ref.removeprefix("#/$defs/")]
    return node


def _variants(node: Schema) -> list[Schema]:
    return list(node["anyOf"]) if "anyOf" in node else [node]


def _signature(schema: Schema, node: Schema) -> set[str]:
    """What a reader can rely on at this node: its JSON types, `$ref` target names and enum values."""
    out: set[str] = set()
    for variant in _variants(node):
        if "$ref" in variant:
            out.add("ref:" + variant["$ref"].removeprefix("#/$defs/"))
            continue
        out.add("type:" + str(variant.get("type", "any")))
        out.update("enum:" + json.dumps(v) for v in variant.get("enum", []))
        if "items" in variant:
            out.update("item:" + s for s in _signature(schema, variant["items"]))
    return out


def breaking_changes(old: Schema, new: Schema) -> list[str]:
    """What `new` breaks for a reader written against `old`. Additive changes (new optional fields, a wider
    enum) are fine within one `schema_version`; anything listed here needs a new version."""
    problems: list[str] = []
    seen: set[str] = set()

    def visit(path: str, o: Schema, n: Schema) -> None:
        o, n = _resolve(old, o), _resolve(new, n)
        if path in seen:
            return
        seen.add(path)
        gone_values = [v for v in o.get("enum", []) if v not in n.get("enum", o.get("enum", []))]
        if gone_values:
            problems.append(f"{path}: enum no longer allows {gone_values}")
        o_props, n_props = o.get("properties", {}), n.get("properties", {})
        for name in o_props:
            if name not in n_props:
                problems.append(f"{path}.{name}: removed or renamed")
                continue
            before, after = _signature(old, o_props[name]), _signature(new, n_props[name])
            gone = sorted(s for s in before - after if not s.startswith("ref:"))
            if gone:
                problems.append(f"{path}.{name}: no longer allows {gone}")
            if {s for s in before if s.startswith("ref:")} != {s for s in after if s.startswith("ref:")}:
                problems.append(f"{path}.{name}: points at a different definition")
            for ov, nv in zip(_variants(o_props[name]), _variants(n_props[name]), strict=False):
                visit(f"{path}.{name}", ov, nv)
        for name in set(n.get("required", [])) - set(o.get("required", [])):
            if name in o_props:
                problems.append(f"{path}.{name}: became required")
        for name in set(n_props) - set(o_props):
            if name in n.get("required", []):
                problems.append(f"{path}.{name}: a new required field")
        if "items" in o and "items" in n:
            visit(f"{path}[]", o["items"], n["items"])

    visit("$", old, new)
    return problems


def main() -> int:
    SCHEMA_PATH.write_text(render(build_schema()), encoding="utf-8")
    print(f"wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
