/**
 * Rynek against the real stack: the built SPA, the real API and Postgres, and market data that
 * `scripts/e2e_session.py plant-market` publishes through the production corpus and summary code. Nothing under
 * `/api/market` is intercepted or replaced here. Every figure below is computed by hand from the hand-made offers
 * (see the helper) and, independently, by SQL (`market-db`), so a static page could not pass.
 *
 * Evidence class: fake provider data, a throwaway account and uniquely tagged places on the stack that runs it.
 * Needs the stack up: see frontend/README.md (Journey lane).
 */
import { execFileSync } from "node:child_process";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const COMPOSE = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");

function helper(...args: string[]): Record<string, unknown> {
  const [command = "docker", ...rest] = COMPOSE;
  const output = execFileSync(
    command,
    [...rest, "exec", "-T", "api", "python", "scripts/e2e_session.py", ...args],
    { encoding: "utf8" },
  );
  return JSON.parse(output.trim().split("\n").at(-1) ?? "{}") as Record<string, unknown>;
}

interface Seeded {
  user_id: string;
  email: string;
  cookie_name: string;
  cookie_value: string;
}
interface Planted {
  run: string;
  ids: Record<"alfa" | "beta" | "gamma" | "delta", string>;
  names: Record<"alfa" | "beta" | "gamma" | "delta", string>;
}

let user: Seeded;
let other: Seeded;
let free: Seeded;
let market: Planted;

async function signIn(context: BrowserContext, who: Seeded, baseURL: string | undefined) {
  await context.addCookies([
    {
      name: who.cookie_name,
      value: who.cookie_value,
      url: baseURL ?? "http://localhost:4173",
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ]);
}

const row = (page: Page, name: string) => page.getByRole("row", { name: new RegExp(name) });
/** "2 375" as a pattern for "2 375 zł": the formatter's separators are no-break spaces, which `\s` matches. */
const money = (digits: string) => new RegExp(`${digits.replace(" ", "\\s")}\\szł`);

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  user = helper("create", "--credits", "1", "--admin") as unknown as Seeded; // full Rynek access
  other = helper("create", "--credits", "1", "--admin") as unknown as Seeded;
  free = helper("create", "--credits", "1") as unknown as Seeded; // no pack, no Pro: the free tier
  market = helper("plant-market") as unknown as Planted;
});

test.afterAll(() => {
  if (market !== undefined) helper("unplant-market", "--run", market.run);
  if (user !== undefined) helper("delete", user.user_id);
  if (other !== undefined) helper("delete", other.user_id);
  if (free !== undefined) helper("delete", free.user_id);
});

test("navigation, search and the list show what the database holds, not a fixture", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  await page.goto("/app");
  await page.getByRole("link", { name: "Rynek", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/market$/);
  await expect(page.getByRole("heading", { level: 1, name: "Rynek" })).toBeVisible();

  await page.getByRole("textbox", { name: "Nazwa miejscowości" }).fill(market.run);
  await page.getByRole("button", { name: "Szukaj" }).click();
  await expect(page).toHaveURL(new RegExp(`\\?q=${market.run}$`));
  await expect(page.getByRole("table").getByRole("rowheader")).toHaveCount(4);
  await expect
    .poll(async () =>
      (await page.getByRole("table").getByRole("rowheader").allTextContents()).map((n) => n.trim()),
    )
    .toEqual(["alfa", "beta", "delta", "gamma"].map((k) => market.names[k as keyof Planted["names"]])); // Alfa, Beta, Delta, Gamma

  // By hand: 12 offers 2000..2550 plus 4 offers 3000..3150 -> 16 offers, median 2375.00, 47.50 PLN/m2.
  const alfa = row(page, market.names.alfa);
  await expect(alfa).toContainText("Aktualne");
  await expect(alfa).toContainText(money("2 375"));
  await expect(alfa).toContainText("47,50");
  await expect(alfa).toContainText("zł/m²");
  await expect(alfa.getByRole("cell").nth(3)).toHaveText("16");
  // Three priced offers are too few: counts stay, the median is withheld with its reason.
  const beta = row(page, market.names.beta);
  await expect(beta).toContainText("Za mało ofert z ceną, by podać medianę");
  await expect(beta.getByRole("cell").nth(3)).toHaveText("3");
  await expect(beta).not.toContainText("zł/m²");
  // No bootstrap yet, and a place that is only in the catalogue: no numbers at all.
  for (const key of ["gamma", "delta"] as const) {
    const unavailable = row(page, market.names[key]);
    await expect(unavailable).toContainText("Brak danych");
    await expect(unavailable).not.toContainText("zł");
  }

  // The same numbers by two other routes: the API's own answer and a SQL recomputation from the stored offers.
  const api = await page.request.get(`/api/market/locations?q=${market.run}`);
  expect(api.status()).toBe(200);
  expect(api.headers()["cache-control"]).toBe("private, no-store");
  const listed = (await api.json()) as { items: { location_id: string; median_rent_pln: string | null }[] };
  expect(listed.items.map((i) => i.location_id).sort()).toEqual(Object.values(market.ids).sort());
  const sql = helper("market-db", "--run", market.run) as Record<
    string,
    { offers: number; median_rent: string; median_ppm2: string }
  >;
  const fromSql = sql[market.ids.alfa];
  expect(fromSql).toEqual({ offers: 16, median_rent: "2375.00", median_ppm2: "47.50" });
  expect(listed.items.find((i) => i.location_id === market.ids.alfa)?.median_rent_pln).toBe("2375.00");
  expect(sql[market.ids.beta]?.offers).toBe(3);
  expect(sql[market.ids.gamma]).toBeUndefined();

  await page.reload();
  await expect(page.getByRole("textbox", { name: "Nazwa miejscowości" })).toHaveValue(market.run);
  await expect(page.getByRole("table").getByRole("rowheader")).toHaveCount(4);
});

test("a place shows its latest reading and a history whose days follow the stored offers", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  await page.goto(`/app/market?q=${market.run}`);
  await page.getByRole("link", { name: market.names.alfa }).click();
  await expect(page).toHaveURL(new RegExp(`/app/market/${market.ids.alfa}\\?q=${market.run}$`));
  await expect(page.getByRole("heading", { level: 1, name: market.names.alfa })).toBeVisible();
  const latest = page.getByRole("region", { name: "Ostatni odczyt" });
  await expect(latest).toContainText(money("2 375"));
  await expect(latest).toContainText("47,50");
  await expect(latest).toContainText("Oferty z ceną");

  // Six published days, newest first. The four late offers arrived two days ago: before that the median is 2275.
  const days = page.getByRole("table").getByRole("rowheader");
  await expect(days).toHaveCount(6);
  const rents = await page.getByRole("table").getByRole("row").allTextContents();
  const body = rents.slice(1);
  expect(body.slice(0, 3).every((r) => money("2 375").test(r))).toBe(true);
  expect(body.slice(3).every((r) => money("2 275").test(r))).toBe(true);

  // 2 pokoje holds every offer (all are two-room), so the same figures; the choice is in the address and survives a reload.
  await page.getByRole("combobox", { name: "Grupa mieszkań" }).click();
  await page.getByRole("option", { name: "2 pokoje", exact: true }).click();
  await expect(page).toHaveURL(/cohort=rooms_2/);
  await expect(page.getByRole("region", { name: "Ostatni odczyt" })).toContainText(money("2 375"));
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Grupa mieszkań" })).toContainText("2 pokoje");

  // The additions series is a different thing: the 12 first offers on their day, the 4 late ones (too few) later;
  // the days between have no row at all, not a row of zeros.
  await page.getByRole("button", { name: "Nowe ogłoszenia dnia" }).click();
  await expect(page).toHaveURL(/series=additions/);
  const additions = page.getByRole("table").getByRole("row");
  await expect(additions.filter({ hasText: money("2 275") })).toHaveCount(1);
  await expect(additions.filter({ hasText: "Za mało ofert z ceną" }).first()).toBeVisible();
  const api = await page.request.get(
    `/api/market/locations/${market.ids.alfa}/history?series=additions&cohort=rooms_2&days=30`,
  );
  const points = ((await api.json()) as { points: { priced_count: number; series: string }[] }).points;
  expect(points.every((p) => p.series === "additions")).toBe(true);
  expect(points.map((p) => p.priced_count).sort((a, b) => a - b)).toEqual([4, 12]); // days without 2-room offers have no row

  await page.goBack();
  await expect(page).not.toHaveURL(/series=additions/);
  await page.goForward();
  await expect(page.getByRole("button", { name: "Nowe ogłoszenia dnia" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("freshness follows the checkpoint on the API's own clock: delayed, then stale, then stale with a gap", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  const place = `/app/market/${market.ids.alfa}`;
  await page.goto(place);
  await expect(page.getByText("Aktualne", { exact: true }).first()).toBeVisible();

  helper("age-market", "--run", market.run, "--hours", "40");
  await page.reload();
  await expect(page.getByText("Opóźnione", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Ostatnie odświeżenie jest starsze niż zwykle/)).toBeVisible();

  helper("age-market", "--run", market.run, "--hours", "100");
  await page.reload();
  await expect(page.getByText("Nieaktualne", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Traktuj liczby jako historyczne/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Ostatni odczyt" })).toBeVisible(); // last valid data stays

  helper("age-market", "--run", market.run, "--hours", "1", "--gap-days", "1");
  await page.reload();
  await expect(page.getByText(/Luka w zbieraniu ofert od/)).toBeVisible();
  await expect(page.getByText("Nieaktualne", { exact: true }).first()).toBeVisible();
});

test("a place with no bootstrap and an unknown place are honest, and the data needs a session", async ({
  browser,
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  await page.goto(`/app/market/${market.ids.gamma}`);
  await expect(page.getByText(/nie zakończyło się jeszcze pierwsze zbieranie ofert/)).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.goto("/app/market/e2e-nie-ma-takiej");
  await expect(page.getByText("Nie ma takiej miejscowości")).toBeVisible();

  // Without a session the API refuses and the page sends the person to sign in.
  const anonymous = await browser.newContext({ baseURL: baseURL ?? "http://localhost:4173" });
  const apiReply = await anonymous.request.get(`/api/market/locations?q=${market.run}`);
  expect(apiReply.status()).toBe(401);
  expect((await apiReply.json()) as { code: string }).toMatchObject({ code: "UNAUTHENTICATED" });
  const visitor = await anonymous.newPage();
  await visitor.goto(`/app/market?q=${market.run}`);
  await expect(visitor).toHaveURL(/\/login\?next=/);
  await expect(visitor.getByText(market.names.alfa)).toHaveCount(0);
  await anonymous.close();

  // Another account reads the same shared figures and nothing of the first account's browsing.
  const second = await browser.newContext({ baseURL: baseURL ?? "http://localhost:4173" });
  await signIn(second, other, baseURL);
  const secondPage = await second.newPage();
  await secondPage.goto(`/app/market?q=${market.run}`);
  await expect(secondPage.getByRole("table").getByRole("rowheader")).toHaveCount(4);
  await expect(secondPage.getByRole("textbox", { name: "Nazwa miejscowości" })).toHaveValue(market.run);
  await second.close();
});

test("a free account on the real stack sees the cap and only places with a sufficient sample", async ({
  page,
  context,
  baseURL,
}) => {
  await signIn(context, free, baseURL);
  await page.goto(`/app/market?view=list&q=${market.run}`);
  // A free account is shown only the places whose published sample is sufficient (12 priced offers or more);
  // the places of this run with fewer are closed to it, so the full count is never reached.
  await expect(page.getByRole("table").getByRole("rowheader")).not.toHaveCount(4);
  const overview = (await (await page.request.get("/api/market/overview")).json()) as {
    access: string;
    visible_places: number;
    total_places: number;
  };
  expect(overview.access).toBe("free");
  expect(overview.visible_places).toBeLessThan(overview.total_places); // the cap is enforced by the server
  await page.goto("/app/market");
  await expect(page.getByText(/Konto darmowe: widzisz \d+ z \d+ miejsc/)).toBeVisible();
});
