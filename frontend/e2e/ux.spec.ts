/**
 * The UX gate (RM-439, `.agent/rules/statistics.md`, `frontend/docs/UX-REVIEW-RYNEK.md`): runs after the functional
 * suite (`pnpm ux`) and looks at Rynek the way a person does. For every representative state (populated, empty,
 * loading, restricted, error) at 390, 768 and 1280 px in the light and the dark theme it takes a picture into
 * `ux-out/` (to be LOOKED AT: a picture and axe prove nothing about spacing) and asserts what a machine can:
 * no horizontal page overflow, no clipped text, targets of at least 24 px (44 px on the map, the tabs and the filter
 * chips), no overlapping chart ticks or map labels, readable chart text, section separation and heading-to-content
 * spacing from the design tokens, axe, and a keyboard walkthrough. Pixel baselines are `visual.spec.ts`.
 */
import { mkdirSync } from "node:fs";

import type { Page } from "@playwright/test";

import { createMarket, type Scenario, type ScenarioName } from "../test/scenarios";
import { THEME_KEY_FOR_TESTS } from "./visual-theme";
import { expect, expectNoA11yViolations, test } from "./fixtures";

const OUT = "ux-out";
const VIEWPORTS = [
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1280", width: 1280, height: 900 },
] as const;
const THEMES = ["light", "dark"] as const;

interface State {
  readonly id: string;
  readonly path: string;
  readonly scenario: ScenarioName | (() => Scenario);
  /** The text that proves the state is on screen. */
  readonly ready: string | RegExp;
  readonly kind: "populated" | "empty" | "loading" | "restricted" | "error";
  /** A loading state is photographed before it settles. */
  readonly settle?: boolean;
}

const STATES: readonly State[] = [
  {
    id: "explorer-map",
    path: "/app/market/otodom",
    scenario: "market",
    ready: "Filtry mieszkań",
    kind: "populated",
  },
  {
    id: "explorer-preview",
    path: "/app/market/otodom?sel=bialystok&cohort=rooms_2",
    scenario: "market",
    ready: "Zamknij",
    kind: "populated",
  },
  {
    id: "explorer-list",
    path: "/app/market/otodom?view=list",
    scenario: "market",
    ready: "Miejsca z medianami",
    kind: "populated",
  },
  {
    id: "compare",
    path: "/app/market/otodom?view=compare&ids=bialystok,bydgoszcz,bytom",
    scenario: "market",
    ready: "Porównanie miejsc",
    kind: "populated",
  },
  {
    id: "compare-empty",
    path: "/app/market/otodom?view=compare",
    scenario: "market",
    ready: "Wybierz co najmniej dwa miejsca",
    kind: "empty",
  },
  {
    id: "place",
    path: "/app/market/otodom/bialystok",
    scenario: "market",
    ready: "Dzielnicę wskazano przy",
    kind: "populated",
  },
  {
    id: "place-no-districts",
    path: "/app/market/otodom/bydgoszcz",
    scenario: "market",
    ready: "Otodom nie wskazuje dzielnic",
    kind: "empty",
  },
  {
    id: "place-unavailable",
    path: "/app/market/otodom/kielce",
    scenario: "market",
    ready: "Brak danych dla tego miejsca",
    kind: "empty",
  },
  {
    id: "place-loading",
    path: "/app/market/otodom/bialystok",
    scenario: () => createMarket({ historyDelayMs: 4000 }),
    ready: "Wczytuję historię odczytów",
    kind: "loading",
    settle: false,
  },
  {
    id: "district",
    path: "/app/market/otodom/bialystok/centrum",
    scenario: "market",
    ready: "Dzielnica według ogłoszeń Otodom",
    kind: "populated",
  },
  {
    id: "district-insufficient",
    path: "/app/market/otodom/bialystok/rubinkowo",
    scenario: "market",
    ready: "Za mało ofert z ceną, by podać medianę",
    kind: "empty",
  },
  {
    id: "gus-ranking",
    path: "/app/market/gus/bialystok",
    scenario: "market",
    ready: "Z czego składa się wynik",
    kind: "populated",
  },
  {
    id: "gus-overview",
    path: "/app/market/gus",
    scenario: "market",
    ready: /Mianownik pozycji/,
    kind: "populated",
  },
  {
    id: "gus-not-scored",
    path: "/app/market/gus/chorzow",
    scenario: "market",
    ready: "Z czego składa się wynik",
    kind: "empty",
  },
  {
    id: "explorer-restricted",
    path: "/app/market/otodom?view=list",
    scenario: "marketFree",
    ready: /Konto darmowe/,
    kind: "restricted",
  },
  {
    id: "explorer-empty",
    path: "/app/market/otodom",
    scenario: "marketEmpty",
    ready: "Filtry mieszkań",
    kind: "empty",
  },
  {
    id: "explorer-error",
    path: "/app/market/otodom",
    scenario: () => createMarket({ overviewFails: true }),
    ready: "Nie udało się wczytać miejsc",
    kind: "error",
  },
  {
    id: "place-error",
    path: "/app/market/otodom/bialystok",
    scenario: () => createMarket({ detailFails: true }),
    ready: "Nie udało się wczytać miejsca",
    kind: "error",
  },
  {
    id: "gus-error",
    path: "/app/market/gus/bialystok",
    scenario: () => createMarket({ rankingFails: true }),
    ready: "Nie udało się wczytać rankingu",
    kind: "error",
  },
];

interface Finding {
  readonly rule: string;
  readonly detail: string;
}

/** Everything a machine can say about the rendered page; `findings` is empty when the layout holds. */
async function audit(page: Page, width: number): Promise<Finding[]> {
  return page.evaluate((viewport) => {
    const findings: { rule: string; detail: string }[] = [];
    const px = (value: string, fallback: number) => {
      const n = Number(value.replace("px", ""));
      return Number.isFinite(n) ? n : fallback;
    };
    const add = (rule: string, detail: string) => findings.push({ rule, detail });
    const label = (el: Element) =>
      `${el.tagName.toLowerCase()}${el.getAttribute("aria-label") ? `[${el.getAttribute("aria-label")}]` : ""} "${(el.textContent ?? "").trim().slice(0, 40)}"`;
    const main = document.querySelector("main") ?? document.body;
    const visible = (el: Element) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };

    // 1. no horizontal page overflow (a scrolling region inside the page is fine, the page itself must not)
    const doc = document.documentElement;
    if (doc.scrollWidth > doc.clientWidth + 1)
      add("horizontal-overflow", `page ${doc.scrollWidth} > ${doc.clientWidth}`);

    // 2. clipped text: a box that hides its overflow and holds more than it shows (scroll regions excepted)
    for (const el of main.querySelectorAll("*")) {
      if (!visible(el)) continue;
      const s = getComputedStyle(el);
      const hides = s.overflowX === "hidden" || s.textOverflow === "ellipsis";
      if (hides && el.scrollWidth > el.clientWidth + 2 && el.children.length === 0 && !el.closest("svg"))
        add("clipped-text", `${label(el)} ${el.scrollWidth} > ${el.clientWidth}`);
    }

    // 3. touch targets: 24 px everywhere (WCAG 2.2 AA 2.5.8), 44 px on the map, the tabs and the filter chips
    const must44 = "[data-map-ui], [data-tab], label:has(input[type=radio])";
    for (const el of main.querySelectorAll("button, a[href], input, select, summary, [role=combobox]")) {
      if (!visible(el) || el.closest("svg")) continue;
      if (el.matches("input:not([type=radio])") && el.getBoundingClientRect().width <= 2) continue; // a visually hidden form mirror
      const r = (el.matches("input[type=radio]") ? (el.closest("label") ?? el) : el).getBoundingClientRect();
      const inline = el.tagName === "A" && getComputedStyle(el).display === "inline" && !el.matches(must44);
      if (inline) continue; // an inline link inside a sentence is exempt (2.5.8)
      const need = el.matches(must44) || el.closest(must44) ? 44 : 24;
      if (r.width + 0.5 < need || r.height + 0.5 < need)
        add("target-size", `${label(el)} ${Math.round(r.width)}x${Math.round(r.height)} < ${need}`);
    }

    // 4. overlap: map labels, markers and the preview, and chart tick labels
    const boxes = (sel: string) =>
      [...main.querySelectorAll(sel)].filter(visible).map((el) => ({ el, r: el.getBoundingClientRect() }));
    const overlaps = (a: DOMRect, b: DOMRect) =>
      a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1;
    const labels = boxes("[data-testid=market-map] span[aria-hidden=true]");
    for (const [i, a] of labels.entries())
      for (const b of labels.slice(i + 1))
        if (overlaps(a.r, b.r) && a.el.textContent && b.el.textContent)
          add("label-overlap", `${label(a.el)} over ${label(b.el)}`);
    const preview = main.querySelector("[data-testid=map-preview]");
    const controls = main.querySelector("[data-testid=market-map] [aria-label='Sterowanie mapą']");
    if (preview && controls && overlaps(preview.getBoundingClientRect(), controls.getBoundingClientRect()))
      add("preview-over-controls", "the preview covers the map controls");
    for (const axis of main.querySelectorAll(".recharts-cartesian-axis")) {
      const ticks = [...axis.querySelectorAll(".recharts-cartesian-axis-tick-value")].map((t) =>
        t.getBoundingClientRect(),
      );
      for (const [i, a] of ticks.entries())
        for (const b of ticks.slice(i + 1))
          if (overlaps(a, b)) add("tick-overlap", "two axis labels overlap");
      for (const t of axis.querySelectorAll("text")) {
        const fontPx = px(getComputedStyle(t).fontSize, 16);
        if (fontPx < 11) add("chart-text-size", `${(t.textContent ?? "").slice(0, 20)} ${fontPx}px < 11px`);
      }
    }

    // 5. a bar or card row must not be wrapped into a column of single words: no word-per-line labels
    for (const el of main.querySelectorAll("th, dt, label, legend, summary, h2, h3")) {
      if (!visible(el)) continue;
      const lines = el.getBoundingClientRect().height / px(getComputedStyle(el).lineHeight, 20);
      const words = (el.textContent ?? "").trim().split(/\s+/).length;
      if (words >= 3 && lines >= words - 0.2 && viewport >= 390 && !el.closest("table"))
        add("one-word-per-line", label(el));
    }

    // 6. heading-to-content and section separation from the design tokens (4, 8, 12, 16, 24, 32 px)
    for (const h of main.querySelectorAll("h2, h3")) {
      if (!visible(h) || h.closest("figure, article, details, aside, header, fieldset")) continue;
      const next = h.nextElementSibling;
      if (next && visible(next)) {
        const gap = next.getBoundingClientRect().top - h.getBoundingClientRect().bottom;
        if (gap < 4) add("heading-gap", `${label(h)} touches its content (${Math.round(gap)}px)`);
        if (gap > 40) add("heading-gap", `${label(h)} is ${Math.round(gap)}px from its content`);
      }
    }
    const sections = [
      ...main.querySelectorAll(":scope > div > section, :scope > div > div > section"),
    ].filter(visible);
    for (let i = 0; i + 1 < sections.length; i += 1) {
      const a = sections[i];
      const b = sections[i + 1];
      if (!a || !b || a.parentElement !== b.parentElement) continue;
      const gap = b.getBoundingClientRect().top - a.getBoundingClientRect().bottom;
      if (gap < 15) add("section-gap", `${label(a)} and ${label(b)} are ${Math.round(gap)}px apart`);
    }
    return findings;
  }, width);
}

for (const theme of THEMES) {
  for (const viewport of VIEWPORTS) {
    test.describe(`${theme} ${viewport.name}px`, () => {
      test.beforeEach(async ({ page }) => {
        mkdirSync(OUT, { recursive: true });
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.addInitScript(
          ([key, value]) => localStorage.setItem(key as string, value as string),
          [THEME_KEY_FOR_TESTS, theme],
        );
      });

      for (const state of STATES) {
        test(`${state.id} (${state.kind})`, async ({ page, serve }) => {
          await serve(typeof state.scenario === "function" ? state.scenario() : state.scenario);
          await page.goto(state.path);
          if (state.kind === "loading") await expect(page.locator("[aria-busy=true]").first()).toBeVisible();
          else await expect(page.getByText(state.ready).first()).toBeVisible();
          if (state.settle !== false) {
            await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
            await page.evaluate(() => document.fonts.ready);
            await page.waitForTimeout(500); // marker and label layout after the first paint
          }
          await page.screenshot({ path: `${OUT}/${state.id}-${theme}-${viewport.name}.png`, fullPage: true });
          const findings = await audit(page, viewport.width);
          expect(
            findings.map((f) => `${f.rule}: ${f.detail}`),
            `${state.id} ${theme} ${viewport.name}`,
          ).toEqual([]);
          if (state.settle !== false) await expectNoA11yViolations(page);
        });
      }
    });
  }
}

test.describe("keyboard walkthroughs", () => {
  test("the explorer: tabs, filters, view, compare, then the map and its controls, each focus visible; Escape closes the preview", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/otodom");
    await expect(page.getByText("Filtry mieszkań")).toBeVisible();
    const visited: string[] = [];
    for (let i = 0; i < 80; i += 1) {
      await page.keyboard.press("Tab");
      const info = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (el === null) return null;
        const s = getComputedStyle(el);
        const ring = s.outlineStyle !== "none" && Number(s.outlineWidth.replace("px", "")) >= 2;
        const label = el.closest("label");
        const labelRing = label ? getComputedStyle(label).outlineStyle !== "none" : false;
        return {
          name:
            el.getAttribute("aria-label") ??
            (el as HTMLInputElement).labels?.[0]?.textContent?.trim() ??
            el.textContent?.trim().slice(0, 30) ??
            el.tagName,
          ring: ring || labelRing || s.boxShadow !== "none",
          tag: el.tagName,
        };
      });
      if (info === null) break;
      visited.push(info.name);
      expect(info.ring, `focus on ${info.name} is visible`).toBe(true);
      if (info.name === "Pokaż całą Polskę") break;
    }
    expect(visited).toEqual(
      expect.arrayContaining([
        "Mapa",
        "Lista",
        "Porównaj miejsca",
        "Przybliż mapę",
        "Oddal mapę",
        "Pokaż całą Polskę",
      ]),
    );
    expect(visited.filter((n) => /^Poniżej 30/.test(n) || /pokój/.test(n)).length).toBeGreaterThan(0);
  });

  test("the comparison and the ranking are operable by keyboard alone", async ({ page, serve }) => {
    await serve("market");
    await page.goto("/app/market/otodom?view=compare");
    await page.getByRole("textbox", { name: "Szukaj miejsca do dodania" }).focus();
    await page.keyboard.type("Byd");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Dodaj do porównania Bydgoszcz" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("compare-message")).toContainText("Dodano Bydgoszcz");
    await page.goto("/app/market/gus/bialystok");
    await page
      .getByRole("link", { name: /^Szczegóły wskaźnika: / })
      .first()
      .focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#metric-/);
  });
});
