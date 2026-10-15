/**
 * The P0 journey in a real browser against the real stack (FRONTEND-PLAN.md FE-07): sign in -> paste a listing ->
 * a report is reserved -> the server's progress -> the result and what happened to the credit.
 *
 * EVIDENCE CLASS: fake provider data. The listings are hand-built and anonymised, planted fresh in Postgres by
 * `scripts/e2e_session.py plant-listing` (so the worker makes no Otodom request); the real adapters read them and
 * hand-built rental comparables; there is no OpenRouter key, so a success is `succeeded_degraded`. This says
 * nothing about Otodom, OpenRouter or the quality of a report.
 */
import { execFileSync } from "node:child_process";

import { expect, test, type Page } from "@playwright/test";

interface Seeded {
  user_id: string;
  email: string;
  cookie_name: string;
  cookie_value: string;
}

interface Planted {
  ref: string;
  stem: string;
}

const COMPOSE = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");

function script(...args: string[]): Record<string, unknown> {
  const [command = "docker", ...rest] = COMPOSE;
  const output = execFileSync(
    command,
    [...rest, "exec", "-T", "api", "python", "scripts/e2e_session.py", ...args],
    { encoding: "utf8" },
  );
  return JSON.parse(output.trim().split("\n").at(-1) ?? "{}") as Record<string, unknown>;
}

let seeded: Seeded;
const planted: Planted[] = [];

test.beforeAll(() => {
  seeded = script("create", "--credits", "3") as unknown as Seeded;
});

test.afterAll(() => {
  // The user first: deleting it cascades the audits, which the planted listings' rows are referenced from.
  script("delete", seeded.user_id);
  for (const item of planted) script("unplant", "--ref", item.ref, "--stem", item.stem);
});

async function signIn(page: Page, baseURL: string | undefined): Promise<void> {
  await page.context().addCookies([
    {
      name: seeded.cookie_name,
      value: seeded.cookie_value,
      url: baseURL ?? "http://localhost:4173",
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ]);
}

function plant(kind: "sale" | "rent"): Planted {
  const item = script("plant-listing", "--kind", kind) as unknown as Planted;
  planted.push(item);
  return item;
}

async function balance(page: Page): Promise<number> {
  const reply = await page.request.get("/api/me");
  return ((await reply.json()) as { credit_balance: number }).credit_balance;
}

async function submit(page: Page, ref: string): Promise<void> {
  await page.goto("/app/analyses/new");
  await page
    .getByRole("textbox", { name: "Adres ogłoszenia lub numer" })
    .fill(`https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-${ref}`);
  await page.getByRole("button", { name: "Rozpocznij analizę" }).click();
  await expect(page).toHaveURL(/\/app\/analyses\/[0-9a-f-]{36}$/);
}

test("a sale listing: submitted, watched live, finished, the report kept", async ({ page, baseURL }) => {
  test.setTimeout(180_000);
  await signIn(page, baseURL);
  const before = await balance(page);
  const item = plant("sale");
  await submit(page, item.ref);
  const result = page.getByRole("region", { name: "Wynik analizy" });
  await expect(result).toContainText(/Analiza gotowa|Gotowa, mniej pewna/, { timeout: 150_000 });
  await expect(result).toContainText("Raport został pobrany z konta.");
  expect(await balance(page)).toBe(before - 1);
});

test("a rental listing is rejected and the report is given back", async ({ page, baseURL }) => {
  test.setTimeout(180_000);
  await signIn(page, baseURL);
  const before = await balance(page);
  const item = plant("rent");
  await submit(page, item.ref);
  const result = page.getByRole("region", { name: "Wynik analizy" });
  await expect(result).toContainText("To ogłoszenie wynajmu", { timeout: 150_000 });
  await expect(result).toContainText("Raport nie został pobrany z konta.");
  expect(await balance(page)).toBe(before);
});

test("an address that is not an Otodom listing is refused by the real API as a field error", async ({
  page,
  baseURL,
}) => {
  await signIn(page, baseURL);
  const before = await balance(page);
  await page.goto("/app/analyses/new");
  await page
    .getByRole("textbox", { name: "Adres ogłoszenia lub numer" })
    .fill("https://example.test/nie-otodom");
  await page.getByRole("button", { name: "Rozpocznij analizę" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Popraw 1 pole" })).toBeVisible();
  expect(await balance(page)).toBe(before);
});
