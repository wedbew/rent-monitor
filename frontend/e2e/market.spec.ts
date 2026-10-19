import type { Locator, Page } from "@playwright/test";

import { createMarket, type Scenario } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

const rows = (page: Page) => page.getByRole("table").getByRole("rowheader");
const more = (page: Page) => page.getByRole("button", { name: "Załaduj więcej" });
const search = (page: Page) => page.getByRole("textbox", { name: "Nazwa miejscowości" });
const names = async (page: Page) => (await rows(page).allTextContents()).map((n) => n.trim());
const pressed = (page: Page, name: string) => page.getByRole("button", { name, exact: true });

/** Choose from the styled select the way a person does: open it, pick the option. */
async function choose(select: Locator, label: string): Promise<void> {
  await select.click();
  await select.page().getByRole("option", { name: label, exact: true }).click();
}

/** The same market, but a search for `q` answers late: the shape of a slow network. */
function slowFor(slowQ: string, delayMs: number): Scenario {
  const market = createMarket();
  return {
    ...market,
    routes: market.routes.map((route) =>
      route.operation !== "GET /api/market/locations" || typeof route.reply !== "function"
        ? route
        : {
            ...route,
            reply: (request) => {
              const answer = (route.reply as (r: typeof request) => object)(request);
              return request.url.searchParams.get("q") === slowQ ? { ...answer, delayMs } : answer;
            },
          },
    ) as Scenario["routes"],
  };
}

test.describe("Rynek: the list", () => {
  test("shows the places in order with their freshness, a sample and an honest cell where data is missing", async ({
    page,
    serve,
  }) => {
    const market = createMarket();
    await serve(market);
    await page.goto("/app/market");
    await expect(rows(page)).toHaveCount(30);
    expect((await names(page)).slice(0, 3)).toEqual(market.places.slice(0, 3).map((p) => p.name));
    const kielce = page.getByRole("row", { name: /Kielce/ });
    await expect(kielce).toContainText("Brak danych");
    await expect(kielce).toContainText("nie obliczono");
    await expect(kielce).not.toContainText("zł");
    await expect(page.getByRole("row", { name: /Elbląg/ })).toContainText("Za mało ofert z ceną");
    await expect(page.getByRole("row", { name: /Gdańsk/ })).toContainText("zł/m²");
    await exercise("market.place", async () => {
      await page.getByRole("link", { name: "Białystok" }).click();
      return [await outcome.url(page, /\/app\/market\/bialystok$/)];
    });
    await expect(page.getByRole("heading", { level: 1, name: "Białystok" })).toBeVisible();
  });

  test("pages by cursor: 30 then 8, each place once, the end only when the server says so", async ({
    page,
    serve,
  }) => {
    const api = await serve("market");
    await page.goto("/app/market");
    await expect(rows(page)).toHaveCount(30);
    await expect(page.getByRole("status").filter({ hasText: "Wyświetlono 30 miejscowości" })).toBeVisible();
    await exercise("market.more", async () => {
      await more(page).click();
      return [await outcome.request(api, { method: "GET", path: "/api/market/locations" })];
    });
    await expect(rows(page)).toHaveCount(38);
    expect(new Set(await names(page)).size).toBe(38);
    await expect(more(page)).toHaveCount(0);
    await expect(page.getByText("To wszystkie miejscowości (38).")).toBeVisible();
    expect(api.requests.filter((r) => r.query.includes("cursor="))).toHaveLength(1);
  });

  test("the search is in the address, reloads, and is what the API was asked for", async ({
    page,
    serve,
  }) => {
    const api = await serve("market");
    await page.goto("/app/market");
    await expect(rows(page)).toHaveCount(30);
    await exercise("market.search", async () => {
      await search(page).fill("gd");
      return [await outcome.value(search(page), "gd")];
    });
    await exercise("market.search.submit", async () => {
      await page.getByRole("button", { name: "Szukaj" }).click();
      return [await outcome.url(page, /\/app\/market\?q=gd$/)];
    });
    await expect(rows(page)).toHaveCount(2);
    await expect.poll(() => names(page)).toEqual(["Gdańsk", "Gdynia"]);
    expect(api.requests.some((r) => r.query.includes("q=gd"))).toBe(true);
    await page.reload();
    await expect(search(page)).toHaveValue("gd");
    await expect.poll(() => names(page)).toEqual(["Gdańsk", "Gdynia"]);
  });

  test("Enter in the field searches, Back and Forward restore each search", async ({ page, serve }) => {
    await serve("market");
    await page.goto("/app/market");
    await expect(rows(page)).toHaveCount(30);
    await search(page).fill("toru");
    await search(page).press("Enter");
    await expect(page).toHaveURL(/\?q=toru$/);
    await expect.poll(() => names(page)).toEqual(["Toruń"]);
    await page.goBack();
    await expect(page).toHaveURL(/\/app\/market$/);
    await expect(rows(page)).toHaveCount(30);
    await page.goForward();
    await expect.poll(() => names(page)).toEqual(["Toruń"]);
  });

  test("a slow answer to an earlier search never replaces the latest one", async ({ page, serve }) => {
    await serve(slowFor("gd", 1500));
    await page.goto("/app/market");
    await expect(rows(page)).toHaveCount(30);
    await search(page).fill("gd");
    await search(page).press("Enter");
    await search(page).fill("toru");
    await search(page).press("Enter");
    await expect.poll(() => names(page)).toEqual(["Toruń"]);
    await page.waitForTimeout(2000); // the late answer for "gd" has arrived by now
    await expect.poll(() => names(page)).toEqual(["Toruń"]);
    await expect(page).toHaveURL(/\?q=toru$/);
  });

  test("no match and an empty catalogue are different messages; clearing brings the list back", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market?q=zzzz");
    await expect(page.getByText("Żadna miejscowość nie pasuje do wyszukiwania")).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
    await exercise("market.clear", async () => {
      await page.getByRole("button", { name: "Wyczyść wyszukiwanie" }).click();
      return [await outcome.url(page, /\/app\/market$/)];
    });
    await expect(rows(page)).toHaveCount(30);
  });

  test("with nothing published the page says so and shows no number", async ({ page, serve }) => {
    await serve("empty");
    await page.goto("/app/market");
    await expect(page.getByText("Nie ma jeszcze danych rynkowych")).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.getByText(/\d\s?zł/)).toHaveCount(0);
  });

  test("a failed list says so and can be retried", async ({ page, serve }) => {
    const api = await serve("marketListFailing");
    await page.goto("/app/market");
    await expect(page.getByRole("alert").filter({ hasText: "Nie udało się wczytać rynku" })).toBeVisible({
      timeout: 15_000,
    });
    await exercise("market.retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [await outcome.request(api, { method: "GET", path: "/api/market/locations" })];
    });
  });

  test("a failed next page keeps the places and the same button works again", async ({ page, serve }) => {
    const market = createMarket({ failPage: 1 });
    await serve(market);
    await page.goto("/app/market");
    await expect(rows(page)).toHaveCount(30);
    await more(page).click();
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie udało się wczytać kolejnych miejscowości" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(rows(page)).toHaveCount(30);
    market.state.failing = false;
    await more(page).click();
    await expect(rows(page)).toHaveCount(38);
  });

  test("a session that ends while the list is open sends the person to sign in with no market data left", async ({
    page,
    serve,
  }) => {
    const market = createMarket();
    const expired: Scenario = {
      ...market,
      routes: market.routes.map((route) =>
        route.operation !== "GET /api/market/locations"
          ? route
          : {
              ...route,
              reply: (request) =>
                request.url.searchParams.has("cursor")
                  ? {
                      status: 401,
                      body: {
                        type: "urn:rentmonitor:problem:UNAUTHENTICATED",
                        title: "Sign in required",
                        status: 401,
                        code: "UNAUTHENTICATED",
                        instance: "/api/market/locations",
                        detail: null,
                        errors: null,
                        request_id: "req_fixture",
                      },
                      contentType: "application/problem+json",
                    }
                  : (route.reply as (r: typeof request) => never)(request),
            },
      ),
    };
    await serve(expired);
    await page.goto("/app/market");
    await expect(rows(page)).toHaveCount(30);
    await more(page).click();
    await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fmarket$/);
    await expect(page.getByText("Białystok")).toHaveCount(0);
  });
});

test.describe("Rynek: one place", () => {
  test("shows the status, the latest reading, a history without invented days, and how to read it", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/torun");
    await expect(page.getByRole("heading", { level: 1, name: "Toruń" })).toBeVisible();
    await expect(page.getByText("Aktualne", { exact: true }).first()).toBeVisible();
    const latest = page.getByRole("region", { name: "Ostatni odczyt" });
    await expect(latest).toContainText("Mediana czynszu");
    await expect(latest).toContainText("zł/m²");
    await expect(latest).toContainText("19 października 2026");
    const table = page.getByRole("table");
    const dates = await table.getByRole("rowheader").allTextContents();
    expect(dates[0]).toContain("19 października 2026"); // newest first
    expect(dates.length).toBeGreaterThan(60);
    expect(dates.length).toBeLessThan(90); // gap days are absent, not rows of zeros
    expect(new Set(dates).size).toBe(dates.length);
    await expect(table).not.toContainText("0,00");
    await expect(page.getByText("To ceny z ogłoszeń, a nie czynsze zapłacone w umowach.")).toBeVisible();
    await expect(page.getByText("To nie są ceny transakcyjne z aktów notarialnych.")).toBeVisible();
    await expect(pressed(page, "Okno 90 dni")).toHaveAttribute("aria-pressed", "true");
    await expect(pressed(page, "90 dni")).toHaveAttribute("aria-pressed", "true");
  });

  test("series, period and cohort live in the address: change, reload, Back and Forward", async ({
    page,
    serve,
  }) => {
    test.setTimeout(60_000); // twelve registered controls are exercised in one visit
    const api = await serve("market");
    await page.goto("/app/market/torun?q=to");
    await expect(page.getByRole("table")).toBeVisible();
    await exercise("market.place.series.additions", async () => {
      await pressed(page, "Nowe ogłoszenia dnia").click();
      return [await outcome.url(page, /series=additions/)];
    });
    await expect(page.getByText(/Dni nie wolno łączyć z oknem 90 dni/)).toBeVisible();
    await exercise("market.place.period.30", async () => {
      await pressed(page, "30 dni").click();
      return [await outcome.url(page, /days=30/)];
    });
    await expect.poll(() => page.getByRole("table").getByRole("rowheader").count()).toBeLessThan(31);
    await exercise("market.place.cohort", async () => {
      await choose(page.getByRole("combobox", { name: "Grupa mieszkań" }), "2 pokoje");
      return [await outcome.url(page, /cohort=rooms_2/)];
    });
    await exercise("market.place.cohort.option.rooms_2", async () => {
      await choose(page.getByRole("combobox", { name: "Grupa mieszkań" }), "2 pokoje");
      return [await outcome.url(page, /cohort=rooms_2/)];
    });
    await exercise("market.place.cohort.option.size_45_60", async () => {
      await choose(page.getByRole("combobox", { name: "Grupa mieszkań" }), "45–60 m²");
      return [await outcome.url(page, /cohort=size_45_60/)];
    });
    await exercise("market.place.cohort.option.all", async () => {
      await choose(page.getByRole("combobox", { name: "Grupa mieszkań" }), "Wszystkie");
      return [await outcome.url(page, /^(?!.*cohort=).*$/)];
    });
    await exercise("market.place.period.365", async () => {
      await pressed(page, "365 dni").click();
      return [await outcome.url(page, /days=365/)];
    });
    await exercise("market.place.period.90", async () => {
      await pressed(page, "90 dni").click();
      return [await outcome.url(page, /^(?!.*days=).*$/)];
    });
    await exercise("market.place.series.cohort", async () => {
      await pressed(page, "Okno 90 dni").click();
      return [await outcome.url(page, /^(?!.*series=).*$/)];
    });
    expect(
      api.requests.some((r) => r.query.includes("series=additions") && r.query.includes("days=30")),
    ).toBe(true);
    // Back restores the previous selection; a reload keeps the one in the address.
    await choose(page.getByRole("combobox", { name: "Grupa mieszkań" }), "2 pokoje");
    await expect(page).toHaveURL(/cohort=rooms_2/);
    await page.goBack();
    await expect(page).not.toHaveURL(/cohort=/);
    await page.goForward();
    await page.reload();
    await expect(page.getByRole("combobox", { name: "Grupa mieszkań" })).toContainText("2 pokoje");
    await expect(page).toHaveURL(/q=to/);
  });

  test("the cohort select opens a labelled list of the cohorts the API published", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/torun");
    const select = page.getByRole("combobox", { name: "Grupa mieszkań" });
    await exercise("market.place.cohort.listbox", async () => {
      await select.click();
      const list = page.getByRole("listbox", { name: "Grupa mieszkań" });
      await expect(list).toBeVisible();
      await expect(list.getByRole("option")).toHaveText(["Wszystkie", "2 pokoje", "45–60 m²"]);
      const opened = await outcome.state(select, "aria-expanded", "true");
      await page.keyboard.press("Escape");
      return [opened];
    });
  });

  test("an address with values outside the vocabulary falls back to the defaults", async ({
    page,
    serve,
  }) => {
    const api = await serve("market");
    await page.goto("/app/market/torun?series=deed&cohort=zzz&days=7");
    await expect(page.getByRole("table")).toBeVisible();
    await expect(pressed(page, "Okno 90 dni")).toHaveAttribute("aria-pressed", "true");
    const history = api.requests.filter((r) => r.path.endsWith("/history"));
    expect(history.every((r) => r.query.includes("series=cohort") && r.query.includes("days=90"))).toBe(true);
    expect(history.some((r) => r.query.includes("deed") || r.query.includes("zzz"))).toBe(false);
  });

  test("a small sample keeps its counts and withholds the numbers with the reason", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/elblag");
    const latest = page.getByRole("region", { name: "Ostatni odczyt" });
    await expect(latest).toContainText("Za mało ofert z ceną, by podać medianę");
    await expect(latest).toContainText("Oferty z ceną");
    await expect(latest).not.toContainText("0,00");
  });

  test("an unavailable place has a state and no numbers or controls", async ({ page, serve }) => {
    const api = await serve("market");
    await page.goto("/app/market/kielce");
    await expect(page.getByText(/nie zakończyło się jeszcze pierwsze zbieranie ofert/)).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
    await expect(page.getByRole("group", { name: "Okres" })).toHaveCount(0);
    expect(api.requests.some((r) => r.path.endsWith("/history"))).toBe(false);
  });

  test("a stale place says the numbers are historical and names the gap", async ({ page, serve }) => {
    await serve("market");
    await page.goto("/app/market/bytom");
    await expect(page.getByText("Nieaktualne", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/Traktuj liczby jako historyczne/)).toBeVisible();
    await expect(page.getByText(/Luka w zbieraniu ofert od 14 października 2026/)).toBeVisible();
  });

  test("an unknown place is a calm not-found, and the way back keeps the search", async ({ page, serve }) => {
    await serve("market");
    await page.goto("/app/market/nie-ma-takiej?q=gd");
    await expect(page.getByText("Nie ma takiej miejscowości")).toBeVisible();
    await exercise("market.place.back", async () => {
      await page.getByRole("link", { name: "Wszystkie miejscowości" }).click();
      return [await outcome.url(page, /\/app\/market\?q=gd$/)];
    });
    await expect(rows(page)).toHaveCount(2);
    await expect.poll(() => names(page)).toEqual(["Gdańsk", "Gdynia"]);
  });

  test("a place that cannot be read can be retried", async ({ page, serve }) => {
    const api = await serve(createMarket({ detailFails: true }));
    await page.goto("/app/market/torun");
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie udało się wczytać miejscowości" }),
    ).toBeVisible({
      timeout: 15_000,
    });
    await exercise("market.place.detail-retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [await outcome.request(api, { method: "GET", path: "/api/market/locations/torun" })];
    });
  });

  test("a history that cannot be read keeps the place and can be retried", async ({ page, serve }) => {
    const api = await serve(createMarket({ historyFails: true }));
    await page.goto("/app/market/torun");
    await expect(page.getByRole("heading", { level: 1, name: "Toruń" })).toBeVisible();
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie udało się wczytać miejscowości" }),
    ).toBeVisible({
      timeout: 15_000,
    });
    await exercise("market.place.history-retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [await outcome.request(api, { method: "GET", path: "/api/market/locations/torun/history" })];
    });
  });

  test("a rate-limited history says to wait and does not hide the place", async ({ page, serve }) => {
    await serve(createMarket({ historyFails: "rate-limited" }));
    await page.goto("/app/market/torun");
    await expect(page.getByRole("heading", { level: 1, name: "Toruń" })).toBeVisible();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
  });

  test("a place with no published reading in the period says so instead of drawing zeros", async ({
    page,
    serve,
  }) => {
    await serve(createMarket({ historyEmpty: true }));
    await page.goto("/app/market/torun");
    await expect(page.getByText("Brak odczytów w wybranym okresie")).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
  });
});

test.describe("Rynek: the way in", () => {
  test("the Pulpit offers it and it opens the market page", async ({ page, serve }) => {
    await serve("market");
    await page.goto("/app");
    await expect(page.getByText("Przegląd rynku najmu i cen pojawi się")).toHaveCount(0);
    await exercise("dashboard.market", async () => {
      await page.getByRole("link", { name: "Otwórz Rynek" }).click();
      return [await outcome.url(page, /\/app\/market$/)];
    });
    await expect(page.getByRole("heading", { level: 1, name: "Rynek" })).toBeVisible();
  });
});
