import { describe, expect, it } from "vitest";

import { REPORT_REQUIRED_KEYS, SUPPORTED_REPORT_VERSION, parseReport } from "../../../api/report";
import { SUCCEEDED_AUDITS } from "../../../test/scenarios";
import { CONDITION, GRADE, TITLE_FORM, VERDICT } from "./copy";

describe("report vocabulary", () => {
  it("has words for every verdict, grade, condition and title form", () => {
    expect(Object.keys(VERDICT).sort()).toEqual(["buy_at_asking", "insufficient_data", "negotiate", "pass"]);
    expect(Object.keys(GRADE).sort()).toEqual(["A", "B", "C", "D", "E", "N"]);
    expect(Object.keys(CONDITION).sort()).toEqual(["good", "refresh", "renovation", "shell", "unknown"]);
    expect(Object.keys(TITLE_FORM)).toHaveLength(4);
  });
});

describe("every captured result is renderable by this build", () => {
  it("parses as the supported version with all required parts", () => {
    for (const audit of SUCCEEDED_AUDITS) {
      const parsed = parseReport(audit.result);
      expect(parsed.kind, audit.audit_id).toBe("ready");
    }
    expect(SUPPORTED_REPORT_VERSION).toBe(1);
    expect(REPORT_REQUIRED_KEYS.length).toBeGreaterThan(10);
  });
});
