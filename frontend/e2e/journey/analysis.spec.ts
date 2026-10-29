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

import { type Page } from "@playwright/test";

import { expect, test } from "./fixtures";

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

test("a sale listing: submitted, watched live, finished, the report kept", async ({
  page,
  baseURL,
  shot,
  a11y,
}) => {
  test.setTimeout(180_000);
  await signIn(page, baseURL);
  const before = await balance(page);
  const item = plant("sale");
  await submit(page, item.ref);
  await shot("submitted");
  // A finished run is the report: the listing id as heading, the section navigation, no result card.
  await expect(page.getByRole("heading", { level: 1, name: `Ogłoszenie ${item.ref}` })).toBeVisible({
    timeout: 150_000,
  });
  await expect(page.getByRole("navigation", { name: "Sekcje raportu" })).toBeVisible();
  await shot("report");
  await a11y();
  expect(await balance(page)).toBe(before - 1);
  // The stored result, rendered: the engine's own numbers, formatted by the SPA.
  await expect(page.getByRole("heading", { level: 2, name: "Podsumowanie" })).toBeVisible();
  await expect(page.getByRole("term").filter({ hasText: /^Kapitał na start$/ })).toBeVisible();
  await expect(page.getByRole("region", { name: "Co sprawdzić przed ofertą" })).toBeVisible();
  // The same analysis is in the collection, found by the id of the listing (server-side filter).
  await page.goto(`/app/analyses?q=${item.ref}`);
  const row = page.getByRole("list", { name: "Analizy" }).getByRole("listitem");
  await expect(row).toHaveCount(1);
  await expect(row.first()).toContainText(`Ogłoszenie ${item.ref}`);
});

test("a rental listing is rejected and the report is given back", async ({ page, baseURL, shot }) => {
  test.setTimeout(180_000);
  await signIn(page, baseURL);
  const before = await balance(page);
  const item = plant("rent");
  await submit(page, item.ref);
  const result = page.getByRole("region", { name: "Wynik analizy" });
  await expect(result).toContainText("To ogłoszenie wynajmu", { timeout: 150_000 });
  await expect(result).toContainText("Raport nie został pobrany z konta.");
  await shot("rejected-rent");
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

test("saved listings: save a finished report, keep a note, find it under Zapisane, remove it (real API)", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(180_000);
  await signIn(page, baseURL);
  const item = plant("sale");
  await submit(page, item.ref);
  await expect(page.getByRole("heading", { level: 1, name: `Ogłoszenie ${item.ref}` })).toBeVisible({
    timeout: 150_000,
  });

  const toggle = page.getByRole("button", { name: "Zapisz to ogłoszenie" });
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  const note = page.getByRole("textbox", { name: "Twoja notatka" });
  await note.fill("Zapytać o czynsz i okna.");
  await page.getByRole("button", { name: "Zapisz notatkę" }).click();
  await expect(page.getByText("Notatka zapisana.")).toBeVisible();

  // What the server holds survives a reload.
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Twoja notatka" })).toHaveValue("Zapytać o czynsz i okna.");
  expect((await (await page.request.get("/api/saved")).json()) as unknown[]).toHaveLength(1);

  // The saved scope of the collection lists it, with the note, linking back to the report.
  await page.goto("/app/analyses?saved=1");
  const entry = page.getByRole("list", { name: "Zapisane ogłoszenia" }).getByRole("listitem");
  await expect(entry).toHaveCount(1);
  await expect(entry.first()).toContainText(`Ogłoszenie ${item.ref}`);
  await expect(entry.first()).toContainText("Zapytać o czynsz i okna.");
  await entry.first().getByRole("link").click();
  await expect(page).toHaveURL(/\/app\/analyses\/[0-9a-f-]{36}$/);

  // Removing a listing that has a note asks first; then it is gone on the server.
  await page.getByRole("button", { name: "Zapisz to ogłoszenie" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Usuń z zapisanych" }).click();
  await expect(page.getByRole("button", { name: "Zapisz to ogłoszenie" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  expect((await (await page.request.get("/api/saved")).json()) as unknown[]).toHaveLength(0);
});
