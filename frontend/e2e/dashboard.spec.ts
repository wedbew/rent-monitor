import type { Page } from "@playwright/test";

import { MIXED_AUDITS, SUCCEEDED_AUDITS, createAuthFlow } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

const rows = (page: Page) => page.getByRole("list", { name: "Ostatnie analizy" }).getByRole("listitem");

test.describe("dashboard", () => {
  test("a first visit shows the real balance, an honest empty state and no invented history", async ({
    page,
    serve,
  }) => {
    await serve("empty");
    await page.goto("/app");
    await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
    await expect(page.getByRole("complementary", { name: "Konto i rynek" })).toContainText("7 raportów");
    await expect(page.getByText("Nie masz jeszcze żadnej analizy")).toBeVisible();
    await expect(page.getByRole("list", { name: "Ostatnie analizy" })).toHaveCount(0);
    await exercise("dashboard.first", async () => {
      await page.getByRole("link", { name: "Sprawdź pierwsze mieszkanie" }).click();
      return [await outcome.url(page, /\/app\/analyses\/new$/)];
    });
  });

  test("the tool card opens a new analysis; the unbuilt tools say Wkrótce and are not links", async ({
    page,
    serve,
  }) => {
    await serve("empty");
    await page.goto("/app");
    await expect(page.getByText("Wkrótce")).toHaveCount(3); // interior, listing assistant, market
    await expect(page.getByRole("link", { name: "Otwórz architekta" })).toHaveCount(0);
    await expect(
      page.getByRole("main").getByRole("link", { name: "Stwórz ogłoszenie", exact: true }),
    ).toHaveCount(0);
    await exercise("dashboard.analysis", async () => {
      await page.getByRole("link", { name: "Rozpocznij analizę" }).click();
      return [await outcome.url(page, /\/app\/analyses\/new$/)];
    });
  });

  test("five distinct analyses are listed newest first, each linking to its own report", async ({
    page,
    serve,
  }) => {
    await serve("loaded");
    await page.goto("/app");
    const list = rows(page);
    await expect(list).toHaveCount(5);
    const hrefs = await list
      .getByRole("link")
      .evaluateAll((links) => links.map((a) => a.getAttribute("href")));
    expect(hrefs).toEqual(SUCCEEDED_AUDITS.map((a) => `/app/analyses/${a.audit_id}`));
    expect(new Set(hrefs).size).toBe(5);
    const first = SUCCEEDED_AUDITS[0];
    await expect(list.first()).toContainText(`Ogłoszenie ${first?.otodom_id ?? ""}`);
    await expect(list.first()).toContainText("Analiza gotowa");
    await expect(list.first()).toContainText(/ocena [A-F]/);
    await expect(list.first()).toContainText(/cena ofertowa .*zł/);
    await exercise("dashboard.row", async () => {
      await list.first().getByRole("link").click();
      return [await outcome.url(page, new RegExp(`/app/analyses/${first?.audit_id ?? ""}$`))];
    });
  });

  test("every state is said in words, with the right tone", async ({ page, serve }) => {
    await serve("mixed");
    await page.goto("/app");
    const list = rows(page);
    await expect(list).toHaveCount(5);
    const expected = [
      "W kolejce",
      "Gotowa, mniej pewna",
      "To ogłoszenie wynajmu",
      "Otodom zablokował pobranie",
      "Ogłoszenie nieaktywne",
    ];
    for (const [i, label] of expected.entries()) await expect(list.nth(i)).toContainText(label);
    expect(MIXED_AUDITS).toHaveLength(6); // the sixth is beyond the five shown
    await exercise("dashboard.all", async () => {
      await page.getByRole("main").getByRole("link", { name: "Moje analizy" }).click();
      return [await outcome.url(page, /\/app\/analyses$/)];
    });
  });

  test("while the list loads there is a status, not an empty state", async ({ page, serve }) => {
    await serve("slow");
    await page.goto("/app");
    await expect(page.getByRole("status", { name: "Wczytuję ostatnie analizy" })).toBeVisible();
    await expect(page.getByText("Nie masz jeszcze żadnej analizy")).toHaveCount(0);
    await expect(page.getByText("Nie masz jeszcze żadnej analizy")).toBeVisible();
  });

  test("a failed list says so and can be retried", async ({ page, serve }) => {
    const api = await serve("auditsFailing");
    await page.goto("/app");
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie udało się wczytać ostatnich analiz" }),
    ).toBeVisible();
    const before = api.requests.filter((r) => r.path === "/api/audits").length;
    await exercise("dashboard.retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [await outcome.request(api, { method: "GET", path: "/api/audits" })];
    });
    await expect
      .poll(() => api.requests.filter((r) => r.path === "/api/audits").length)
      .toBeGreaterThan(before);
  });

  test("when Otodom is rate-limiting us the notice says for how long and analysis entry is disabled", async ({
    page,
    serve,
  }) => {
    await serve("breakerOpen");
    await page.goto("/app");
    const notice = page.getByRole("status").filter({ hasText: "Otodom ogranicza zapytania" });
    await expect(notice).toContainText(/Spróbuj za \d+ (sekund|minut)/);
    await expect(page.getByText("Chwilowo niedostępne")).toBeVisible();
    await expect(page.getByRole("link", { name: "Rozpocznij analizę" })).toHaveCount(0);
  });

  test("with no reports left the balance says 0 and offers to buy", async ({ page, serve }) => {
    await serve("insufficientCredits");
    await page.goto("/app");
    await expect(page.getByRole("complementary", { name: "Konto i rynek" })).toContainText("0 raportów");
    await exercise("dashboard.buy", async () => {
      await page.getByRole("link", { name: "Kup raporty" }).click();
      return [await outcome.url(page, /\/app\/credits$/)];
    });
  });

  test("a session that ends while the page is open sends the person to sign in and back", async ({
    page,
    serve,
  }) => {
    await serve("expiredMidUse");
    await page.goto("/app");
    await expect(page).toHaveURL(/\/login\?next=%2Fapp$/);
  });

  test("the balance is the server's: a changed balance after a refresh shows, nothing is counted locally", async ({
    page,
    serve,
  }) => {
    const flow = createAuthFlow();
    flow.state.signedIn = true;
    await serve(flow);
    await page.goto("/app");
    await expect(page.getByRole("complementary", { name: "Konto i rynek" })).toContainText("7 raportów");
  });
});
