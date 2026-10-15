import { describe, expect, it } from "vitest";

import { fx } from "../test/fixtures";
import { SUCCEEDED_SCENARIOS } from "../test/scenarios";
import schema from "../../docs/deal-analysis.schema.json";
import { parseReport, REPORT_REQUIRED_KEYS, SUPPORTED_REPORT_VERSION } from "./report";
import { REPORT_SCHEMA } from "./report-schema.generated";
import { schemaErrors, unsupportedKeywords } from "./schema-check";

const resultOf = (scenario: string) =>
  (fx("GET /api/audits/{audit_id}", scenario).body as { result: unknown }).result;

describe("report parsing", () => {
  it("knows exactly the keys docs/deal-analysis.schema.json requires", () => {
    expect([...REPORT_REQUIRED_KEYS].sort()).toEqual([...schema.required].sort());
    expect(schema["x-schema-version"]).toBe(SUPPORTED_REPORT_VERSION);
  });

  it.each(SUCCEEDED_SCENARIOS)("accepts the %s result", (scenario) => {
    const parsed = parseReport(resultOf(scenario));
    expect(parsed.kind).toBe("ready");
  });

  it("says 'unsupported' for another version instead of guessing", () => {
    const next = { ...(resultOf("succeeded_torun") as object), schema_version: SUPPORTED_REPORT_VERSION + 1 };
    expect(parseReport(next)).toEqual({ kind: "unsupported", version: SUPPORTED_REPORT_VERSION + 1 });
    expect(parseReport({ listing: {} })).toEqual({ kind: "unsupported", version: null });
  });

  it("rejects a document of the right version that lacks a required section", () => {
    const rest = { ...(resultOf("succeeded_torun") as Record<string, unknown>) };
    delete rest["listing"];
    expect(parseReport(rest)).toMatchObject({ kind: "invalid", problems: ["/: missing listing"] });
    expect(parseReport(null)).toMatchObject({ kind: "invalid" });
    expect(parseReport("text")).toMatchObject({ kind: "invalid" });
    expect(parseReport([])).toMatchObject({ kind: "invalid" });
  });

  it("treats a degraded audit as a ready report with its warning visible", () => {
    const parsed = parseReport(resultOf("succeeded_degraded"));
    expect(parsed.kind).toBe("ready");
    if (parsed.kind === "ready") expect(parsed.report.warnings).toContain("vision_unavailable");
  });
});

/**
 * Audit F11: a report of the right version whose nested blocks are malformed used to be typed as DealAnalysis
 * and could throw while rendering. Each case below passed the old key-presence check.
 */
describe("a malformed report of a known version is invalid, not rendered", () => {
  type Doc = Record<string, Record<string, unknown>>;
  const good = () => structuredClone(resultOf("succeeded_torun")) as Doc;
  const block = (doc: Doc, key: string) => doc[key] ?? {};

  it.each([
    ["a required block is null", (r: Doc) => void (r["valuation"] = null as never)],
    ["a nested block is a string", (r: Doc) => void (r["cash_flow"] = "x" as never)],
    ["a number arrives as text", (r: Doc) => void (block(r, "listing")["rooms"] = "3")],
    ["an enum has an unknown value", (r: Doc) => void (block(r, "valuation")["verdict"] = "maybe")],
    ["warnings is not a list", (r: Doc) => void (r["warnings"] = "all good" as never)],
    ["a closed block has an unknown key", (r: Doc) => void (block(r, "listing")["injected"] = 1)],
  ])("%s", (_, mutate) => {
    const report = good();
    mutate(report);
    const parsed = parseReport(report);
    expect(parsed.kind).toBe("invalid");
    if (parsed.kind === "invalid") expect(parsed.problems.length).toBeGreaterThan(0);
  });

  it("the problems name paths, never values (nothing from the listing leaks into diagnostics)", () => {
    const report = good();
    block(report, "listing")["rooms"] = "secret-text-123";
    const parsed = parseReport(report);
    expect(parsed.kind === "invalid" && parsed.problems.join(" ")).not.toContain("secret-text-123");
  });
});

describe("the schema check", () => {
  it("understands every keyword the committed report schema uses", () => {
    expect(unsupportedKeywords(REPORT_SCHEMA)).toEqual([]);
    expect(unsupportedKeywords({ type: "object", oneOf: [] })).toEqual(["oneOf"]);
  });

  it("the generated schema is the committed one without documentation keywords", () => {
    // Documentation keywords are gone; property names such as `listing.title` and `listing.description` stay.
    expect(Object.keys(REPORT_SCHEMA)).not.toContain("title");
    expect(Object.keys(REPORT_SCHEMA.properties.valuation)).toEqual(["$ref"]);
    expect(Object.keys(REPORT_SCHEMA.$defs.Listing.properties)).toContain("description");
    expect(Object.keys(REPORT_SCHEMA.properties).sort()).toEqual(Object.keys(schema.properties).sort());
  });

  it("checks types, nullability, bounds, patterns, dates and references", () => {
    const s = {
      $defs: { Id: { type: "string", pattern: "^[a-z]+$", maxLength: 5 } },
      type: "object",
      additionalProperties: false,
      required: ["id", "n"],
      properties: {
        id: { $ref: "#/$defs/Id" },
        n: { type: "integer", minimum: 0, maximum: 9 },
        maybe: { anyOf: [{ type: "string" }, { type: "null" }] },
        at: { type: "string", format: "date-time" },
        list: { type: "array", maxItems: 2, items: { type: "number" } },
        fixed: { const: 1 },
        short: { type: "string", minLength: 2 },
        free: { type: "object", additionalProperties: { type: "boolean" } },
      },
    };
    expect(
      schemaErrors(s, { id: "abc", n: 3, maybe: null, at: "2026-10-15T10:00:00Z", list: [1.5] }),
    ).toEqual([]);
    expect(schemaErrors(s, { id: "ABC", n: 3 })).toEqual(["/id: wrong format"]);
    expect(schemaErrors(s, { id: "abcdef", n: 10 })).toEqual(["/id: too long", "/n: above the maximum"]);
    expect(schemaErrors(s, { id: "a", n: -1 })).toEqual(["/n: below the minimum"]);
    expect(schemaErrors(s, { id: "a", n: 1.5 })).toEqual(['/n: expected "integer", got number']);
    expect(schemaErrors(s, { id: "a", n: 1, maybe: 3 })).toEqual(["/maybe: matches no allowed shape"]);
    expect(schemaErrors(s, { id: "a", n: 1, at: "yesterday" })).toEqual(["/at: not a date-time"]);
    expect(schemaErrors(s, { id: "a", n: 1, list: [1, 2, "3"] })).toEqual([
      "/list: too many items",
      '/list/2: expected "number", got string',
    ]);
    expect(schemaErrors(s, { id: "a", n: 1, fixed: 2, short: "x" })).toEqual([
      "/fixed: must be 1",
      "/short: too short",
    ]);
    expect(schemaErrors(s, { id: "a", n: 1, free: { ok: true, bad: "no" } })).toEqual([
      '/free/bad: expected "boolean", got string',
    ]);
    expect(schemaErrors(s, { n: 1, extra: true })).toEqual(["/: missing id", "/: unexpected extra"]);
    expect(schemaErrors({ enum: ["a"] }, "b")).toEqual(["/: not an allowed value"]);
  });

  it("stops collecting at 20 problems for a hostile answer", () => {
    const s = { type: "array", items: { type: "string" } };
    expect(
      schemaErrors(
        s,
        Array.from({ length: 500 }, () => 1),
      ),
    ).toHaveLength(20);
  });

  it("refuses a reference it cannot resolve instead of skipping it", () => {
    expect(() => schemaErrors({ $ref: "https://example.test/x" }, 1)).toThrow(/unsupported/);
    expect(() => schemaErrors({ $ref: "#/$defs/Missing" }, 1)).toThrow(/unknown/);
  });
});
