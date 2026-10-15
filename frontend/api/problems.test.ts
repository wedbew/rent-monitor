import { describe, expect, it } from "vitest";

import { OPENAPI } from "../test/contract";
import { ApiError, asProblem, TransportError } from "./errors";
import { describeProblem, describeTransport, isProblemCode, PROBLEM_COPY, TRANSPORT_COPY } from "./problems";

const ACTIONS = new Set([
  "none",
  "retry",
  "waitAndRetry",
  "signIn",
  "buyReports",
  "verifyEmail",
  "fixInput",
  "openAnalysis",
  "contactSupport",
  "useEmailLink",
  "requestNewLink",
  "reload",
  "goBack",
]);

function documentedCodes(): string[] {
  const schema = OPENAPI.components.schemas["ProblemCode"] as { enum: string[] };
  return schema.enum;
}

describe("problem copy", () => {
  it("covers every code in docs/openapi.json, so a new API code fails here", () => {
    expect(Object.keys(PROBLEM_COPY).sort()).toEqual([...documentedCodes()].sort());
  });

  it("is Polish, complete and points at a known action", () => {
    for (const [code, copy] of Object.entries(PROBLEM_COPY)) {
      expect(copy.title.length, code).toBeGreaterThan(3);
      expect(copy.detail.endsWith("."), code).toBe(true);
      expect(ACTIONS.has(copy.action), code).toBe(true);
      expect(copy.title, code).not.toMatch(/\b(error|failed|invalid)\b/i);
    }
  });

  it("tells the user when a failed analysis cost nothing", () => {
    for (const code of [
      "RENT_NOT_DEAL",
      "FRACTIONAL_OWNERSHIP",
      "LISTING_GONE",
      "UPSTREAM_BLOCKED",
      "CONTEXT_UNAVAILABLE",
    ] as const) {
      expect(PROBLEM_COPY[code].detail, code).toContain("nie został pobrany");
    }
  });

  it("keeps the request id for support and the retry delay", () => {
    expect(describeProblem("RATE_LIMITED", { requestId: "abc", retryAfterS: 30 })).toMatchObject({
      requestId: "abc",
      retryAfterS: 30,
      action: "waitAndRetry",
    });
    expect(describeProblem("NOT_FOUND").requestId).toBeNull();
  });

  it("describes failures that never reach the API", () => {
    expect(Object.keys(TRANSPORT_COPY).sort()).toEqual(["aborted", "invalid-response", "network", "timeout"]);
    expect(describeTransport("network").action).toBe("retry");
  });
});

describe("problem parsing", () => {
  const body = {
    type: "urn:rentmonitor:problem:NOT_FOUND",
    title: "Audit not found",
    status: 404,
    code: "NOT_FOUND",
    instance: "/api/audits/x",
    request_id: "r1",
  };

  it("recognises a problem body and rejects anything else", () => {
    expect(asProblem(body)?.code).toBe("NOT_FOUND");
    expect(asProblem({ ...body, code: "SOMETHING_NEW" })).toBeNull();
    expect(asProblem("<html>502</html>")).toBeNull();
    expect(asProblem(null)).toBeNull();
    expect(isProblemCode("QUOTA_EXHAUSTED")).toBe(true);
    expect(isProblemCode("toString")).toBe(false);
  });

  it("exposes code and request id on ApiError", () => {
    const error = new ApiError(404, asProblem(body));
    expect(error.code).toBe("NOT_FOUND");
    expect(error.requestId).toBe("r1");
    expect(new ApiError(502, null).code).toBeNull();
    expect(new TransportError("timeout").kind).toBe("timeout");
  });
});
