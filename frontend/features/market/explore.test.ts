import { describe, expect, it } from "vitest";

import { MAX_COMPARED, readExplore, sortPlaces, toggleCompared, writeExplore } from "./explore";
import type { OverviewPlace } from "./queries";

const place = (id: string, name: string, ppm2: string | null, sufficient = true): OverviewPlace => ({
  location_id: id,
  name,
  data_status: "fresh",
  last_successful_refresh_at: null,
  latest_summary_date: null,
  median_rent_pln: ppm2,
  median_ppm2: ppm2,
  priced_count: 12,
  sufficient,
  withheld_reason: null,
  mapping: "mapped",
  relation: "gmina",
  gmina_teryt: "1007013",
  powiat_name: null,
  wojewodztwo_name: null,
});

describe("address state", () => {
  it("falls back to defaults for anything outside the vocabulary", () => {
    const s = readExplore(new URLSearchParams("view=evil&metric=x&sort=;&sel=../../x&ids=a,b,A,a,c,d,e,f"));
    expect(s).toEqual({ view: "map", metric: "ppm2", sort: "name", sel: null, ids: ["a", "b", "c", "d"] });
  });
  it("round-trips and writes only what differs from the default", () => {
    const s = { view: "compare", metric: "rent", sort: "ppm2", sel: "torun", ids: ["a", "b"] } as const;
    expect(readExplore(writeExplore(s))).toEqual(s);
    expect(writeExplore(readExplore(new URLSearchParams())).toString()).toBe("");
  });
  it("caps the comparison and toggles", () => {
    expect(toggleCompared(["a"], "a")).toEqual([]);
    const full = Array.from({ length: MAX_COMPARED }, (_, i) => `p${i}`);
    expect(toggleCompared(full, "x")).toEqual(full);
  });
});

describe("sorting", () => {
  const places = [
    place("a", "Łódź", "40"),
    place("b", "Gdańsk", null),
    place("c", "Kielce", "55"),
    place("d", "Elbląg", "99", false),
  ];
  it("sorts names by Polish collation", () => {
    expect(sortPlaces(places, "name").map((p) => p.name)).toEqual(["Elbląg", "Gdańsk", "Kielce", "Łódź"]);
  });
  it("puts missing and withheld values last, never as zero", () => {
    expect(sortPlaces(places, "ppm2").map((p) => p.location_id)).toEqual(["c", "a", "d", "b"]);
  });
});
