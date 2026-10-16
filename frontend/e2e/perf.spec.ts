/**
 * Lab diagnostics (#286 item 3): LCP, CLS and the slowest interaction on the built SPA, with the API answered from the
 * scenario registry. These are DIAGNOSTICS, not thresholds: one machine, no real network, a mocked API, Chromium only;
 * the phone project runs with 4x CPU throttling. They say whether something got badly slower, not what a visitor
 * experiences (that needs field data). Run with `pnpm perf`; the numbers worth keeping go to `docs/PERFORMANCE.md`.
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

import type { Page } from "@playwright/test";

import { SUCCEEDED_AUDITS } from "../test/scenarios";
import { expect, test } from "./fixtures";

interface Vitals {
  readonly lcpMs: number | null;
  readonly cls: number;
  readonly slowestInteractionMs: number | null;
}

const OUT = join(process.env["PERF_OUT"] ?? "test-results", "perf");

async function observe(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const w = window as unknown as { __perf: { lcp: number | null; cls: number; slowest: number | null } };
    w.__perf = { lcp: null, cls: 0, slowest: null };
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) w.__perf.lcp = entry.startTime;
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as unknown as { value: number; hadRecentInput: boolean }[])
        if (!entry.hadRecentInput) w.__perf.cls += entry.value;
    }).observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries())
        w.__perf.slowest = Math.max(w.__perf.slowest ?? 0, entry.duration);
    }).observe({ type: "event", durationThreshold: 16, buffered: true } as PerformanceObserverInit);
  });
}

async function vitals(page: Page): Promise<Vitals> {
  await page.waitForTimeout(500);
  return page.evaluate(() => {
    const p = (window as unknown as { __perf: { lcp: number | null; cls: number; slowest: number | null } })
      .__perf;
    return { lcpMs: p.lcp, cls: p.cls, slowestInteractionMs: p.slowest };
  });
}

const results: Record<string, Vitals> = {};

test.afterAll(() => {
  mkdirSync(OUT, { recursive: true });
  writeFileSync(join(OUT, `${test.info().project.name}.json`), JSON.stringify(results, null, 2));
});

test.beforeEach(async ({ page, isMobile }) => {
  await observe(page);
  if (isMobile) {
    const client = await page.context().newCDPSession(page);
    await client.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  }
});

const PAGES: readonly [string, "empty" | "loaded", string, string][] = [
  ["dashboard", "loaded", "/app", "Pulpit"],
  ["analyses", "loaded", "/app/analyses", "Moje analizy"],
  ["new-analysis", "empty", "/app/analyses/new", "Nowa analiza"],
];

for (const [name, scenario, path, heading] of PAGES) {
  test(`${name}: LCP, CLS and the slowest interaction`, async ({ page, serve }) => {
    await serve(scenario);
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    await page
      .getByRole("link", { name: "Tryb ciemny" })
      .or(page.getByRole("button", { name: "Tryb ciemny" }))
      .first()
      .click();
    results[name] = await vitals(page);
    expect(results[name]?.cls).toBeGreaterThanOrEqual(0);
  });
}

test("report: LCP, CLS and the slowest interaction", async ({ page, serve }) => {
  await serve("loaded");
  await page.goto(`/app/analyses/${SUCCEEDED_AUDITS[0]?.audit_id ?? ""}`);
  await expect(page.getByRole("navigation", { name: "Sekcje raportu" })).toBeVisible();
  await page.getByRole("button", { name: "Zwroty, wyjście i wrażliwość na wzrost cen" }).click();
  results["report"] = await vitals(page);
  expect(results["report"]?.cls).toBeGreaterThanOrEqual(0);
});
