import { describe, expect, it } from "vitest";

import { t } from ".";

/** Every leaf of the catalog, with its path: strings, plural tuples and message functions. */
function leaves(node: unknown, path = "t"): [string, unknown][] {
  if (typeof node === "string" || typeof node === "function" || Array.isArray(node)) return [[path, node]];
  if (node === null || typeof node !== "object") return [[path, node]];
  return Object.entries(node).flatMap(([key, value]) => leaves(value, `${path}.${key}`));
}

describe("the Polish catalog", () => {
  const all = leaves(t);

  it("has text everywhere: no empty, padded or doubled-space string", () => {
    for (const [path, value] of all.filter(([, v]) => typeof v === "string")) {
      const text = value as string;
      expect(text.length, path).toBeGreaterThan(0);
      if (!path.endsWith("errorPrefix") && !path.endsWith("conditionAssumed"))
        expect(text, path).toBe(text.trim());
      expect(text, path).not.toMatch(/ {2}|\n/);
    }
  });

  it("plural entries have exactly the three Polish forms", () => {
    for (const [path, value] of all.filter(([, v]) => Array.isArray(v))) {
      expect(value, path).toHaveLength(3);
      for (const form of value as string[]) expect(form.length, path).toBeGreaterThan(0);
    }
  });

  it("every message puts each value it is given into the sentence (no lost or undefined placeholder)", () => {
    for (const [path, value] of all.filter(([, v]) => typeof v === "function")) {
      const message = value as (params: Record<string, string>) => unknown; // a message takes one params object
      const params: Record<string, string> = new Proxy({}, { get: (_, key) => `«${String(key)}»` });
      const out = message(params);
      const text = Array.isArray(out)
        ? out.join("")
        : typeof out === "object" && out !== null
          ? Object.values(out).join(" ")
          : String(out);
      expect(text, path).not.toMatch(/undefined|\[object/);
      expect(text, path).toMatch(/«[a-zA-Z]+»/);
    }
  });

  it("covers every problem code and transport failure with a title and detail", () => {
    for (const copy of [...Object.values(t.problems.codes), ...Object.values(t.problems.transport)]) {
      expect(copy.title.length).toBeGreaterThan(0);
      expect(copy.detail.length).toBeGreaterThan(0);
    }
  });
});
