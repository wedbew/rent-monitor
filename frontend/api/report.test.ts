import { describe, expect, it } from "vitest";

import { fx } from "../test/fixtures";
import { SUCCEEDED_SCENARIOS } from "../test/scenarios";
import schema from "../../docs/deal-analysis.schema.json";
import { parseReport, REPORT_REQUIRED_KEYS, SUPPORTED_REPORT_VERSION } from "./report";

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
    expect(parseReport(rest)).toEqual({ kind: "invalid" });
    expect(parseReport(null)).toEqual({ kind: "invalid" });
    expect(parseReport("text")).toEqual({ kind: "invalid" });
  });

  it("treats a degraded audit as a ready report with its warning visible", () => {
    const parsed = parseReport(resultOf("succeeded_degraded"));
    expect(parsed.kind).toBe("ready");
    if (parsed.kind === "ready") expect(parsed.report.warnings).toContain("vision_unavailable");
  });
});
