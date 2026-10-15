import { describe, expect, it } from "vitest";

import { toolIsAvailable } from "./DashboardPage";

const built = {
  id: "a",
  number: "01",
  icon: "search",
  title: "t",
  body: "b",
  cta: "c",
  to: "/x",
  built: true,
} as const;

describe("toolIsAvailable", () => {
  it("is false for a tool that is not built, whatever the flags say", () => {
    expect(toolIsAvailable({ ...built, built: false }, { a: true })).toBe(false);
    expect(toolIsAvailable({ ...built, built: false, flag: "x" }, { x: true })).toBe(false);
  });

  it("is true for a built tool, unless its flag is explicitly off", () => {
    expect(toolIsAvailable(built, {})).toBe(true);
    expect(toolIsAvailable({ ...built, flag: "x" }, {})).toBe(true);
    expect(toolIsAvailable({ ...built, flag: "x" }, { x: true })).toBe(true);
    expect(toolIsAvailable({ ...built, flag: "x" }, { x: false })).toBe(false);
  });
});
