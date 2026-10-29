/**
 * The settings page against the real stack (RM-278): a person signs up, sees their one browser, downloads their
 * data, changes the password (which signs every browser out), signs in with the new one, and deletes the account.
 * Synthetic account only (`e2e-<random>@example.test`); the mailed link is read the way auth.spec.ts does it.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";

import { type Page } from "@playwright/test";

import { expect, test } from "./fixtures";

const COMPOSE = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");
const FIRST = "correct-horse-battery-staple-91";
const SECOND = "correct-horse-battery-staple-92";
const email = `e2e-${randomBytes(5).toString("hex")}@example.test`;

function seed(...args: string[]): Record<string, unknown> {
  const [command = "docker", ...rest] = COMPOSE;
  const output = execFileSync(
    command,
    [...rest, "exec", "-T", "api", "python", "scripts/e2e_session.py", ...args],
    { encoding: "utf8" },
  );
  return JSON.parse(output.trim().split("\n").at(-1) ?? "{}") as Record<string, unknown>;
}

test.afterAll(() => {
  seed("delete-email", email);
});

async function signUp(page: Page): Promise<void> {
  await page.goto("/signup");
  await page.getByRole("textbox", { name: "Adres e-mail" }).fill(email);
  await page.getByRole("textbox", { name: "Hasło" }).fill(FIRST);
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sprawdź skrzynkę" })).toBeVisible();
  const { token } = seed("register-token", "--email", email, "--password", FIRST) as { token: string };
  await page.goto(`/signup/verify#t=${token}`);
  await expect(page).toHaveURL(/\/app$/);
}

async function signIn(page: Page, password: string): Promise<void> {
  await page.getByRole("textbox", { name: "Adres e-mail", exact: true }).fill(email);
  await page.getByRole("textbox", { name: "Hasło" }).fill(password);
  await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
}

test("sessions, export, password change and deletion through the real API", async ({ page }) => {
  await signUp(page);
  await page.goto("/app/settings");
  await expect(page.getByRole("heading", { level: 1, name: "Ustawienia" })).toBeVisible();
  await expect(page.getByLabel("Dane konta").getByText(email, { exact: true })).toBeVisible();

  // The real list has this browser, marked.
  const sessions = page.getByRole("list", { name: "Aktywne sesje" }).getByRole("listitem");
  await expect(sessions).toHaveCount(1);
  await expect(sessions.first()).toContainText("Ta przeglądarka");

  // The export is the real document for this account.
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Pobierz moje dane" }).click();
  const file = await download;
  const path = await file.path();
  const exported = JSON.parse(readFileSync(path, "utf8")) as { profile: { email: string } };
  expect(exported.profile.email).toBe(email);

  // A wrong current password is refused and the session stays.
  const form = page.getByRole("form", { name: "Zmiana hasła" });
  await form.getByLabel("Obecne hasło").fill("not-my-password-at-all");
  await form.getByLabel(/Nowe hasło/).fill(SECOND);
  await form.getByRole("button", { name: "Zmień hasło" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "To nie jest Twoje obecne hasło." })).toBeVisible();
  expect((await page.request.get("/api/me")).status()).toBe(200);

  // The right one changes it, signs every browser out, and the new password works.
  await form.getByLabel("Obecne hasło").fill(FIRST);
  await form.getByRole("button", { name: "Zmień hasło" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/api/me")).status()).toBe(401);
  await signIn(page, FIRST);
  await expect(page.getByRole("alert").first()).toBeVisible(); // the old password no longer works
  await page.getByRole("textbox", { name: "Hasło" }).fill(SECOND);
  await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);

  // Sign out everywhere ends this browser too.
  await page.goto("/app/settings");
  await page.getByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Wyloguj wszędzie" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/api/me")).status()).toBe(401);

  // Deleting the account: the wrong address is refused by the server's rule, the right one erases it.
  await signIn(page, SECOND);
  await expect(page).toHaveURL(/\/app$/);
  await page.goto("/app/settings");
  await page.getByRole("button", { name: "Usuń konto", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Usunąć konto na stałe?" });
  await dialog.getByRole("textbox", { name: "Adres e-mail konta" }).fill(email);
  await dialog.getByRole("button", { name: "Usuń konto na stałe" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/api/me")).status()).toBe(401);
  await signIn(page, SECOND);
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});
