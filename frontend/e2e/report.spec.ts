import type { Page } from "@playwright/test";

import { formatMoney } from "../api/format";
import { SUCCEEDED_AUDITS } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

type Result = {
  listing: { title: string; admin_fee_pln: string | null };
  valuation: { max_bid_pln: string | null; asking_price_pln: string };
  cash_flow: { total_invested_pln: string; purchase: { broker_pln: string } };
};

const resultOf = (index: number): Result => {
  const audit = SUCCEEDED_AUDITS[index];
  if (audit === undefined) throw new Error("no audit fixture");
  return audit.result as Result;
};
const idOf = (index: number): string => SUCCEEDED_AUDITS[index]?.audit_id ?? "";

const figure = (page: Page, label: string) =>
  page
    .getByRole("term")
    .filter({ hasText: new RegExp(`^${label}$`) })
    .locator("xpath=..");

async function open(page: Page, index = 0): Promise<void> {
  await page.goto(`/app/analyses/${idOf(index)}`);
  await expect(page.getByRole("heading", { level: 2, name: "Podsumowanie" })).toBeVisible();
}

test.describe("the report", () => {
  test("the report is loaded on first visit; if its file is gone after a deploy the page offers a reload", async ({
    page,
    serve,
    allowErrors,
    browserName,
  }) => {
    // The chunk is aborted on purpose: the browser and React Router report it, and the page must still cope.
    // What each engine logs for the aborted module (Firefox logs the error object without its text).
    const expected: Record<string, RegExp[]> = {
      chromium: [/Failed to load resource/, /Failed to fetch dynamically imported module/],
      webkit: [/Importing a module script failed/],
      firefox: [/^console\.error: JSHandle@object$/, /React Router caught the following error during render/],
    };
    allowErrors(...(expected[browserName] ?? []));
    await serve("loaded");
    const chunks: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/assets/")) chunks.push(request.url());
    });
    await page.goto("/app");
    await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
    expect(chunks.some((url) => /AnalysisPage-/.test(url))).toBe(false); // not part of the first page (#312)

    await page.route(/\/assets\/AnalysisPage-[^/]+\.js$/, (route) => route.abort("failed"));
    await page.goto(`/app/analyses/${idOf(0)}`);
    await expect(
      page.getByRole("heading", { level: 1, name: "Dostępna jest nowa wersja aplikacji" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Odśwież stronę" })).toBeVisible();
  });

  test("five different captured results each show their own property and numbers", async ({
    page,
    serve,
  }) => {
    await serve("loaded");
    const seen = new Set<string>();
    for (const [index, audit] of SUCCEEDED_AUDITS.entries()) {
      await open(page, index);
      const result = resultOf(index);
      await expect(page.getByRole("heading", { level: 3, name: result.listing.title })).toBeVisible();
      await expect(figure(page, "Kapitał na start")).toContainText(
        formatMoney(result.cash_flow.total_invested_pln, { decimals: 0 }),
      );
      await expect(page.getByRole("region", { name: "Wynik analizy" })).toContainText("Analiza gotowa");
      seen.add(`${audit.audit_id}|${result.listing.title}|${result.cash_flow.total_invested_pln}`);
    }
    expect(seen.size).toBe(5);
  });

  test("an unknown value is said to be unknown, never shown as zero; a real zero stays a zero", async ({
    page,
    serve,
  }) => {
    await serve("loaded");
    const torun = SUCCEEDED_AUDITS.findIndex((a) => (a.result as Result).valuation.max_bid_pln === null);
    expect(torun).toBeGreaterThanOrEqual(0);
    await open(page, torun);
    const max = figure(page, "Cena spełniająca próg zwrotu");
    await expect(max).toContainText("nie obliczono");
    await expect(max).not.toContainText(/\b0\s?zł/);
    await expect(max).toContainText("żadna cena nie spełnia progu");
    // The same report has a genuine zero (no broker): it is shown as a zero, in the details.
    await page.getByRole("button", { name: "Koszty zakupu: szczegóły" }).click();
    await expect(page.getByText("0,00 zł").first()).toBeVisible();
  });

  test("the admin fee is a cost of the owner, not income; asking prices are not transaction prices", async ({
    page,
    serve,
  }) => {
    await serve("loaded");
    await open(page);
    const admin = figure(page, "Czynsz administracyjny");
    await expect(admin).toContainText("koszt właściciela, nie przychód z najmu");
    await expect(admin).toContainText(formatMoney(resultOf(0).listing.admin_fee_pln, { decimals: 0 }));
    await expect(figure(page, "Szacowany czynsz miesięcznie")).toContainText("nie umowy najmu");
    await expect(
      page
        .getByRole("region", { name: "Cena zakupu" })
        .getByRole("term")
        .filter({ hasText: /^Cena ofertowa$/ })
        .locator("xpath=.."),
    ).toContainText("nie cena transakcyjna");
    await page.getByRole("button", { name: "Koszty właściciela w roku 1" }).click();
    await expect(page.getByText("Czynsz administracyjny").nth(1)).toBeVisible();
  });

  test("preliminary renovation prices are labelled as such, before any click", async ({ page, serve }) => {
    await serve("loaded");
    await open(page);
    await expect(page.getByText("Koszt remontu jest wstępny").first()).toBeVisible();
    await expect(page.getByText("wstępny", { exact: true })).toBeVisible();
  });

  test("a degraded result lists what is missing in the open and says the conclusion is less sure", async ({
    page,
    serve,
  }) => {
    await serve("degraded");
    await page.goto("/app/analyses/00000000-0000-4000-8000-000000000037");
    await expect(page.getByRole("heading", { level: 2, name: "Podsumowanie" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Wynik analizy" })).toContainText("Gotowa, mniej pewna");
    await expect(page.getByText("wniosek jest mniej pewny")).toBeVisible();
    await expect(page.getByText("Nie oceniliśmy zdjęć").first()).toBeVisible();
    const checklist = page.getByRole("region", { name: "Co sprawdzić przed ofertą" });
    await expect(checklist).toContainText("Nie oceniliśmy zdjęć");
    await expect(checklist).toContainText("Brak informacji o ogrzewaniu");
    await page.getByRole("button", { name: "Ocena zdjęć" }).click();
    await expect(page.getByText("Zdjęć nie oceniono")).toBeVisible();
  });

  test("details open and close on their own, several at a time, from the keyboard too", async ({
    page,
    serve,
  }) => {
    await serve("loaded");
    await open(page);
    const rent = page.getByRole("button", { name: "Jak policzyliśmy czynsz" });
    const years = page.getByRole("button", { name: "Przepływy pieniężne rok po roku" });
    await exercise("report.more.rent-how", async () => {
      await rent.click();
      return [await outcome.state(rent, "aria-expanded", "true")];
    });
    await expect(page.getByText("Czynsz użyty w obliczeniach")).toBeVisible();
    await exercise("report.more.years", async () => {
      await years.click();
      return [await outcome.state(years, "aria-expanded", "true")];
    });
    await expect(rent).toHaveAttribute("aria-expanded", "true"); // opening one did not close the other
    await expect(page.getByRole("table")).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount(11); // header and ten years
    await years.focus();
    await page.keyboard.press("Enter");
    await expect(years).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByRole("table")).toBeHidden();
  });

  for (const [id, label, content] of [
    ["purchase", "Koszty zakupu: szczegóły", "Taksa notarialna"],
    ["owner-costs", "Koszty właściciela w roku 1", "Razem koszty rocznie"],
    ["capex", "Remont: szacunek i założenia", "Wersja cennika"],
    ["sensitivity", "Zwroty, wyjście i wrażliwość na wzrost cen", "Wpływy netto ze sprzedaży"],
    ["listing", "Dane z ogłoszenia", "Numer ogłoszenia"],
    ["vision", "Ocena zdjęć", "Model i wersja instrukcji"],
  ] as const) {
    test(`the "${label}" details show their content`, async ({ page, serve }) => {
      await serve("loaded");
      await open(page);
      const trigger = page.getByRole("button", { name: label });
      await expect(trigger).toHaveAttribute("aria-expanded", "false");
      await exercise(`report.more.${id}`, async () => {
        await trigger.click();
        return [await outcome.state(trigger, "aria-expanded", "true")];
      });
      await expect(page.getByText(content, { exact: true })).toBeVisible();
    });
  }

  for (const [id, label] of [
    ["podsumowanie", "Podsumowanie"],
    ["czynsz", "Czynsz"],
    ["koszty", "Koszty i stan"],
    ["cena", "Cena zakupu"],
    ["sprawdz", "Co sprawdzić"],
    ["zrodla", "Źródła"],
  ] as const) {
    test(`the section link "${label}" moves focus to its heading without changing the address`, async ({
      page,
      serve,
    }) => {
      await serve("loaded");
      await open(page);
      const url = page.url();
      await exercise(`report.nav.${id}`, async () => {
        await page
          .getByRole("navigation", { name: "Sekcje raportu" })
          .getByRole("link", { name: label })
          .click();
        return [await outcome.focus(page.locator(`#sekcja-${id}`))];
      });
      expect(page.url()).toBe(url);
    });
  }

  test("a rich report links to the listing safely and quotes the evidence as plain text", async ({
    page,
    serve,
  }) => {
    await serve("richReport");
    await page.goto(`/app/analyses/${idOf(0)}`);
    const link = page.getByRole("link", { name: "Zobacz ogłoszenie na Otodom" });
    await exercise("report.external", async () => {
      await expect(link).toHaveAttribute("rel", "noopener noreferrer");
      return [await outcome.state(link, "target", "_blank")];
    });
    await expect(link).toHaveAttribute("href", "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd");
    const evidence = page.getByRole("button", { name: /^Fragmenty ogłoszenia użyte w ocenie \(2\)$/ });
    await exercise("report.more.evidence", async () => {
      await evidence.click();
      return [await outcome.state(evidence, "aria-expanded", "true")];
    });
    await expect(page.getByText("<img src=x onerror=alert(1)> własność")).toBeVisible(); // text, not markup
    await expect(page.locator("img[src='x']")).toHaveCount(0);
  });

  test("a version this build does not know is refused safely and its values are not shown", async ({
    page,
    serve,
  }) => {
    await serve("unsupportedReport");
    await page.goto(`/app/analyses/${idOf(0)}`);
    await expect(page.getByRole("status").filter({ hasText: "Nieobsługiwana wersja raportu" })).toBeVisible();
    await expect(page.getByText("hidden")).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 2 })).toHaveCount(0);
  });

  test("a stored result that is incomplete is said to be unreadable, not guessed at", async ({
    page,
    serve,
  }) => {
    await serve("invalidReport");
    await page.goto(`/app/analyses/${idOf(0)}`);
    await expect(page.getByRole("status").filter({ hasText: "Nie można wyświetlić raportu" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2 })).toHaveCount(0);
  });
});
