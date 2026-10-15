import type { Page } from "@playwright/test";

import { createRun, RUN_AUDIT_ID } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

const LISTING = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd";
/** The balance lives in the account block: in the rail on a wide screen, in the menu sheet on a narrow one. */
async function expectBalance(page: Page, text: string): Promise<void> {
  const menu = page.getByRole("button", { name: "Otwórz menu nawigacji" });
  if (await menu.isVisible()) {
    await menu.click();
    await expect(page.getByRole("dialog", { name: "Nawigacja" })).toContainText(text);
    await page.keyboard.press("Escape");
    return;
  }
  await expect(page.getByText(text).first()).toBeVisible();
}

/** A finished run is the report itself: the listing, the section navigation, no banner and no result card. */
async function expectCompletedReport(page: Page, timeout?: number): Promise<void> {
  const wait = timeout === undefined ? {} : { timeout };
  await expect(page.getByRole("heading", { level: 1, name: /^Ogłoszenie / })).toBeVisible(wait);
  await expect(page.getByRole("navigation", { name: "Sekcje raportu" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Wynik analizy" })).toHaveCount(0);
  await expect(page.getByText(/Analiza (jest )?gotowa|Raport został pobrany z konta/)).toHaveCount(0);
}

async function start(page: Page): Promise<void> {
  await page.goto("/app/analyses/new");
  await page.getByRole("textbox", { name: "Adres ogłoszenia lub numer" }).fill(LISTING);
  await page.getByRole("button", { name: "Rozpocznij analizę" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/analyses/${RUN_AUDIT_ID}$`));
}

test.describe("an analysis from click to result", () => {
  test("a success: one stream, the final state re-read from the API, the credit kept and said so", async ({
    page,
    serve,
    isMobile,
  }) => {
    const run = createRun();
    const api = await serve(run);
    await start(page);
    await expectCompletedReport(page);
    expect(run.state.streams).toBe(1);
    // The stream said "done"; the page asked the API again instead of trusting it.
    expect(
      api.requests.filter((r) => r.path === `/api/audits/${RUN_AUDIT_ID}`).length,
    ).toBeGreaterThanOrEqual(2);
    await expectBalance(page, "6 raportów");
    // "Moje analizy" is reached through the application navigation, not through a card on the report.
    if (isMobile) await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
    await page.getByRole("navigation").getByRole("link", { name: "Moje analizy" }).click();
    await expect(page).toHaveURL(/\/app\/analyses$/);
  });

  test("a rental listing is rejected: said in words, the report is given back", async ({ page, serve }) => {
    const run = createRun({ outcome: "rejected" });
    await serve(run);
    await start(page);
    const result = page.getByRole("region", { name: "Wynik analizy" });
    await expect(result).toContainText("To ogłoszenie wynajmu");
    await expect(result).toContainText("Raport nie został pobrany z konta.");
    await expectBalance(page, "7 raportów");
    await exercise("report.all.rejected", async () => {
      await result.getByRole("link", { name: "Moje analizy" }).click();
      return [await outcome.url(page, /\/app\/analyses$/)];
    });
    await page.goBack();
    await exercise("report.new.rejected", async () => {
      await result.getByRole("link", { name: "Nowa analiza" }).click();
      return [await outcome.url(page, /\/app\/analyses\/new$/)];
    });
  });

  test("an upstream failure releases the report and offers a new analysis", async ({ page, serve }) => {
    await serve(createRun({ outcome: "failed" }));
    await start(page);
    const result = page.getByRole("region", { name: "Wynik analizy" });
    await expect(result).toContainText("Otodom zablokował pobranie");
    await expect(result).toContainText("Raport nie został pobrany z konta.");
    await exercise("report.all.failed", async () => {
      await result.getByRole("link", { name: "Moje analizy" }).click();
      return [await outcome.url(page, /\/app\/analyses$/)];
    });
    await page.goBack();
    await exercise("report.new.failed", async () => {
      await result.getByRole("link", { name: "Nowa analiza" }).click();
      return [await outcome.url(page, /\/app\/analyses\/new$/)];
    });
  });

  test("an interrupted stream shows 'Łączę ponownie' with the last server percentage, then resumes", async ({
    page,
    serve,
  }) => {
    const run = createRun({ interrupt: true });
    await serve(run);
    await start(page);
    const progress = page.getByRole("region", { name: "Postęp analizy" });
    await expect(progress.getByRole("status").filter({ hasText: "Łączę ponownie" })).toBeVisible();
    await expect(progress.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");
    const stages = progress.getByRole("list", { name: "Etapy analizy" }).getByRole("listitem");
    await expect(stages).toHaveText([
      "Pobieranie ogłoszenia",
      "Odczyt danych z ogłoszenia",
      "Dane rynkowe i czynsze",
    ]);
    await expectCompletedReport(page);
    expect(run.state.streams).toBe(2); // the browser reconnected once; the page never opened a second source itself
  });

  test("without a stream the page polls the API and still reaches the result", async ({ page, serve }) => {
    const run = createRun({ streamDown: "http" });
    await serve(run);
    await start(page);
    await expect(page.getByText("Sprawdzam postęp co kilka sekund")).toBeVisible();
    await expectCompletedReport(page, 15_000);
  });

  test("a stream that goes silent does not leave the page stale: the API is asked again and the balance follows", async ({
    page,
    serve,
  }) => {
    test.setTimeout(45_000);
    const run = createRun({ silent: true });
    await serve(run);
    await start(page);
    await expect(page.getByRole("progressbar", { name: "Postęp analizy" })).toHaveAttribute(
      "aria-valuenow",
      "25",
    );
    await expectCompletedReport(page, 25_000);
    await expectBalance(page, "6 raportów");
  });

  test("when the stream is down and the page polls, the balance still follows the result", async ({
    page,
    serve,
  }) => {
    await serve(createRun({ streamDown: "http" }));
    await start(page);
    await expectCompletedReport(page, 15_000);
    await expectBalance(page, "6 raportów");
  });

  test("reloading a running analysis asks the API for its status first, then watches again", async ({
    page,
    serve,
  }) => {
    const run = createRun({ interrupt: true });
    const api = await serve(run);
    await page.goto(`/app/analyses/${RUN_AUDIT_ID}`);
    await expect(page.getByRole("progressbar", { name: "Postęp analizy" })).toBeVisible();
    const order = api.requests.map((r) => r.path);
    expect(order.indexOf(`/api/audits/${RUN_AUDIT_ID}`)).toBeGreaterThanOrEqual(0);
    expect(order.indexOf(`/api/audits/${RUN_AUDIT_ID}`)).toBeLessThan(
      order.indexOf(`/api/audits/${RUN_AUDIT_ID}/events`),
    );
  });

  test("an address that is not an analysis id is not looked up", async ({ page, serve }) => {
    const api = await serve("empty");
    await page.goto("/app/analyses/not-an-id");
    await expect(page.getByText("Ten adres nie wskazuje żadnej Twojej analizy.")).toBeVisible();
    expect(api.requests.some((r) => r.path.startsWith("/api/audits/"))).toBe(false);
  });

  test("an analysis that is not the person's is 'not found', never 'forbidden'", async ({ page, serve }) => {
    await serve("unknownAudit");
    await page.goto("/app/analyses/00000000-0000-4000-8000-000000000999");
    await expect(page.getByRole("alert")).toContainText("Nie znaleziono analizy");
    await expect(page.getByRole("alert")).not.toContainText(/dostęp|zabroni/i);
    await exercise("report.all.notfound", async () => {
      await page.getByRole("alert").getByRole("link", { name: "Moje analizy" }).click();
      return [await outcome.url(page, /\/app\/analyses$/)];
    });
  });

  test("an analysis that cannot be loaded says so and can be retried", async ({ page, serve }) => {
    const api = await serve("auditUnavailable");
    await page.goto("/app/analyses/00000000-0000-4000-8000-000000000999");
    await expect(page.getByRole("alert")).toBeVisible();
    await exercise("report.retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [
        await outcome.request(api, {
          method: "GET",
          path: "/api/audits/00000000-0000-4000-8000-000000000999",
        }),
      ];
    });
  });
});
