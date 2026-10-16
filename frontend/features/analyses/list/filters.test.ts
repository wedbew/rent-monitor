import { describe, expect, it } from "vitest";

import {
  apiQuery,
  DEFAULT_FILTERS,
  hasActiveFilters,
  readFilters,
  STATUS_GROUPS,
  writeFilters,
} from "./filters";

const read = (search: string) => readFilters(new URLSearchParams(search));

describe("readFilters", () => {
  it("reads the defaults from a plain address", () => {
    expect(read("")).toEqual(DEFAULT_FILTERS);
  });

  it("reads each known value", () => {
    expect(read("view=table&status=ready&grade=E&q=IDLST0011")).toEqual({
      view: "table",
      status: "ready",
      grade: "E",
      q: "IDLST0011",
      saved: false,
    });
  });

  it("ignores anything outside the vocabulary: it is never sent to the API", () => {
    expect(read("view=weird&status=bogus&grade=Z&q=%3Cscript%3E")).toEqual(DEFAULT_FILTERS);
    expect(read("q=" + "A".repeat(21))).toEqual(DEFAULT_FILTERS);
    expect(read("q=a%20b").q).toBe("");
    expect(read("status=ready,failed").status).toBe("");
  });

  it("trims the search", () => {
    expect(read("q=%20ID4abcd%20").q).toBe("ID4abcd");
  });
});

describe("writeFilters", () => {
  it("writes only what differs from the default, so the plain list has a plain address", () => {
    expect(writeFilters(DEFAULT_FILTERS).toString()).toBe("");
    expect(writeFilters({ ...DEFAULT_FILTERS, status: "failed" }).toString()).toBe("status=failed");
    expect(
      writeFilters({ ...DEFAULT_FILTERS, view: "table", status: "ready", grade: "A", q: "ID1" }).toString(),
    ).toBe("view=table&status=ready&grade=A&q=ID1");
    expect(writeFilters({ ...DEFAULT_FILTERS, saved: true }).toString()).toBe("saved=1");
  });

  it("reads the saved scope only from saved=1", () => {
    expect(read("saved=1").saved).toBe(true);
    for (const value of ["0", "true", "", "yes"]) expect(read(`saved=${value}`).saved).toBe(false);
  });

  it("round-trips", () => {
    const filters = { view: "table", status: "active", grade: "N", q: "ID4x", saved: true } as const;
    expect(read(writeFilters(filters).toString())).toEqual(filters);
  });
});

describe("apiQuery", () => {
  it("sends a status group as its member statuses and nothing for an unset filter", () => {
    expect(apiQuery(DEFAULT_FILTERS, 24, null)).toEqual({ limit: 24 });
    expect(apiQuery({ ...DEFAULT_FILTERS, status: "ready" }, 24, "abc")).toEqual({
      limit: 24,
      cursor: "abc",
      status: ["succeeded", "succeeded_degraded"],
    });
    expect(apiQuery({ ...DEFAULT_FILTERS, grade: "E", q: "ID1" }, 24, null)).toEqual({
      limit: 24,
      grade: "E",
      q: "ID1",
    });
  });

  it("covers every audit state exactly once across the groups", () => {
    const all = Object.values(STATUS_GROUPS).flat();
    expect(new Set(all).size).toBe(all.length);
    expect(all).toHaveLength(9);
  });
});

describe("hasActiveFilters", () => {
  it("is about filters, not the view", () => {
    expect(hasActiveFilters({ ...DEFAULT_FILTERS, view: "table" })).toBe(false);
    expect(hasActiveFilters({ ...DEFAULT_FILTERS, q: "ID1" })).toBe(true);
  });
});
