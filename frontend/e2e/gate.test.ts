import { describe, expect, it } from "vitest";

import {
  compareCoverage,
  coverageFailed,
  findViolations,
  interactiveNodes,
  nameMatches,
  parseAriaSnapshot,
  requiredIds,
} from "./gate";
import type { Interaction, Popup } from "./interactions";

const SNAPSHOT = `
- banner:
  - link "renti":
    - /url: /app
  - navigation "Główna":
    - list:
      - listitem:
        - link "Pulpit" [disabled]
        - link "Moje analizy"
- main:
  - heading "Moje analizy" [level=1]
  - text: Pokazuję 5 z 120
  - textbox "Szukaj po numerze"
  - button "Usuń \\"koszt\\""
  - button
  - button "Otwórz menu nawigacji": Menu
  - 'button "Eksport: CSV"'
  - checkbox "Tylko udane" [checked]
  - combobox "Status":
    - option "Wszystkie"
  - paragraph: nie interaktywny
`;

const entry = (over: Partial<Interaction> & Pick<Interaction, "id" | "role" | "name">): Interaction => ({
  page: "list",
  outcome: "url",
  ...over,
});

describe("parseAriaSnapshot: a quoted name that has children", () => {
  it("reads a link whose name holds a colon and which contains another node", () => {
    const nodes = parseAriaSnapshot(
      `- 'link "Wróć do: Białystok" [ref=e122] [cursor=pointer]':\n  - img\n- 'button "Dodaj do porównania: Toruń" [ref=e5]'`,
    );
    expect(nodes.map((n) => [n.role, n.name])).toEqual([
      ["link", "Wróć do: Białystok"],
      ["img", null],
      ["button", "Dodaj do porównania: Toruń"],
    ]);
  });
});

describe("parseAriaSnapshot: a quoted name followed by inline text", () => {
  it("reads a button whose name holds a colon and whose text content is inline (RM-451)", () => {
    const nodes = parseAriaSnapshot(
      [
        `- 'button "Dodaj zdjęcie: Stary fotel"': Zdjęcie`,
        `- 'button "Zmniejsz liczbę sztuk: Sofa Nordic 3-osobowa" [disabled]': −`,
      ].join("\n"),
    );
    expect(nodes.map((n) => [n.role, n.name, n.attributes])).toEqual([
      ["button", "Dodaj zdjęcie: Stary fotel", []],
      ["button", "Zmniejsz liczbę sztuk: Sofa Nordic 3-osobowa", ["[disabled]"]],
    ]);
  });
});

describe("parseAriaSnapshot", () => {
  it("reads roles, names and attributes, and skips properties and plain text", () => {
    const nodes = parseAriaSnapshot(SNAPSHOT);
    expect(nodes.find((n) => n.role === "link" && n.name === "Pulpit")?.attributes).toEqual(["[disabled]"]);
    expect(nodes.find((n) => n.role === "heading")?.attributes).toEqual(["[level=1]"]);
    expect(interactiveNodes(SNAPSHOT).some((n) => n.role === "text" || n.role === "paragraph")).toBe(false);
    expect(nodes.find((n) => n.name?.startsWith("Usuń"))?.name).toBe('Usuń "koszt"');
    expect(nodes.find((n) => n.name?.startsWith("Eksport"))?.name).toBe("Eksport: CSV");
  });

  it("reads a control whose text content follows the name", () => {
    const nodes = parseAriaSnapshot(SNAPSHOT);
    expect(nodes.find((n) => n.name === "Otwórz menu nawigacji")?.role).toBe("button");
  });

  it("keeps a control with no name as a nameless node", () => {
    expect(parseAriaSnapshot(SNAPSHOT).filter((n) => n.role === "button" && n.name === null)).toHaveLength(1);
  });

  it("lists only interactive roles", () => {
    const roles = new Set(interactiveNodes(SNAPSHOT).map((n) => n.role));
    expect([...roles].sort()).toEqual(["button", "checkbox", "combobox", "link", "option", "textbox"]);
  });
});

describe("nameMatches", () => {
  it("matches exact strings and patterns, never a missing name", () => {
    expect(nameMatches("Pulpit", "Pulpit")).toBe(true);
    expect(nameMatches("Pulpit", "Pulpit 2")).toBe(false);
    expect(nameMatches(/^Otwórz raport \d+$/, "Otwórz raport 3")).toBe(true);
    expect(nameMatches("x", null)).toBe(false);
  });
});

describe("findViolations", () => {
  const all: Interaction[] = [
    entry({ id: "a", role: "link", name: "renti" }),
    entry({ id: "b", role: "link", name: "Pulpit" }),
    entry({ id: "c", role: "link", name: "Moje analizy" }),
    entry({ id: "d", role: "textbox", name: "Szukaj po numerze" }),
    entry({ id: "e", role: "button", name: 'Usuń "koszt"' }),
    entry({ id: "f", role: "button", name: "Eksport: CSV" }),
    entry({ id: "g", role: "checkbox", name: "Tylko udane" }),
    entry({ id: "h", role: "combobox", name: "Status" }),
    entry({ id: "i", role: "option", name: "Wszystkie" }),
    entry({ id: "j", role: "button", name: "Otwórz menu nawigacji" }),
  ];
  const scope = { page: "list", scenario: "loaded" };

  it("reports only the nameless control when everything else is registered", () => {
    const found = findViolations(SNAPSHOT, all, scope);
    expect(found.map((v) => v.kind)).toEqual(["unnamed"]);
  });

  it("reports an element nobody registered", () => {
    const found = findViolations(
      SNAPSHOT,
      all.filter((e) => e.id !== "d"),
      scope,
    );
    expect(found.map((v) => v.message)).toContain(
      'list / loaded: textbox "Szukaj po numerze" is not in e2e/interactions.ts',
    );
  });

  it("reports a registered element that disappeared, but only in scenarios it belongs to", () => {
    const extra = entry({ id: "z", role: "button", name: "Kup pakiet", scenarios: ["insufficientCredits"] });
    expect(findViolations(SNAPSHOT, [...all, extra], scope).map((v) => v.kind)).toEqual(["unnamed"]);
    expect(
      findViolations(SNAPSHOT, [...all, extra], { ...scope, scenario: "insufficientCredits" })
        .map((v) => v.kind)
        .sort(),
    ).toEqual(["missing", "unnamed"]);
  });

  it("keeps page and popup scopes apart", () => {
    const inPopup = entry({ id: "p", role: "button", name: "Potwierdź", within: "confirm" });
    expect(findViolations('- button "Potwierdź"', [inPopup], { ...scope, within: "confirm" })).toEqual([]);
    expect(
      findViolations('- button "Potwierdź"', [inPopup], scope)
        .map((v) => v.kind)
        .sort(),
    ).toEqual(["unregistered"]);
    expect(
      findViolations('- button "Potwierdź"', [inPopup], {
        page: "other",
        scenario: "x",
        within: "confirm",
      }).map((v) => v.kind),
    ).toEqual(["unregistered"]);
  });
});

describe("page states", () => {
  const base = entry({ id: "b", role: "button", name: "Zapisz" });
  const inState = entry({ id: "s", role: "link", name: "Popraw to pole", state: "errors" });
  const registry = [base, inState];
  const snapshot = `- button "Zapisz"\n- link "Popraw to pole"`;

  it("the base state demands only base elements and does not accept state-only ones", () => {
    const found = findViolations('- button "Zapisz"', registry, { page: "list", scenario: "x" });
    expect(found).toEqual([]);
    const extra = findViolations(snapshot, registry, { page: "list", scenario: "x" });
    expect(extra.map((v) => v.kind)).toEqual(["unregistered"]);
  });

  it("a state accepts base elements and demands its own", () => {
    expect(findViolations(snapshot, registry, { page: "list", scenario: "x", state: "errors" })).toEqual([]);
    expect(
      findViolations('- button "Zapisz"', registry, { page: "list", scenario: "x", state: "errors" }).map(
        (v) => v.kind,
      ),
    ).toEqual(["missing"]);
  });

  it("a state does not demand base elements that the state replaced", () => {
    expect(
      findViolations('- link "Popraw to pole"', registry, { page: "list", scenario: "x", state: "errors" }),
    ).toEqual([]);
  });

  it("the signed-out frame's shared elements apply to public pages only", () => {
    const shared = [entry({ id: "t", page: "public:*", role: "button", name: "Tryb ciemny" })];
    expect(
      findViolations('- button "Tryb ciemny"', shared, { page: "login", scenario: "x", layout: "public" }),
    ).toEqual([]);
    expect(
      findViolations('- button "Tryb ciemny"', shared, { page: "login", scenario: "x" }).map((v) => v.kind),
    ).toEqual(["unregistered"]);
  });
});

describe("coverage comparison", () => {
  const interactions = [
    entry({ id: "nav.pulpit", role: "link", name: "Pulpit", outcome: "url" }),
    entry({ id: "list.search", role: "textbox", name: "Szukaj", outcome: "request" }),
  ];
  const popups: Popup[] = [
    {
      id: "confirm",
      page: "list",
      trigger: "list.search",
      role: "dialog",
      name: "Potwierdź",
      backdrop: "stays",
    },
  ];

  it("requires every interaction and every popup", () => {
    expect(requiredIds(interactions, popups)).toEqual(["nav.pulpit", "list.search", "popup:confirm"]);
  });

  it("passes when everything was exercised with the promised outcome", () => {
    const report = compareCoverage(
      [
        { id: "nav.pulpit", kind: "url" },
        { id: "list.search", kind: "request" },
        { id: "popup:confirm", kind: "dialog" },
      ],
      interactions,
      popups,
    );
    expect(coverageFailed(report)).toBe(false);
  });

  it("fails on an interaction no test exercised", () => {
    const report = compareCoverage([{ id: "nav.pulpit", kind: "url" }], interactions, popups);
    expect(report.missing).toEqual(["list.search", "popup:confirm"]);
    expect(coverageFailed(report)).toBe(true);
  });

  it("does not count a test that asserted a different outcome than the registry promises", () => {
    const report = compareCoverage(
      [
        { id: "nav.pulpit", kind: "text" },
        { id: "list.search", kind: "request" },
        { id: "popup:confirm", kind: "dialog" },
      ],
      interactions,
      popups,
    );
    expect(report.missing).toEqual(["nav.pulpit"]);
    expect(report.wrongOutcome).toEqual(["nav.pulpit: asserted text, registry says url"]);
    expect(coverageFailed(report)).toBe(true);
  });

  it("fails on a recorded id that is not registered", () => {
    const report = compareCoverage([{ id: "ghost", kind: "url" }], [], []);
    expect(report.unknown).toEqual(["ghost"]);
    expect(coverageFailed(report)).toBe(true);
  });
});
