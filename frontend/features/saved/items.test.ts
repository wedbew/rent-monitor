import { describe, expect, it } from "vitest";

import { noteLength, readSaved } from "./items";

const row = {
  otodom_id: "IDFIX0001",
  note: "tekst",
  latest_audit_id: "00000000-0000-4000-8000-000000000001",
  created_at: "2026-10-01T10:00:00Z",
};

describe("readSaved", () => {
  it("reads rows, keeping a null note and a null analysis", () => {
    expect(readSaved([row, { ...row, otodom_id: "IDFIX0002", note: null, latest_audit_id: null }])).toEqual([
      expect.objectContaining({ otodomId: "IDFIX0001", note: "tekst" }),
      expect.objectContaining({ otodomId: "IDFIX0002", note: null, latestAuditId: null }),
    ]);
  });

  it("is null for a non-list or a list of only malformed rows; an empty list is an answer", () => {
    for (const v of [null, {}, "x", 4]) expect(readSaved(v)).toBeNull();
    expect(readSaved([{ otodom_id: 1 }, null])).toBeNull();
    expect(readSaved([])).toEqual([]);
  });

  it("drops a row whose id or link target could not be trusted in an address", () => {
    const bad = [
      { ...row, otodom_id: "../etc" },
      { ...row, otodom_id: "ab" },
      { ...row, latest_audit_id: "../../x" },
      { ...row, note: 5 },
    ];
    expect(readSaved([row, ...bad])).toHaveLength(1);
  });
});

describe("noteLength", () => {
  it("counts characters the way the server does, not UTF-16 units", () => {
    expect(noteLength("zażółć")).toBe(6);
    expect(noteLength("😀😀")).toBe(2);
  });
});
