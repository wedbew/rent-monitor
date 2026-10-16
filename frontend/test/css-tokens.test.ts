import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A `var(--name)` with no definition is silently ignored by the browser: the property just does not apply (found by
 * the visual lane, #334: `--space-5` does not exist, so a card had no padding). Every custom property a stylesheet
 * reads must be defined in `styles/tokens.css`, or in the same file, or come with a fallback.
 */
const root = join(__dirname, "..");
/** Set at runtime by Base UI on its popups (positioner), not by a stylesheet. */
const RUNTIME = new Set(["--anchor-width", "--available-height", "--transform-origin"]);
const SKIP = new Set(["node_modules", "dist", "coverage", "playwright-coverage", "test-results", "e2e"]);

function stylesheets(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (entry.isDirectory()) return SKIP.has(entry.name) ? [] : stylesheets(join(dir, entry.name));
    return entry.name.endsWith(".css") ? [join(dir, entry.name)] : [];
  });
}

const defined = (css: string) =>
  new Set([...css.matchAll(/(--[a-z0-9-]+)\s*:/gi)].map((m) => m[1] as string));
const tokens = defined(readFileSync(join(root, "styles", "tokens.css"), "utf8"));

describe("custom properties", () => {
  it("every var(--x) without a fallback is defined in tokens.css or in its own file", () => {
    const unknown: string[] = [];
    for (const file of stylesheets(root)) {
      const css = readFileSync(file, "utf8");
      const own = defined(css);
      for (const match of css.matchAll(/var\(\s*(--[a-z0-9-]+)\s*([,)])/gi)) {
        const name = match[1] as string;
        const hasFallback = match[2] === ",";
        if (!hasFallback && !tokens.has(name) && !own.has(name) && !RUNTIME.has(name))
          unknown.push(`${relative(root, file)}: ${name}`);
      }
    }
    expect(unknown).toEqual([]);
  });

  it("finds the tokens it is checking against", () => {
    expect(tokens.has("--space-4")).toBe(true);
    expect(tokens.has("--space-5")).toBe(false);
  });
});
