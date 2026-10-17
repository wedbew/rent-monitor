import { describe, expect, it } from "vitest";

import { orderSessions, readSessions, type SessionRow } from "./sessions";

const good = {
  id: 1,
  current: false,
  created_hint: "2026-10-01T10:00:00Z",
  expires_at: "2026-11-01T10:00:00Z",
  user_agent: "Mozilla/5.0 (fixture)",
  ip: "203.0.113.1",
};

describe("readSessions", () => {
  it("reads well-formed rows and keeps null device details", () => {
    expect(readSessions([good, { ...good, id: 2, user_agent: null, ip: null }])).toEqual([
      expect.objectContaining({ id: 1, lastSeen: good.created_hint, userAgent: good.user_agent }),
      expect.objectContaining({ id: 2, userAgent: null, ip: null }),
    ]);
  });

  it("is null for anything that is not a list, and for a list of only malformed rows", () => {
    for (const value of [null, undefined, {}, "x", 7, { items: [good] }])
      expect(readSessions(value)).toBeNull();
    expect(readSessions([{ id: "1" }, null, 3, []])).toBeNull();
  });

  it("drops a malformed row without losing the good ones; an empty list is a real answer", () => {
    expect(readSessions([good, { ...good, id: 2, current: "yes" }, { ...good, id: 3, ip: 7 }])).toHaveLength(
      1,
    );
    expect(readSessions([])).toEqual([]);
  });
});

describe("orderSessions", () => {
  const row = (id: number, current: boolean, lastSeen: string): SessionRow => ({
    id,
    current,
    lastSeen,
    expiresAt: lastSeen,
    userAgent: null,
    ip: null,
  });

  it("puts the current browser first, then the most recently seen, without touching its input", () => {
    const input = [
      row(1, false, "2026-10-01T10:00:00Z"),
      row(2, false, "2026-10-03T10:00:00Z"),
      row(3, true, "2026-09-01T10:00:00Z"),
    ];
    expect(orderSessions(input).map((r) => r.id)).toEqual([3, 2, 1]);
    expect(input.map((r) => r.id)).toEqual([1, 2, 3]);
  });
});
