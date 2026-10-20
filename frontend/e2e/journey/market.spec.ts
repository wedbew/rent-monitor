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
  await expect(page).toHaveURL(/\/app\/market\/otodom$/); // the Otodom tab is the default
  await expect(page.getByRole("heading", { level: 1, name: "Rynek" })).toBeVisible();

  await page.getByRole("button", { name: "Lista", exact: true }).click();
  await expect(page).toHaveURL(/view=list/);
  await page.getByRole("textbox", { name: "Szukaj miejsca na liście" }).fill(market.run);
  await expect(page).toHaveURL(new RegExp(`q=${market.run}`));
  const names = page.getByRole("table").getByRole("rowheader");
  await expect(names).toHaveCount(4);
  await expect
    .poll(async () => (await names.allTextContents()).map((n) => n.replace(/Otwórz miejsce.*$/, "").trim()))
    .toEqual(["alfa", "beta", "delta", "gamma"].map((k) => market.names[k as keyof Planted["names"]]));

  // By hand: 12 offers 2000..2550 plus 4 offers 3000..3150 -> 16 offers, median 2375.00, 47.50 PLN/m2.
  const alfa = row(page, market.names.alfa);
  await expect(alfa).toContainText("Aktualne");
  await expect(alfa).toContainText(money("2 375"));
  await expect(alfa).toContainText("47,50");
  await expect(alfa).toContainText("zł/m²");
  await expect(alfa.getByRole("cell").nth(3)).toHaveText("16");
  // Three priced offers are too few: counts stay, the median is withheld with its reason.
  const beta = row(page, market.names.beta);
  await expect(beta).toContainText("Za mało ofert z ceną (3), by podać medianę");
  await expect(beta).not.toContainText("zł/m²");
  for (const key of ["gamma", "delta"] as const) {
    const unavailable = row(page, market.names[key]);
    await expect(unavailable).toContainText("Brak danych");
    await expect(unavailable).not.toContainText("zł/m²");
  }

  // The same numbers by two other routes: the API's own answer and a SQL recomputation from the stored offers.
  const overview = await page.request.get("/api/market/overview");
  expect(overview.status()).toBe(200);
  expect(overview.headers()["cache-control"]).toBe("private, no-store");
  const listed = (await overview.json()) as {
    cohort_key: string;
    items: { location_id: string; median_rent_pln: string | null }[];
  };
  expect(listed.cohort_key).toBe("all");
  const mine = listed.items.filter((i) => Object.values(market.ids).includes(i.location_id));
  expect(mine.map((i) => i.location_id).sort()).toEqual(Object.values(market.ids).sort());
  const sql = helper("market-db", "--run", market.run) as Record<
    string,
    { offers: number; median_rent: string; median_ppm2: string }
  >;
  expect(sql[market.ids.alfa]).toEqual({ offers: 16, median_rent: "2375.00", median_ppm2: "47.50" });
  expect(mine.find((i) => i.location_id === market.ids.alfa)?.median_rent_pln).toBe("2375.00");
  expect(sql[market.ids.beta]?.offers).toBe(3);
  expect(sql[market.ids.gamma]).toBeUndefined();

  await page.reload();
  await expect(page.getByRole("textbox", { name: "Szukaj miejsca na liście" })).toHaveValue(market.run);
  await expect(page.getByRole("table").getByRole("rowheader")).toHaveCount(4);
});

test("the group of flats changes the request and the figures: two-room offers are all of them, other groups none", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  await page.goto(`/app/market/otodom?view=list&q=${market.run}`);
  const seen: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/market/overview")) seen.push(r.url());
  });
  await page.getByRole("radio", { name: "2 pokoje" }).click();
  await expect(page).toHaveURL(/cohort=rooms_2/);
  await expect.poll(() => seen.some((u) => u.includes("cohort=rooms_2"))).toBe(true);
  // Every planted offer has two rooms, so the two-room figures equal the whole-place figures.
  await expect(row(page, market.names.alfa)).toContainText(money("2 375"));
  // Every planted offer is 50 m2: the "below 30 m2" group has none, the 45 to 60 group has them all.
  await page.getByRole("radio", { name: "Poniżej 30 m²" }).click();
  await expect(page).toHaveURL(/cohort=size_lt30/);
  await expect(page.getByText(/Zastąpiono filtr „2 pokoje”/)).toBeVisible();
  await expect(row(page, market.names.alfa)).not.toContainText("zł/m²");
  await page.getByRole("radio", { name: "45 do 60 m²" }).click();
  await expect(row(page, market.names.alfa)).toContainText("47,50"); // 50 m2 is inside 45 to 60
  const api = (await (await page.request.get("/api/market/overview?cohort=size_45_60")).json()) as {
    cohort_key: string;
    items: { location_id: string; priced_count: number | null }[];
  };
  expect(api.cohort_key).toBe("size_45_60");
  expect(api.items.find((i) => i.location_id === market.ids.alfa)?.priced_count).toBe(16);
  expect((await page.request.get("/api/market/overview?cohort=hacked")).status()).toBe(422);
  await page.reload();
  await expect(page.getByRole("radio", { name: "45 do 60 m²" })).toBeChecked();
  await page.getByRole("button", { name: "Wyczyść filtr" }).click();
  await expect(page).not.toHaveURL(/cohort=/);
});

test("a place shows its latest reading, its districts and a history whose days follow the stored offers", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  await page.goto(`/app/market/otodom?view=list&q=${market.run}`);
  await page.getByRole("link", { name: `Otwórz miejsce ${market.names.alfa}` }).click();
  await expect(page).toHaveURL(new RegExp(`/app/market/otodom/${market.ids.alfa}`));
  await expect(page.getByRole("heading", { level: 1, name: market.names.alfa })).toBeVisible();
  const median = page.getByRole("article").filter({ hasText: "Mediana ceny ofertowej za m²" });
  await expect(median).toContainText("47,50");
  await expect(median).toContainText("Źródło");
  await expect(page.getByRole("article").filter({ hasText: "Mediana czynszu ofertowego" })).toContainText(
    money("2 375"),
  );

  // Districts: 12 of the 16 offers carry "Centrum"; by hand its PLN/m2 are 40..51 -> median 45.50, quartiles 42.75 / 48.25.
  const districts = page
    .getByRole("region")
    .or(page.locator("section"))
    .filter({ has: page.getByRole("heading", { name: "Dzielnice" }) });
  await expect(districts.getByText("Dzielnicę wskazano przy 12 z 16 ofert")).toBeVisible();
  await page.getByRole("link", { name: "Centrum", exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Centrum" })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "Mediana ceny ofertowej za m²" })).toContainText(
    "45,50",
  );
  await expect(page.getByRole("article").filter({ hasText: "Środkowa połowa ofert" })).toContainText("42,75");
  const sqlDistricts = (await (
    await page.request.get(`/api/market/locations/${market.ids.alfa}/districts`)
  ).json()) as { coverage: string; districts: { name: string; priced_count: number; median_ppm2: string }[] };
  expect(sqlDistricts.coverage).toBe("supported");
  expect(sqlDistricts.districts.map((d) => [d.name, d.priced_count, d.median_ppm2])).toEqual([
    ["Centrum", 12, "45.50"],
  ]);
  await page.getByRole("link", { name: /^Wróć do: / }).click();

  // Six published days; the table equivalent of the chart lists them newest first. The four late offers arrived two
  // days ago: before that the median is 2275.
  await page.getByText("Pokaż dane w tabeli").first().click();
  const history = page.getByRole("table", { name: "Zmiana mediany w czasie" });
  await expect(history.getByRole("row")).toHaveCount(7); // header and six days
  const body = (await history.getByRole("row").allTextContents()).slice(1);
  expect(body.slice(0, 3).every((r) => r.includes("47,50"))).toBe(true);
  expect(body.slice(3).every((r) => r.includes("45,50"))).toBe(true);

  // The additions series is a different thing: days between have no row at all, not a row of zeros.
  await page.getByRole("button", { name: "Nowe ogłoszenia dnia" }).click();
  await expect(page).toHaveURL(/series=additions/);
  const api = await page.request.get(
    `/api/market/locations/${market.ids.alfa}/history?series=additions&cohort=rooms_2&days=30`,
  );
  const points = ((await api.json()) as { points: { priced_count: number; series: string }[] }).points;
  expect(points.every((p) => p.series === "additions")).toBe(true);
  expect(points.map((p) => p.priced_count).sort((a, b) => a - b)).toEqual([4, 12]);
  await page.goBack();
  await expect(page).not.toHaveURL(/series=additions/);
  await page.goForward();
  await expect(page.getByRole("button", { name: "Nowe ogłoszenia dnia" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("a place without districts says so; the district list never invents one", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  await page.goto(`/app/market/otodom/${market.ids.beta}`);
  await expect(page.getByText("Otodom nie wskazuje dzielnic dla tego miejsca")).toBeVisible();
  const api = (await (
    await page.request.get(`/api/market/locations/${market.ids.beta}/districts`)
  ).json()) as {
    coverage: string;
    districts: unknown[];
  };
  expect(api).toMatchObject({ coverage: "none", districts: [] });
});

test("the GUS tab and the ranking are reachable and honest when no GUS release is published for the place", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  await page.goto(`/app/market/otodom/${market.ids.alfa}`);
  await page.locator("[data-tab=gus]").click();
  await expect(page).toHaveURL(new RegExp(`/app/market/gus/${market.ids.alfa}$`));
  const card = page.getByTestId("ranking-card");
  await expect(card).toBeVisible();
  await expect(card.getByTestId("index-score")).toHaveCount(0); // planted places map to no gmina: no score, said plainly
  await expect(
    card.getByText(/Nie podajemy wyniku|Za mało danych|nie udało się jednoznacznie/).first(),
  ).toBeVisible();
});

test("freshness follows the checkpoint on the API's own clock: delayed, then stale, then stale with a gap", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, user, baseURL);
  const place = `/app/market/otodom/${market.ids.alfa}`;
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
  await expect(page.getByRole("article").filter({ hasText: "Mediana ceny ofertowej za m²" })).toBeVisible(); // last valid data stays

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
  await page.goto(`/app/market/otodom/${market.ids.gamma}`);
  await expect(
    page.getByText(/Pierwsze zbieranie ofert dla tego miejsca jeszcze się nie zakończyło/),
  ).toBeVisible();
  await page.goto("/app/market/otodom/e2e-nie-ma-takiej");
  await expect(page.getByText("Nie ma takiego miejsca")).toBeVisible();

  // Without a session the API refuses and the page sends the person to sign in.
  const anonymous = await browser.newContext({ baseURL: baseURL ?? "http://localhost:4173" });
  const apiReply = await anonymous.request.get("/api/market/overview");
  expect(apiReply.status()).toBe(401);
  expect((await apiReply.json()) as { code: string }).toMatchObject({ code: "UNAUTHENTICATED" });
  const visitor = await anonymous.newPage();
  await visitor.goto(`/app/market/otodom?q=${market.run}`);
  await expect(visitor).toHaveURL(/\/login\?next=/);
  await expect(visitor.getByText(market.names.alfa)).toHaveCount(0);
  await anonymous.close();

  // Another account reads the same shared figures and nothing of the first account's browsing.
  const second = await browser.newContext({ baseURL: baseURL ?? "http://localhost:4173" });
  await signIn(second, other, baseURL);
  const secondPage = await second.newPage();
  await secondPage.goto(`/app/market/otodom?view=list&q=${market.run}`);
  await expect(secondPage.getByRole("table").getByRole("rowheader")).toHaveCount(4);
  await second.close();
});

test("an account with the explicit no-limit entitlement sees the whole market while a free one is capped", async ({
  page,
  context,
  browser,
  baseURL,
}) => {
  await signIn(context, free, baseURL);
  await page.goto("/app/market/otodom");
  await expect(page.getByText(/Konto darmowe: widzisz \d+ z \d+ miejsc/)).toBeVisible();
  const cap = (await (await page.request.get("/api/market/overview")).json()) as {
    access: string;
    visible_places: number;
    total_places: number;
  };
  expect(cap.access).toBe("free");
  expect(cap.visible_places).toBeLessThan(cap.total_places); // the server enforces the cap

  // The entitlement is a row granted to the account (scripts/grant_entitlement.py), not a hard-coded address.
  helper("session-for", "--email", free.email, "--entitlement", "unlimited_reports");
  const entitled = await browser.newContext({ baseURL: baseURL ?? "http://localhost:4173" });
  await signIn(entitled, free, baseURL);
  const entitledPage = await entitled.newPage();
  await entitledPage.goto("/app/market/otodom");
  await expect(entitledPage.getByText("Pełny dostęp do rynku")).toBeVisible();
  const full = (await (await entitledPage.request.get("/api/market/overview")).json()) as {
    access: string;
    visible_places: number;
    total_places: number;
  };
  expect(full.access).toBe("full");
  expect(full.visible_places).toBe(full.total_places);
  const me = (await (await entitledPage.request.get("/api/me")).json()) as {
    plan: { unlimited_reports: boolean };
  };
  expect(me.plan.unlimited_reports).toBe(true);
  await entitled.close();
});
