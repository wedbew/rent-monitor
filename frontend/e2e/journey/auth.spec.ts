/**
 * The sign-up journey against the real stack: register in the form, open the mailed link, land signed in with the
 * signup credits, sign out, sign in with the password. The mailed link is not read from a mailbox or a log: the
 * api container's `scripts/e2e_session.py register-token` stores the token exactly as registration does and returns
 * the raw value (the mail itself goes nowhere here: no provider is configured on the journey stack).
 */
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";

import { expect, test } from "@playwright/test";

const COMPOSE = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");
const SAMPLE_PHRASE = "correct-horse-battery-staple-91";
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

test("register, confirm by the mailed link, sign out, sign in", async ({ page }) => {
  await page.goto("/signup");
  await page.getByRole("textbox", { name: "Adres e-mail" }).fill(email);
  await page.getByRole("textbox", { name: "Hasło" }).fill(SAMPLE_PHRASE);
  await page.getByRole("button", { name: "Załóż konto" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sprawdź skrzynkę" })).toBeVisible();

  const { token } = seed("register-token", "--email", email, "--password", SAMPLE_PHRASE) as {
    token: string;
  };
  await page.goto(`/signup/verify#t=${token}`);
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
  await expect(page.getByText("3 raporty na koncie")).toBeVisible();

  await page.getByRole("button", { name: "Wyloguj się" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/api/me")).status()).toBe(401);

  await page.getByRole("textbox", { name: "Adres e-mail", exact: true }).fill(email);
  await page.getByRole("textbox", { name: "Hasło" }).fill(SAMPLE_PHRASE);
  await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  expect(await (await page.request.get("/api/me")).json()).toMatchObject({ email, credit_balance: 3 });
});

test("an expired or used link is refused by the real API and says so", async ({ page }) => {
  await page.goto("/login/email#t=AbCdEfGhIjKlMnOpQrStUvWxYz012345");
  await expect(
    page.getByRole("alert").filter({ hasText: "Link jest nieprawidłowy lub wygasł" }),
  ).toBeVisible();
});
