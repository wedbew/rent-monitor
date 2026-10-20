import { describe, expect, it } from "vitest";

import {
  cleanSearch,
  cohortOptions,
  DEFAULT_SELECTION,
  listAddress,
  placeAddress,
  readSelection,
  writeSelection,
} from "./filters";

describe("the selection in the address", () => {
  it("reads defaults from a plain address and ignores values outside the closed vocabulary", () => {
    expect(readSelection(new URLSearchParams())).toEqual(DEFAULT_SELECTION);
    expect(readSelection(new URLSearchParams("series=deed&cohort=rooms_9&days=7"))).toEqual(
      DEFAULT_SELECTION,
    );
    expect(readSelection(new URLSearchParams("series=additions&cohort=size_30_45&days=365"))).toEqual({
      series: "additions",
      cohort: "size_30_45",
      days: 365,
    });
  });

  it("writes only non-default values and carries the search", () => {
    expect(writeSelection(DEFAULT_SELECTION, "").toString()).toBe("");
    expect(writeSelection({ series: "additions", cohort: "rooms_2", days: 30 }, "gd").toString()).toBe(
      "series=additions&cohort=rooms_2&days=30&q=gd",
    );
  });

  it("round-trips every combination it can write", () => {
    for (const series of ["cohort", "additions"] as const)
      for (const days of [30, 90, 365] as const) {
        const selection = { series, cohort: "rooms_3", days } as const;
        expect(readSelection(writeSelection(selection, ""))).toEqual(selection);
      }
  });
});

describe("the search text", () => {
  it("is trimmed, bounded and free of control characters", () => {
    expect(cleanSearch("  Toruń ")).toBe("Toruń");
    expect(cleanSearch(null)).toBe("");
    expect(cleanSearch("   ")).toBe("");
    expect(cleanSearch("x".repeat(61))).toBe("");
    expect(cleanSearch("a\u0000b")).toBe("");
  });

  it("is encoded into the addresses, never concatenated", () => {
    expect(listAddress("")).toBe("/app/market?view=list");
    expect(listAddress("zielona góra")).toBe("/app/market?view=list&q=zielona+g%C3%B3ra");
    expect(placeAddress("torun", "a&b=c")).toBe("/app/market/torun?q=a%26b%3Dc");
    expect(placeAddress("a/b", "")).toBe("/app/market/a%2Fb");
  });
});

describe("the cohorts offered", () => {
  it("are those the API published, plus the one already chosen, in a fixed order", () => {
    expect(cohortOptions(["size_45_60", "all", "rooms_2", "unknown_key"], "all").map((o) => o.value)).toEqual(
      ["all", "rooms_2", "size_45_60"],
    );
    expect(cohortOptions(["all"], "rooms_3").map((o) => o.value)).toEqual(["all", "rooms_3"]);
  });
});
