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
/** The report routes answer with their fixture whatever the id is. */
const ANY_AUDIT = "00000000-0000-4000-8000-000000000037";
/** [scenario, picture name, text that proves the page is ready]. */
const REPORT_VARIANTS = [
  ["degraded", "degraded", "wniosek jest mniej pewny"],
  ["rejectedRent", "rejected-rent", "To ogłoszenie wynajmu"],
  ["rejectedFractional", "rejected-fractional", "Sprzedaż udziału"],
  ["failedUpstream", "failed-upstream", "Raport nie został pobrany z konta."],
] as const;
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
      await shoot(page, "dashboard-empty", { fullPage: true }); // the history sits below a phone's first screen
    });

    test("dashboard with five analyses", async ({ page, serve }) => {
      await serve("loaded");
      await page.goto("/app");
      await expect(page.getByRole("list", { name: "Ostatnie analizy" })).toBeVisible();
      await shoot(page, "dashboard-loaded", { fullPage: true });
    });

    const MARKET: [string, string, string, string, boolean][] = [
      [
        "the map with a preview",
        "market-map-preview",
        "/app/market/otodom?sel=bialystok",
        "map-preview",
        false,
      ],
      [
        "the list filtered to two rooms",
        "market-list-rooms",
        "/app/market/otodom?view=list&cohort=rooms_2",
        "",
        false,
      ],
      [
        "the comparison",
        "market-compare",
        "/app/market/otodom?view=compare&ids=bialystok,bydgoszcz",
        "",
        true,
      ],
      ["a place", "market-place", "/app/market/otodom/bialystok", "", true],
      ["a district", "market-district", "/app/market/otodom/bialystok/centrum", "", true],
      ["the GUS ranking", "market-gus", "/app/market/gus/bialystok", "ranking-card", true],
    ];
    for (const [title, name, url, testId, full] of MARKET) {
      test(`market: ${title}`, async ({ page, serve }) => {
        test.slow();
        await serve("market");
        await page.goto(url);
        if (testId !== "") await expect(page.getByTestId(testId)).toBeVisible({ timeout: 15_000 });
        else await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        if (full) await expect(page.locator("[aria-busy=true]")).toHaveCount(0, { timeout: 15_000 });
        if (testId === "map-preview") await page.getByTestId("market-map").scrollIntoViewIfNeeded();
        await page.waitForTimeout(600); // lazy chart chunks and the map camera settle
        await shoot(page, name, { fullPage: full });
      });
    }

    test("market: a restricted account and an empty catalogue", async ({ page, serve }) => {
      await serve("marketFree");
      await page.goto("/app/market/otodom?view=list");
      await expect(page.getByText(/Konto darmowe/)).toBeVisible();
      await shoot(page, "market-restricted");
      await serve("marketEmpty");
      await page.goto("/app/market/otodom");
      await expect(page.getByText("Filtry mieszkań")).toBeVisible();
      await shoot(page, "market-empty");
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

    test("report, the whole page (below the fold: costs, price, what to verify, sources)", async ({
      page,
      serve,
    }) => {
      await serve("loaded");
      await page.goto(`/app/analyses/${SUCCEEDED_AUDITS[0]?.audit_id ?? ""}`);
      await expect(page.getByRole("navigation", { name: "Sekcje raportu" })).toBeVisible();
      await shoot(page, "report-full", { fullPage: true });
    });

    test("report with listing details and evidence", async ({ page, serve }) => {
      await serve("richReport");
      await page.goto(`/app/analyses/${SUCCEEDED_AUDITS[0]?.audit_id ?? ""}`);
      await expect(page.getByRole("heading", { level: 2, name: "Podsumowanie" })).toBeVisible();
      await shoot(page, "report-rich", { fullPage: true });
    });

    for (const [scenario, name, ready] of REPORT_VARIANTS) {
      test(`report variant: ${name}`, async ({ page, serve }) => {
        await serve(scenario);
        await page.goto(`/app/analyses/${ANY_AUDIT}`);
        await expect(page.getByText(ready).first()).toBeVisible();
        await shoot(page, `report-${name}`, { fullPage: true });
      });
    }

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

    test("settings, and the account deletion dialog", async ({ page, serve }) => {
      await serve("settings");
      await page.goto("/app/settings");
      await expect(page.getByRole("list", { name: "Aktywne sesje" })).toBeVisible();
      await shoot(page, "settings");
      await page.getByRole("button", { name: "Usuń konto", exact: true }).click();
      await expect(page.getByRole("dialog", { name: "Usunąć konto na stałe?" })).toBeVisible();
      await shoot(page, "settings-erase");
    });

    test("unknown address keeps the shell", async ({ page, serve }) => {
      await serve("empty");
      await page.goto("/nie-ma-takiej-strony");
      await expect(page.getByRole("heading", { level: 1, name: "Nie znaleziono strony" })).toBeVisible();
      await shoot(page, "not-found");
    });

    // Architekt wnętrz (RM-451): the same fictional project in every state worth a picture.
    test("interior: empty list", async ({ page, serve }) => {
      await serve("interiorEmpty");
      await page.goto("/app/interior");
      await expect(page.getByText("Nie masz jeszcze projektu")).toBeVisible();
      await shoot(page, "interior-empty");
    });

    test("interior: closed beta", async ({ page, serve }) => {
      await serve("interiorClosed");
      await page.goto("/app/interior");
      await expect(page.getByText("Architekt wnętrz jest w zamkniętej wersji beta")).toBeVisible();
      await shoot(page, "interior-closed");
    });

    test("interior: a project with photo, brief, items, products and totals", async ({ page, serve }) => {
      await serve("interior");
      await page.goto("/app/interior/00000000-0000-4000-8000-000000000901");
      await expect(page.getByRole("region", { name: "Tablica produktów" })).toBeVisible();
      await shoot(page, "interior-project", { fullPage: true });
    });

    test("interior: no catalogue source configured", async ({ page, serve }) => {
      await serve("interiorNoCatalogue");
      await page.goto("/app/interior/00000000-0000-4000-8000-000000000901");
      await expect(page.getByRole("region", { name: "Katalog produktów" })).toBeVisible();
      await shoot(page, "interior-no-catalogue", { fullPage: true });
    });

    test("interior: delete confirmation", async ({ page, serve }) => {
      await serve("interior");
      await page.goto("/app/interior");
      await page
        .getByRole("button", { name: /^Usuń projekt/ })
        .first()
        .click();
      await expect(page.getByRole("dialog", { name: "Usunąć projekt?" })).toBeVisible();
      await shoot(page, "interior-delete");
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
