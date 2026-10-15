import type { Page } from "@playwright/test";

import { createRun, RUN_AUDIT_ID } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";
import { fx } from "../test/fixtures";

const LISTING = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd";
const field = (page: Page) => page.getByRole("textbox", { name: "Adres ogłoszenia lub numer" });
const submit = (page: Page) => page.getByRole("button", { name: "Rozpocznij analizę" });

function problemReply(operation: string, name: string) {
  const fixture = fx(operation, name);
  return {
    status: fixture.status,
    body: fixture.body,
    contentType: fixture.content_type,
    headers: fixture.headers,
  };
}

test.describe("new analysis", () => {
  test("an empty form is refused before any request, with a summary that takes focus and links to the field", async ({
    page,
    serve,
  }) => {
    const api = await serve("empty");
    await page.goto("/app/analyses/new");
    await submit(page).click();
    const summary = page.getByRole("alert").filter({ hasText: "Popraw 1 pole" });
    await expect(summary).toBeFocused();
    await expect(field(page)).toHaveAttribute("aria-invalid", "true");
    expect(api.requests.filter((r) => r.method === "POST")).toEqual([]);
    await exercise("new.error.field", async () => {
      await summary.getByRole("link", { name: "Wklej adres ogłoszenia lub jego numer." }).click();
      return [await outcome.focus(field(page))];
    });
  });

  test("what is typed is what the form holds, and too long an address is refused", async ({
    page,
    serve,
  }) => {
    await serve("empty");
    await page.goto("/app/analyses/new");
    await exercise("new.field", async () => {
      await field(page).fill(LISTING);
      return [await outcome.value(field(page), LISTING)];
    });
    await field(page).fill(`https://www.otodom.pl/${"a".repeat(400)}`);
    await submit(page).click();
    await expect(page.getByRole("alert").filter({ hasText: "Popraw 1 pole" })).toBeVisible();
    await expect(page.getByText("Adres może mieć najwyżej 300 znaków.").first()).toBeVisible();
  });

  test("a submit sends exactly one request with the product's fixed options and opens the analysis", async ({
    page,
    serve,
  }) => {
    const run = createRun({ postDelayMs: 600 });
    const api = await serve(run);
    await page.goto("/app/analyses/new");
    await field(page).fill(`  ${LISTING}  `);
    await exercise("new.submit", async () => {
      // A double click and Enter on top of it: still one request (the form is busy while it is in flight).
      await submit(page).dblclick();
      await field(page).press("Enter");
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/audits",
          body: { listing_ref: LISTING, lang: "pl", analyst: false },
        }),
      ];
    });
    await expect(page).toHaveURL(new RegExp(`/app/analyses/${RUN_AUDIT_ID}$`));
    expect(run.state.posts).toBe(1);
    expect(api.requests.filter((r) => r.method === "POST" && r.path === "/api/audits")).toHaveLength(1);
  });

  test("pressing Enter in the field submits once", async ({ page, serve }) => {
    const run = createRun();
    await serve(run);
    await page.goto("/app/analyses/new");
    await field(page).fill(LISTING);
    await field(page).press("Enter");
    await expect(page).toHaveURL(new RegExp(`/app/analyses/${RUN_AUDIT_ID}$`));
    expect(run.state.posts).toBe(1);
  });

  test("the manual tab is announced as coming later and nothing hidden is sent; there is no cancel and no analyst option", async ({
    page,
    serve,
  }) => {
    await serve("empty");
    await page.goto("/app/analyses/new");
    await expect(page.getByText("Dane ręcznie · wkrótce")).toBeVisible();
    await expect(page.getByRole("textbox")).toHaveCount(1);
    await expect(page.getByRole("checkbox")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /anuluj|analityk/i })).toHaveCount(0);
  });

  test("when Otodom is rate-limiting us there is no form, only the notice with the retry time", async ({
    page,
    serve,
  }) => {
    await serve("breakerOpen");
    await page.goto("/app/analyses/new");
    await expect(page.getByRole("status").filter({ hasText: "Otodom ogranicza zapytania" })).toContainText(
      /Spróbuj za \d+/,
    );
    await expect(submit(page)).toHaveCount(0);
    await expect(field(page)).toHaveCount(0);
  });

  test("an address the API refuses (422) is a field error and the value stays", async ({ page, serve }) => {
    const run = createRun({ post: problemReply("POST /api/audits", "invalid_listing_ref") });
    await serve(run);
    await page.goto("/app/analyses/new");
    await field(page).fill("https://example.test/nie-otodom");
    await submit(page).click();
    await expect(page.getByRole("alert").filter({ hasText: "Popraw 1 pole" })).toBeVisible();
    await expect(
      page.getByText("Wklej adres ogłoszenia sprzedaży z Otodom albo jego numer.").first(),
    ).toBeVisible();
    await expect(field(page)).toHaveValue("https://example.test/nie-otodom");
    await expect(page).toHaveURL(/\/app\/analyses\/new$/);
    await exercise("new.error.listing", async () => {
      await page
        .getByRole("alert")
        .getByRole("link", { name: "Wklej adres ogłoszenia sprzedaży z Otodom albo jego numer." })
        .click();
      return [await outcome.focus(field(page))];
    });
  });

  test("a throttle (429) says when to try again; nothing is retried", async ({ page, serve }) => {
    const limited = problemReply("POST /api/auth/login", "rate_limited");
    const run = createRun({ post: { ...limited, headers: { ...limited.headers, "retry-after": "42" } } });
    await serve(run);
    await page.goto("/app/analyses/new");
    await field(page).fill(LISTING);
    await submit(page).click();
    await expect(page.getByRole("alert").filter({ hasText: /za 42 sekundy/ })).toBeVisible();
    expect(run.state.posts).toBe(1);
  });

  test("an analysis of the same listing already running (409) links to it", async ({ page, serve }) => {
    await serve(createRun({ post: problemReply("POST /api/audits", "already_in_progress") }));
    await page.goto("/app/analyses/new");
    await field(page).fill(LISTING);
    await submit(page).click();
    await exercise("new.existing", async () => {
      await page.getByRole("link", { name: "Otwórz analizę" }).click();
      return [await outcome.url(page, /\/app\/analyses\/00000000-0000-4000-8000-000000000025$/)];
    });
  });

  test("a dropped connection that did reach the server is found in the list and not submitted twice", async ({
    page,
    serve,
  }) => {
    const created = {
      audit_id: RUN_AUDIT_ID,
      otodom_id: "ID4abcd",
      status: "queued" as const,
      error_code: null,
      created_at: new Date().toISOString(),
      finished_at: null,
      grade: null,
      asking_price_pln: null,
      max_bid_pln: null,
    };
    const run = createRun({ post: { status: 0, networkError: true }, listAfterPost: [created] });
    const api = await serve(run);
    await page.goto("/app/analyses/new");
    await field(page).fill(LISTING);
    await submit(page).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Analiza tego ogłoszenia już istnieje" }),
    ).toBeVisible();
    expect(api.requests.some((r) => r.method === "GET" && r.path === "/api/audits")).toBe(true);
    expect(run.state.posts).toBe(1);
    await exercise("new.arrived", async () => {
      await page.getByRole("link", { name: "Zobacz postęp" }).click();
      return [await outcome.url(page, new RegExp(`/app/analyses/${RUN_AUDIT_ID}$`))];
    });
  });

  test("an unrelated recent analysis is not mistaken for the lost request", async ({ page, serve }) => {
    const other = {
      audit_id: "00000000-0000-4000-8000-0000000000b2",
      otodom_id: "IDOTHER1",
      status: "running" as const,
      error_code: null,
      created_at: new Date().toISOString(),
      finished_at: null,
      grade: null,
      asking_price_pln: null,
      max_bid_pln: null,
    };
    await serve(createRun({ post: { status: 0, networkError: true }, listAfterPost: [other] }));
    await page.goto("/app/analyses/new");
    await field(page).fill(LISTING);
    await submit(page).click();
    await expect(page.getByRole("alert").filter({ hasText: "Nie wiemy, czy analiza ruszyła" })).toBeVisible();
    await expect(page.getByText("Analiza tego ogłoszenia już istnieje")).toHaveCount(0);
  });

  test("when the list cannot be read either, the page says it does not know and does not guess", async ({
    page,
    serve,
  }) => {
    const run = createRun({ post: { status: 0, networkError: true }, listFails: true });
    await serve(run);
    await page.goto("/app/analyses/new");
    await field(page).fill(LISTING);
    await submit(page).click();
    await expect(page.getByRole("alert").filter({ hasText: "Nie wiemy, czy analiza ruszyła" })).toBeVisible();
    await exercise("new.check", async () => {
      await page.getByRole("link", { name: "Sprawdź w Moich analizach" }).click();
      return [await outcome.url(page, /\/app\/analyses$/)];
    });
  });

  test("with no reports left the API's 402 opens the paywall: buy, or close and keep the form", async ({
    page,
    serve,
  }) => {
    await serve("insufficientCredits");
    await page.goto("/app/analyses/new");
    await field(page).fill(LISTING);
    await submit(page).click();
    const dialog = page.getByRole("dialog", { name: "Nie masz już raportów" });
    await expect(dialog).toBeVisible();
    await exercise("new.paywall.close", async () => {
      await dialog.getByRole("button", { name: "Zamknij okno" }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    await expect(field(page)).toHaveValue(LISTING);
    await submit(page).click();
    await exercise("new.paywall.buy", async () => {
      await dialog.getByRole("link", { name: "Kup raporty" }).click();
      return [await outcome.url(page, /\/app\/credits$/)];
    });
  });
});
