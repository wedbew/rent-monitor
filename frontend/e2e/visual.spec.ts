/**
 * Visual baselines (audit F13, #334): the shell, forms with errors, dialogs, collection views and the report, in both
 * themes at desktop and phone width. A picture is only comparable on the stack that made it, so the baselines in
 * `e2e/__screenshots__/` are made and compared ONLY inside the pinned Playwright Linux image (`pnpm visual`,
 * `pnpm visual:update`); a run anywhere else will differ in fonts and is not evidence.
 *
 * Data is the sanitised fixtures and scenarios, so the pictures are of a fictional account. Dates, balances and
 * identifiers are fixed by the scenarios; nothing here depends on the clock.
 */
import type { Page } from "@playwright/test";

import { THEME_KEY_FOR_TESTS } from "./visual-theme";
import { createSaved, SUCCEEDED_AUDITS } from "../test/scenarios";
import { expect, test } from "./fixtures";

const THEMES = ["light", "dark"] as const;
const LISTING = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd";

async function settle(page: Page): Promise<void> {
  await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
  await page.evaluate(() => document.fonts.ready);
}

for (const theme of THEMES) {
  test.describe(`${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript(
        ([key, value]) => {
          localStorage.setItem(key as string, value as string);
        },
        [THEME_KEY_FOR_TESTS, theme],
      );
    });

    const shoot = async (page: Page, name: string, options: { fullPage?: boolean } = {}) => {
      await settle(page);
      await expect(page).toHaveScreenshot(`${name}-${theme}.png`, { fullPage: options.fullPage ?? false });
    };

    test("dashboard: first visit and with history", async ({ page, serve }) => {
      await serve("empty");
      await page.goto("/app");
      await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
      await shoot(page, "dashboard-empty");
    });

    test("dashboard with five analyses", async ({ page, serve }) => {
      await serve("loaded");
      await page.goto("/app");
      await expect(page.getByRole("list", { name: "Ostatnie analizy" })).toBeVisible();
      await shoot(page, "dashboard-loaded");
    });

    test("analyses: cards, table and the saved scope", async ({ page, serve }) => {
      await serve(createSaved());
      await page.goto("/app/analyses");
      await expect(page.getByRole("list", { name: "Analizy" })).toBeVisible();
      await shoot(page, "analyses-cards");
      await page.goto("/app/analyses?view=table");
      await expect(page.getByRole("table")).toBeVisible();
      await shoot(page, "analyses-table");
      await page.goto("/app/analyses?saved=1");
      await expect(page.getByRole("list", { name: "Zapisane ogłoszenia" })).toBeVisible();
      await shoot(page, "analyses-saved");
    });

    test("report, top of the page", async ({ page, serve }) => {
      await serve("loaded");
      await page.goto(`/app/analyses/${SUCCEEDED_AUDITS[0]?.audit_id ?? ""}`);
      await expect(page.getByRole("navigation", { name: "Sekcje raportu" })).toBeVisible();
      await shoot(page, "report");
    });

    test("new analysis: empty, with an error, and the paywall dialog", async ({ page, serve }) => {
      await serve("insufficientCredits");
      await page.goto("/app/analyses/new");
      await expect(page.getByRole("heading", { level: 1, name: "Nowa analiza" })).toBeVisible();
      await shoot(page, "new-analysis");
      await page.getByRole("button", { name: "Rozpocznij analizę" }).click();
      await expect(page.getByRole("alert").filter({ hasText: "Popraw 1 pole" })).toBeVisible();
      await shoot(page, "new-analysis-error");
      await page.getByRole("textbox", { name: "Adres ogłoszenia lub numer" }).fill(LISTING);
      await page.getByRole("button", { name: "Rozpocznij analizę" }).click();
      await expect(page.getByRole("dialog", { name: "Nie masz już raportów" })).toBeVisible();
      await shoot(page, "new-analysis-paywall");
    });

    test("sign in and sign up, with and without errors", async ({ page, serve }) => {
      await serve("firstVisit");
      await page.goto("/login");
      await expect(page.getByRole("heading", { level: 1, name: "Zaloguj się" })).toBeVisible();
      await shoot(page, "login");
      await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
      await expect(page.getByRole("alert").filter({ hasText: "Popraw pola" })).toBeVisible();
      await shoot(page, "login-errors");
      await page.goto("/signup");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await shoot(page, "signup");
    });

    test("credits: the shop and a purchase history", async ({ page, serve }) => {
      await serve("shop");
      await page.goto("/app/credits");
      await expect(page.getByRole("list", { name: "Dostępne pakiety" })).toBeVisible();
      await shoot(page, "credits-shop");
      await page.unrouteAll();
      await serve("shopHistory");
      await page.goto("/app/credits");
      await expect(page.getByRole("list", { name: "Zakupy" })).toBeVisible();
      await shoot(page, "credits-history", { fullPage: true });
    });

    test("unknown address keeps the shell", async ({ page, serve }) => {
      await serve("empty");
      await page.goto("/nie-ma-takiej-strony");
      await expect(page.getByRole("heading", { level: 1, name: "Nie znaleziono strony" })).toBeVisible();
      await shoot(page, "not-found");
    });

    test("the mobile navigation sheet", async ({ page, serve, isMobile }) => {
      test.skip(!isMobile, "the sheet exists on a phone only");
      await serve("empty");
      await page.goto("/app");
      await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
      await expect(page.getByRole("dialog", { name: "Nawigacja" })).toBeVisible();
      await shoot(page, "mobile-menu");
    });
  });
}
