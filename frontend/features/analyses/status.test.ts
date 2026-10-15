import { describe, expect, it } from "vitest";

import { type AuditState, hasReport, isActive, statusCopy } from "./status";

const ALL: readonly AuditState[] = [
  "queued",
  "running",
  "succeeded",
  "succeeded_degraded",
  "rejected",
  "failed_input",
  "failed_upstream",
  "failed_internal",
  "cancelled",
];

describe("statusCopy", () => {
  it("covers every state with a label, a tone and a statement about the credit", () => {
    for (const status of ALL) {
      const copy = statusCopy(status, null);
      expect(copy.label.length, status).toBeGreaterThan(2);
      expect(copy.credit, status).toMatch(/Raport/);
    }
  });

  it("says a failed or rejected analysis cost nothing, and a finished one did", () => {
    for (const status of [
      "rejected",
      "failed_input",
      "failed_upstream",
      "failed_internal",
      "cancelled",
    ] as const) {
      expect(statusCopy(status, null).credit).toBe("Raport nie został pobrany.");
    }
    expect(statusCopy("succeeded", null).credit).toBe("Raport został pobrany z konta.");
    expect(statusCopy("succeeded_degraded", null).credit).toBe("Raport został pobrany z konta.");
  });

  it("names the reason when the API gave a known code, and stays generic for an unknown one", () => {
    expect(statusCopy("rejected", "RENT_NOT_DEAL").label).toBe("To ogłoszenie wynajmu");
    expect(statusCopy("rejected", "FRACTIONAL_OWNERSHIP").label).toBe("Sprzedaż udziału");
    expect(statusCopy("failed_input", "LISTING_GONE").label).toBe("Ogłoszenie nieaktywne");
    expect(statusCopy("failed_upstream", "UPSTREAM_BLOCKED").label).toBe("Otodom zablokował pobranie");
    expect(statusCopy("rejected", "SOMETHING_NEW").label).toBe("Odrzucona");
    expect(statusCopy("failed_internal", null).label).toBe("Nie udało się");
  });

  it("uses a tone that matches the outcome", () => {
    expect(statusCopy("succeeded", null).tone).toBe("success");
    expect(statusCopy("succeeded_degraded", null).tone).toBe("warning");
    expect(statusCopy("failed_upstream", "UPSTREAM_BLOCKED").tone).toBe("danger");
    expect(statusCopy("running", null).tone).toBe("info");
  });

  it("tells finished from active", () => {
    expect(ALL.filter(hasReport)).toEqual(["succeeded", "succeeded_degraded"]);
    expect(ALL.filter(isActive)).toEqual(["queued", "running"]);
  });
});
