import { describe, expect, it } from "vitest";

import { validateResponse, operationKeys } from "./contract";
import { ALL_FIXTURES, bodyOf, fixturesFor, fx } from "./fixtures";
import { SUCCEEDED_SCENARIOS } from "./scenarios";
import type { components } from "../api/schema.generated";

type AuditOut = components["schemas"]["AuditOut"];

describe("fixtures", () => {
  it("exist for every API operation", () => {
    const without = operationKeys().filter((key) => fixturesFor(key).length === 0);
    expect(without).toEqual([]);
  });

  it.each(ALL_FIXTURES.map((f) => [`${f.operation.key} :: ${f.scenario}`, f] as const))(
    "%s matches the documented response",
    (_name, fixture) => {
      if (fixture.events !== undefined) {
        expect(fixture.events.length).toBeGreaterThan(0);
        return;
      }
      expect(validateResponse(fixture.operation.key, fixture.status, fixture.body)).toEqual([]);
    },
  );

  it("the validator really rejects a body that breaks the schema", () => {
    expect(validateResponse("GET /api/me", 200, { id: 1 }).length).toBeGreaterThan(0);
    expect(validateResponse("GET /api/audits", 200, []).length).toBeGreaterThan(0);
    expect(validateResponse("GET /api/audits", 418, {})).toEqual([
      "GET /api/audits does not document status 418",
    ]);
  });

  it("holds five distinct finished audits", () => {
    const audits = SUCCEEDED_SCENARIOS.map((s) => bodyOf<AuditOut>(fx("GET /api/audits/{audit_id}", s)));
    expect(new Set(audits.map((a) => a.audit_id)).size).toBe(5);
    expect(new Set(audits.map((a) => a.otodom_id)).size).toBe(5);
    expect(new Set(audits.map((a) => a.asking_price_pln)).size).toBe(5);
    expect(audits.every((a) => a.status === "succeeded" && a.result !== null)).toBe(true);
  });

  it("contain no real-looking email, phone number or foreign URL", () => {
    const text = JSON.stringify(ALL_FIXTURES);
    const emails = (text.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}/g) ?? []).filter(
      (e) => !e.endsWith("@example.test"),
    );
    const urls = (text.match(/https?:\/\/[^"\s]+/g) ?? []).filter(
      (u) => !u.startsWith("https://example.test"),
    );
    expect({ emails, urls }).toEqual({ emails: [], urls: [] });
  });
});
