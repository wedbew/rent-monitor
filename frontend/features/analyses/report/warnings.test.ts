import { describe, expect, it } from "vitest";

import { orderedWarnings, warningCopy } from "./warnings";

describe("warningCopy", () => {
  it("says what a known warning means and what to do", () => {
    const copy = warningCopy("capex_prices_are_placeholders");
    expect(copy.material).toBe(true);
    expect(copy.title).toBe("Koszt remontu jest wstępny");
    expect(copy.check.length).toBeGreaterThan(20);
  });

  it("never hides a code it does not know: it is shown generically, with the code", () => {
    const copy = warningCopy("something_new");
    expect(copy.title).toBe("Dodatkowe zastrzeżenie silnika");
    expect(copy.check).toContain("something_new");
    expect(copy.material).toBe(false);
  });

  it("covers every code the engine can emit today", () => {
    for (const code of [
      "vision_unavailable",
      "capex_prices_are_placeholders",
      "admin_fee_missing",
      "rent_refused_too_few_comparables",
      "rent_thin_market",
      "size_window_widened",
      "comparables_dropped_implausible",
      "irr_not_computable",
      "legal_class_needs_review",
      "city_missing",
      "street_missing",
      "coordinates_missing",
      "coordinates_invalid",
      "coordinates_outside_poland",
      "building_type_missing",
      "heating_missing",
      "windows_missing",
    ]) {
      expect(warningCopy(code).title, code).not.toBe("Dodatkowe zastrzeżenie silnika");
    }
  });
});

describe("orderedWarnings", () => {
  it("removes duplicates and puts the material ones first, keeping the engine's order otherwise", () => {
    const ordered = orderedWarnings([
      "heating_missing",
      "vision_unavailable",
      "heating_missing",
      "windows_missing",
      "admin_fee_missing",
    ]).map((w) => w.code);
    expect(ordered).toEqual([
      "vision_unavailable",
      "admin_fee_missing",
      "heating_missing",
      "windows_missing",
    ]);
  });

  it("is empty for no warnings", () => {
    expect(orderedWarnings([])).toEqual([]);
  });
});
