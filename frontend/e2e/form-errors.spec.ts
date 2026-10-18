import type { Locator, Page } from "@playwright/test";

import { fx } from "../test/fixtures";
import {
  createAuthFlow,
  createRun,
  createSettings,
  SETTINGS_EMAIL,
  type Reply,
  type Scenario,
} from "../test/scenarios";
import { expect, test } from "./fixtures";

/**
 * Audit F12 (frontend/docs/AUDIT-2026-10-15.md): one error contract on every form. The summary takes focus when a
 * submit RESULT is invalid (at once for a client check, when the answer arrives for a server one), it lists the
 * server's field errors too, a repeated failure is announced again, and typing never steals focus.
 */

const EMAIL = "anna@example.test";
const PHRASE = "correct-horse-battery-staple-91";
const TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz012345";
const LISTING = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd";

/** A fixture's answer, held back so a summary that focuses when the request STARTS would be caught. */
function slow(operation: string, name: string, delayMs = 400): Reply {
  const fixture = fx(operation, name);
  return {
    status: fixture.status,
    body: fixture.body,
    contentType: fixture.content_type,
    headers: fixture.headers,
    delayMs,
  };
}

interface FormCase {
  readonly name: string;
  readonly path: string;
  readonly scenario: (failure: Reply) => Scenario;
  /** The server's field failure for this form, and the field that should then be invalid. */
  readonly fieldFailure: Reply;
  readonly field: (page: Page) => Locator;
  /** Fill what the client accepts, so the server is asked. */
  readonly fill: (page: Page) => Promise<void>;
  readonly submit: (page: Page) => Locator;
  /** The summary or notice of THIS form (a page can hold two forms). */
  readonly scope: (page: Page) => Locator;
  /** Get to the form when it is not on the page at once (a dialog the person opens). */
  readonly open?: (page: Page) => Promise<void>;
}

const textbox = (page: Page, name: string) => page.getByRole("textbox", { name, exact: true });
const signedOut = (overrides: Record<string, Reply>) => createAuthFlow(overrides);

const FORMS: readonly FormCase[] = [
  {
    name: "sign in with a password",
    path: "/login",
    scenario: (failure) => signedOut({ "POST /api/auth/login": failure }),
    fieldFailure: slow("POST /api/auth/login", "validation_error"),
    field: (page) => textbox(page, "Adres e-mail"),
    fill: async (page) => {
      await textbox(page, "Adres e-mail").fill(EMAIL);
      await page.getByLabel("Hasło", { exact: true }).fill(PHRASE);
    },
    submit: (page) => page.getByRole("button", { name: "Zaloguj się", exact: true }),
    scope: (page) => page.getByRole("form", { name: "Logowanie hasłem" }),
  },
  {
    name: "sign in with a mailed link",
    path: "/login",
    scenario: (failure) => signedOut({ "POST /api/auth/email/start": failure }),
    fieldFailure: slow("POST /api/auth/email/start", "validation_error"),
    field: (page) => textbox(page, "Adres e-mail do linku"),
    fill: async (page) => textbox(page, "Adres e-mail do linku").fill(EMAIL),
    submit: (page) => page.getByRole("button", { name: "Wyślij link do logowania" }),
    scope: (page) => page.getByRole("form", { name: "Logowanie linkiem" }),
  },
  {
    name: "sign up",
    path: "/signup",
    scenario: (failure) => signedOut({ "POST /api/auth/register": failure }),
    fieldFailure: slow("POST /api/auth/register", "weak_password"),
    field: (page) => page.getByLabel("Hasło", { exact: true }),
    fill: async (page) => {
      await textbox(page, "Adres e-mail").fill(EMAIL);
      await page.getByLabel("Hasło", { exact: true }).fill(PHRASE);
    },
    submit: (page) => page.getByRole("button", { name: "Załóż konto" }),
    scope: (page) => page.getByRole("form", { name: "Rejestracja" }),
  },
  {
    name: "forgotten password",
    path: "/password/forgot",
    scenario: (failure) => signedOut({ "POST /api/auth/password/forgot": failure }),
    fieldFailure: slow("POST /api/auth/password/forgot", "validation_error"),
    field: (page) => textbox(page, "Adres e-mail"),
    fill: async (page) => textbox(page, "Adres e-mail").fill(EMAIL),
    submit: (page) => page.getByRole("button", { name: "Wyślij link" }),
    scope: (page) => page.getByRole("form", { name: "Reset hasła" }),
  },
  {
    name: "new password from a mailed link",
    path: `/password/reset#t=${TOKEN}`,
    scenario: (failure) => signedOut({ "POST /api/auth/password/reset": failure }),
    fieldFailure: slow("POST /api/auth/password/reset", "weak_password"),
    field: (page) => page.locator("#reset-password"),
    fill: async (page) => page.locator("#reset-password").fill(PHRASE),
    submit: (page) => page.getByRole("button", { name: "Zapisz hasło" }),
    scope: (page) => page.getByRole("form", { name: "Nowe hasło" }),
  },
  {
    name: "new analysis",
    path: "/app/analyses/new",
    scenario: (failure) => createRun({ post: failure }),
    fieldFailure: slow("POST /api/audits", "invalid_listing_ref"),
    field: (page) => textbox(page, "Adres ogłoszenia lub numer"),
    fill: async (page) => textbox(page, "Adres ogłoszenia lub numer").fill(LISTING),
    submit: (page) => page.getByRole("button", { name: "Rozpocznij analizę" }),
    scope: (page) => page.locator("form"),
  },
  {
    name: "change password in settings",
    path: "/app/settings",
    scenario: (failure) => createSettings([{ operation: "POST /api/auth/password/change", reply: failure }]),
    fieldFailure: slow("POST /api/auth/password/change", "weak_new_password"),
    field: (page) => page.getByRole("form", { name: "Zmiana hasła" }).getByLabel(/Nowe hasło/),
    fill: async (page) => {
      const form = page.getByRole("form", { name: "Zmiana hasła" });
      await form.getByLabel("Obecne hasło").fill("my-current-password");
      await form.getByLabel(/Nowe hasło/).fill(PHRASE);
    },
    submit: (page) => page.getByRole("button", { name: "Zmień hasło" }),
    scope: (page) => page.getByRole("form", { name: "Zmiana hasła" }),
  },
  {
    name: "delete the account in settings",
    path: "/app/settings",
    scenario: (failure) => createSettings([{ operation: "DELETE /api/me", reply: failure }]),
    fieldFailure: slow("DELETE /api/me", "confirmation_mismatch"),
    field: (page) => page.getByRole("dialog").getByRole("textbox", { name: "Adres e-mail konta" }),
    fill: async (page) =>
      page.getByRole("dialog").getByRole("textbox", { name: "Adres e-mail konta" }).fill(SETTINGS_EMAIL),
    submit: (page) => page.getByRole("dialog").getByRole("button", { name: "Usuń konto na stałe" }),
    scope: (page) => page.getByRole("dialog"),
    open: async (page) => page.getByRole("button", { name: "Usuń konto", exact: true }).click(),
  },
];

const summaryOf = (form: FormCase, page: Page) =>
  form
    .scope(page)
    .getByRole("alert")
    .filter({ has: page.getByRole("heading", { name: /^Popraw/ }) });

for (const form of FORMS) {
  test.describe(form.name, () => {
    test.skip(({ isMobile }) => isMobile, "focus and announcement are layout-independent");

    test("blank: the summary takes focus at once, links to the field, and typing keeps focus there", async ({
      page,
      serve,
    }) => {
      await serve(form.scenario(form.fieldFailure));
      await page.goto(form.path);
      await form.open?.(page);
      await form.submit(page).click();
      const summary = summaryOf(form, page);
      await expect(summary).toBeFocused();
      await form.field(page).click();
      await page.keyboard.type("x");
      await expect(form.field(page)).toBeFocused();
    });

    test("a server field error is in the summary, which takes focus when the answer arrives", async ({
      page,
      serve,
    }) => {
      await serve(form.scenario(form.fieldFailure));
      await page.goto(form.path);
      await form.open?.(page);
      await form.fill(page);
      await form.submit(page).click();
      const summary = summaryOf(form, page);
      await expect(summary).toBeFocused();
      await expect(form.field(page)).toHaveAttribute("aria-invalid", "true");

      // The same failure again, submitted with Enter from the field: announced and focused again.
      await form.field(page).focus();
      await expect(form.field(page)).toBeFocused();
      await form.field(page).press("Enter");
      await expect(summary).toBeFocused();
    });

    test("a repeated general failure is announced again (a new alert, not the old one)", async ({
      page,
      serve,
    }) => {
      const limited = slow("POST /api/auth/login", "rate_limited", 100);
      await serve(form.scenario(limited));
      await page.goto(form.path);
      await form.open?.(page);
      await form.fill(page);
      await form.submit(page).click();
      const notice = form
        .scope(page)
        .getByRole("alert")
        .filter({ hasText: /Spróbuj ponownie/ });
      await expect(notice).toBeVisible();
      const first = await notice.elementHandle();
      await form.submit(page).click();
      await expect.poll(async () => first?.evaluate((node) => node.isConnected)).toBe(false);
      await expect(notice).toBeVisible();
    });
  });
}
