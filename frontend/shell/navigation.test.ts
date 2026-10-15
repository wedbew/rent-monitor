import { describe, expect, it } from "vitest";

import { ALL_DESTINATIONS, destinationFor, LEGAL, PRIMARY } from "./navigation";

const active = (pathname: string) => ALL_DESTINATIONS.filter((d) => d.isActive(pathname)).map((d) => d.id);

describe("navigation registry", () => {
  it("has the seven app destinations in the agreed order, then the two documents", () => {
    expect(PRIMARY.map((d) => d.label)).toEqual([
      "Pulpit",
      "Nowa analiza",
      "Moje analizy",
      "Rynek",
      "Architekt wnętrz",
      "Stwórz ogłoszenie",
      "Ustawienia",
    ]);
    expect(LEGAL.map((d) => d.label)).toEqual(["Regulamin", "Polityka prywatności"]);
  });

  it("gives every destination a unique id and path", () => {
    expect(new Set(ALL_DESTINATIONS.map((d) => d.id)).size).toBe(ALL_DESTINATIONS.length);
    expect(new Set(ALL_DESTINATIONS.map((d) => d.to)).size).toBe(ALL_DESTINATIONS.length);
  });

  it.each([
    ["/app", ["dashboard"]],
    ["/app/analyses", ["analyses"]],
    ["/app/analyses/new", ["new-analysis"]],
    ["/app/analyses/abc-123", ["analyses"]],
    ["/app/market", ["market"]],
    ["/app/interior", ["interior"]],
    ["/app/listings/new", ["listing"]],
    ["/app/settings", ["settings"]],
    ["/terms", ["terms"]],
    ["/privacy", ["privacy"]],
    ["/nie-ma-takiej-strony", []],
    ["/app/analysesx", []],
  ])("%s lights exactly %j", (pathname, expected) => {
    expect(active(pathname)).toEqual(expected);
  });

  it("finds the destination a path belongs to", () => {
    expect(destinationFor("/app/analyses/xyz")?.label).toBe("Moje analizy");
    expect(destinationFor("/x")).toBeUndefined();
  });

  it("is honest about what is not offered yet", () => {
    expect(PRIMARY.filter((d) => d.availability === "unavailable").map((d) => d.id)).toEqual([
      "market",
      "interior",
      "listing",
    ]);
  });
});
