import { describe, expect, it } from "vitest";

import { attributeLabel, floorSummary } from "./attributes";

describe("attributeLabel", () => {
  it("maps each attribute by its own table", () => {
    expect(attributeLabel("heating", "gas")).toBe("Gazowe");
    expect(attributeLabel("heating", "urban")).toBe("Miejskie");
    expect(attributeLabel("windows", "plastic")).toBe("PCV");
    expect(attributeLabel("windows", "wooden")).toBe("Drewniane");
    expect(attributeLabel("buildingType", "block")).toBe("Blok");
    expect(attributeLabel("buildingType", "tenement")).toBe("Kamienica");
  });

  it("reads the same raw word differently under different attributes", () => {
    expect(attributeLabel("heating", "other")).toBe("Inne");
    // `other` is not a window type: it is not silently borrowed from heating
    expect(attributeLabel("windows", "other")).toBe("nierozpoznana wartość");
  });

  it("formats storeys: ground, numbered, higher than ten, attic, cellar, bare numbers", () => {
    expect(attributeLabel("floor", "ground_floor")).toBe("Parter");
    expect(attributeLabel("floor", "floor_0")).toBe("Parter");
    expect(attributeLabel("floor", "0")).toBe("Parter");
    expect(attributeLabel("floor", "floor_1")).toBe("1. piętro");
    expect(attributeLabel("floor", "floor_10")).toBe("10. piętro");
    expect(attributeLabel("floor", "2")).toBe("2. piętro");
    expect(attributeLabel("floor", "floor_higher_than_10")).toBe("Powyżej 10. piętra");
    expect(attributeLabel("floor", "garret")).toBe("Poddasze");
    expect(attributeLabel("floor", "cellar")).toBe("Suterena");
  });

  it("returns null for a missing value, and a readable fallback, never the raw code, for an unknown one", () => {
    for (const missing of [null, undefined, "", "   "]) {
      expect(attributeLabel("heating", missing)).toBeNull();
      expect(attributeLabel("floor", missing)).toBeNull();
    }
    for (const kind of ["heating", "windows", "buildingType", "floor"] as const) {
      const label = attributeLabel(kind, "geothermal_something");
      expect(label).toBe("nierozpoznana wartość");
      expect(label).not.toMatch(/geothermal|_/);
    }
  });

  it("does not resolve prototype keys", () => {
    expect(attributeLabel("heating", "constructor")).toBe("nierozpoznana wartość");
    expect(attributeLabel("floor", "__proto__")).toBe("nierozpoznana wartość");
  });

  it("is case and whitespace tolerant", () => {
    expect(attributeLabel("heating", " GAS ")).toBe("Gazowe");
  });
});

describe("floorSummary", () => {
  it("says 'of N' only for a numbered storey, and never repeats the word or leaks the code", () => {
    expect(floorSummary("floor_1", 4)).toBe("1. piętro z 4");
    expect(floorSummary("floor_1", 1)).toBe("1. piętro z 1");
    expect(floorSummary("3", null)).toBe("3. piętro");
    expect(floorSummary("ground_floor", 5)).toBe("Parter");
    expect(floorSummary("garret", 5)).toBe("Poddasze");
    for (const raw of ["floor_1", "ground_floor", "3"]) {
      expect(floorSummary(raw, 4)).not.toMatch(/floor|piętro piętro|_/);
    }
  });

  it("omits an unreadable or missing storey from the summary", () => {
    expect(floorSummary(null, 4)).toBeNull();
    expect(floorSummary("weird", 4)).toBeNull();
  });
});
