import { describe, expect, it } from "vitest";

import { createApi, unwrap } from "../api/client";
import { operationKeys, validateResponse } from "./contract";
import { unmatched, useScenario } from "./handlers";
import { SCENARIO_NAMES, SCENARIOS, SUCCEEDED_AUDITS, type Reply } from "./scenarios";

const api = createApi({ baseUrl: window.location.origin });

describe("scenario registry", () => {
  it("has the states the screens are built against", () => {
    expect(SCENARIO_NAMES).toEqual(
      expect.arrayContaining([
        "firstVisit",
        "empty",
        "loaded",
        "pending",
        "degraded",
        "rejectedRent",
        "rejectedFractional",
        "failedUpstream",
        "failedInput",
        "insufficientCredits",
        "breakerOpen",
        "billingDisabled",
        "sessionExpired",
        "offline",
        "reconnecting",
      ]),
    );
  });

  it("only routes operations that exist, and every static reply matches the documented schema", () => {
    const known = new Set(operationKeys());
    for (const scenario of Object.values(SCENARIOS)) {
      for (const route of scenario.routes) {
        expect(known.has(route.operation), `${scenario.name}: ${route.operation}`).toBe(true);
        const reply = route.reply;
        if (typeof reply === "function" || reply.networkError === true || reply.text !== undefined) continue;
        expect(
          validateResponse(route.operation, reply.status, reply.body ?? null),
          `${scenario.name}: ${route.operation}`,
        ).toEqual([]);
      }
    }
  });

  it("builds the loaded state from five distinct audits, newest first", () => {
    expect(SUCCEEDED_AUDITS).toHaveLength(5);
    expect(new Set(SUCCEEDED_AUDITS.map((a) => a.audit_id)).size).toBe(5);
    const times = SUCCEEDED_AUDITS.map((a) => a.created_at);
    expect(times).toEqual([...times].sort().reverse());
  });

  it("serves a scenario through the real client", async () => {
    useScenario("loaded");
    const page = unwrap(await api.GET("/api/audits"));
    expect(page.items).toHaveLength(5);
    const first = page.items[0];
    expect(first).toBeDefined();
    const detail = unwrap(
      await api.GET("/api/audits/{audit_id}", { params: { path: { audit_id: first?.audit_id ?? "" } } }),
    );
    expect(detail.otodom_id).toBe(first?.otodom_id);
  });

  it("answers a request the scenario has no route for with a loud failure, not an empty success", async () => {
    useScenario("empty");
    const response = await fetch(`${window.location.origin}/api/admin/jobs`);
    expect(response.status).toBe(599);
    expect(unmatched.splice(0)).toEqual(["GET /api/admin/jobs (scenario empty)"]);
  });

  it("can refuse every request like a dropped connection", async () => {
    useScenario("offline");
    await expect(api.GET("/api/me")).rejects.toMatchObject({ kind: "network" });
  });

  it("keeps replies framework-neutral (no MSW types in the registry)", () => {
    const reply: Reply = { status: 200 };
    expect(reply.status).toBe(200);
  });
});
