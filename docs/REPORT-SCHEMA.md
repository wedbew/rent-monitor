# The report schema (`DealAnalysis`)

`GET /api/audits/{id}` returns the engine's canonical result in `result`. OpenAPI types that field as an opaque
object on purpose: an audit keeps the shape of the `schema_version` it was made with, and old audits stay
readable. The shape itself is published as [`deal-analysis.schema.json`](deal-analysis.schema.json) (JSON Schema
2020-12), generated from the Pydantic models by `scripts/gen_report_schema.py` and checked by
`tests/unit/test_report_schema.py` (RM-266). The report page types its adapters from this file and refuses a
`schema_version` it does not know (it shows "unsupported version", never a guess).

## What the schema promises

- **Money is a string.** Every `Decimal` (PLN amounts, rates, ratios) is a JSON string such as `"450000.00"`; no
  property anywhere is a JSON number. Parse with a decimal type, never `Number()`.
- **Unknown is not zero.** A value the engine could not compute (for example Max Bid when the rent was refused) is
  explicitly nullable (`anyOf: [..., null]`). Render it as "not computed".
- **Serialized fields are required.** `model_dump` always writes every field, defaults included, so every property
  in the schema is `required` and a reader may rely on it being present.
- **One version per document.** `schema_version` is a `const` in the schema; a document of another version does not
  validate against it.

## Compatibility rule

Within one `schema_version` the schema may only **grow**:

| Change | Same version? |
|---|---|
| a new optional field, a new nullable field, a new enum value, a new definition | yes |
| a removed or renamed field | **no**: bump |
| a changed JSON type, or a type no longer allowed (for example `null`) | **no**: bump |
| a narrowed enum | **no**: bump |
| a field that becomes required, or a new required field | **no**: bump |

`test_schema_version_bumped_on_breaking_change` compares the generated schema with the frozen baseline of the
current version (`tests/fixtures/report_schema_v<N>.json`, a copy of the schema as first released) and lists
what broke. Readers written against version N keep working for every N document, old or new.

## Additive fields (optional within a version)

A field added after a version was first released cannot be `required`: reports stored before it do not
have it. `ADDITIVE_FIELDS` in `scripts/gen_report_schema.py` names them (per definition); they are written by
`model_dump` but left out of `required`, and a reader treats an absent one as its default. An entry is removed
only together with a version bump. Current entries (version 1):

- `VisionRecord.floor_plan_text` (string or null), `VisionRecord.notes` (string or null) and
  `VisionRecord.equipment` (array of `EquipmentObservation`, default empty), RM-387 / G-02. The report now keeps
  the OCR transcription of floor plans and the equipment the vision model saw: `item`, `media_ordinal` (the
  position in the selected media list, photos then plans, same as the media manifest `ordinal`; null when the
  model named no usable image), `confidence` (decimal string, 0 to 1), `provenance` (`photo | floor_plan |
  unattributed`) and `sale_status` (`included | visible_only | unknown`). It is evidence, never an input to a
  number; a report loaded later needs no second model call. Prompt version `vision-v2`.
  `LEGAL[images]`, `LEGAL[republication]`, `GDPR[processor]`.

The SPA keeps rendering version 1 (it ignores the new fields); panels for them are G-02b.

## Changing the engine's output

1. Change the models in `apps/deal_analyzer`. Additive: keep `SCHEMA_VERSION`. Breaking: raise it in
   `deal_analyzer/analysis.py`.
2. `uv run python scripts/gen_report_schema.py` and commit `docs/deal-analysis.schema.json`.
3. After a bump, copy the new schema to `tests/fixtures/report_schema_v<new>.json` (never edit an older baseline) and
   regenerate `data/api-samples` and the frontend fixtures.
4. Golden `DealAnalysis` snapshots: unchanged, or each diff explained in the PR.
