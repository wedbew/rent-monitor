/**
 * Sign-in, sign-up, the pages the API's e-mails link to, password recovery, the session boundary and sign-out.
 * The API is the scenario registry's stateful `authFlow`: GET /api/me answers 401 until a sign-in succeeds.
 * Google is e2e/gis.ts's stand-in for Google's script.
 */
import type { Page } from "@playwright/test";

import { createAuthFlow, replyFrom, type AuthFlow } from "../test/scenarios";
import { fx } from "../test/fixtures";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";
import { nextGoogleCredential } from "./gis";
import { mockApi, type MockApi } from "./mock";

const EMAIL = "anna@example.test";
const SAMPLE_PHRASE = "correct-horse-battery-staple-91";
const TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz012345";

async function start(
  serve: (flow: AuthFlow) => Promise<MockApi>,
  overrides: Record<string, ReturnType<typeof replyFrom>> = {},
) {
  const flow = createAuthFlow(overrides);
  const api = await serve(flow);
  return { flow, api };
}

const heading = (page: Page, name: string | RegExp) => page.getByRole("heading", { level: 1, name });
const field = (page: Page, name: string, exact = true) => page.getByRole("textbox", { name, exact });

async function fillLogin(page: Page, email = EMAIL, password = SAMPLE_PHRASE) {
  await field(page, "Adres e-mail").fill(email);
  await field(page, "Hasło").fill(password);
}

// ------------------------------------------------------------------------------------------ the frame
test.describe("the signed-out frame", () => {
  test("the skip link is the first stop", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login");
    await expect(heading(page, "Zaloguj się")).toBeVisible();
    const skip = page.getByRole("link", { name: "Przejdź do treści" });
    await exercise("public.skip", async () => {
      await page.keyboard.press("Tab");
      return [await outcome.focus(skip)];
    });
    await page.keyboard.press("Enter");
    await expect(page.locator("main")).toBeFocused();
  });

  test("the brand link tries the dashboard, which asks a signed-out person to sign in", async ({
    page,
    serve,
  }) => {
    await start(serve);
    await page.goto("/signup");
    await exercise("public.brand", async () => {
      await page.getByRole("link", { name: "renti.tech, przejdź do pulpitu" }).click();
      return [await outcome.url(page, /\/login\?next=%2Fapp$/)];
    });
  });

  test("the theme control works without a session", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login");
    await exercise("public.theme", async () => {
      await page.getByRole("button", { name: "Tryb ciemny" }).click();
      return [await outcome.state(page.locator("html"), "data-theme", "dark")];
    });
  });

  for (const [id, name, path] of [
    ["public.terms", "Regulamin", /\/terms$/],
    ["public.privacy", "Polityka prywatności", /\/privacy$/],
  ] as const) {
    test(`the footer link "${name}" opens the document`, async ({ page, serve }) => {
      await start(serve);
      await page.goto("/login");
      await exercise(id, async () => {
        await page.getByRole("contentinfo").getByRole("link", { name }).click();
        return [await outcome.url(page, path)];
      });
      await expect(heading(page, name)).toBeVisible();
    });
  }
});

// ------------------------------------------------------------------------------------------------ login
test.describe("login", () => {
  test("Google sign-in sends the credential to the API and opens the app", async ({ page, serve }) => {
    const { api } = await start(serve);
    await page.goto("/login");
    await expect(heading(page, "Zaloguj się")).toBeVisible();
    await exercise("login.google", async () => {
      await page.getByRole("button", { name: "Zaloguj się przez Google" }).click();
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/auth/google",
          body: { credential: "fake-google-credential-0123456789" },
        }),
      ];
    });
    await expect(page).toHaveURL(/\/app$/);
    await expect(heading(page, "Pulpit")).toBeVisible();
  });

  test("the fields hold what is typed", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login");
    await exercise("login.email", async () => {
      await field(page, "Adres e-mail").fill(EMAIL);
      return [await outcome.value(field(page, "Adres e-mail"), EMAIL)];
    });
    await exercise("login.password", async () => {
      await field(page, "Hasło").fill(SAMPLE_PHRASE);
      return [await outcome.value(field(page, "Hasło"), SAMPLE_PHRASE)];
    });
    await exercise("login.link-email", async () => {
      await field(page, "Adres e-mail do linku").fill(EMAIL);
      return [await outcome.value(field(page, "Adres e-mail do linku"), EMAIL)];
    });
  });

  test("e-mail and password sign in, show who is signed in, and land on the dashboard", async ({
    page,
    serve,
  }) => {
    const { api, flow } = await start(serve);
    await page.goto("/login");
    await fillLogin(page);
    await exercise("login.submit", async () => {
      await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/auth/login",
          body: { email: EMAIL, password: SAMPLE_PHRASE },
        }),
      ];
    });
    await expect(page).toHaveURL(/\/app$/);
    await expect(heading(page, "Pulpit")).toBeVisible();
    expect(flow.state.signedIn).toBe(true);
  });

  test("a deep link signed out returns there after sign-in", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/app/market");
    await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fmarket$/);
    await fillLogin(page);
    await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
    await expect(page).toHaveURL(/\/app\/market$/);
    await expect(heading(page, "Rynek")).toBeVisible();
  });

  for (const next of ["//evil.test/app", "https://evil.test/app", "/elsewhere", "/app\\evil"]) {
    test(`a next target of "${next}" is not followed`, async ({ page, serve }) => {
      await start(serve);
      await page.goto(`/login?next=${encodeURIComponent(next)}`);
      await fillLogin(page);
      await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
      await expect(page).toHaveURL(/\/app$/);
    });
  }

  test("a wrong password says so, keeps what was typed and spends nothing", async ({ page, serve }) => {
    const { flow } = await start(serve);
    await page.goto("/login");
    await fillLogin(page, EMAIL, "wrong-password-1");
    await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Nieprawidłowy e-mail lub hasło" })).toBeVisible();
    await expect(field(page, "Adres e-mail")).toHaveValue(EMAIL);
    await expect(field(page, "Hasło")).toHaveValue("wrong-password-1");
    expect(flow.state.signedIn).toBe(false);
  });

  test("a throttled sign-in shows when to try again", async ({ page, serve }) => {
    const limited = replyFrom(fx("POST /api/auth/login", "rate_limited"));
    await start(serve, {
      "POST /api/auth/login": { ...limited, headers: { ...limited.headers, "retry-after": "42" } },
    });
    await page.goto("/login");
    await fillLogin(page);
    await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Zbyt wiele prób" })).toContainText(
      "za 42 sekundy",
    );
  });

  test("an empty submit sends nothing, moves focus to the summary and links to each problem", async ({
    page,
    serve,
  }) => {
    const { api } = await start(serve);
    await page.goto("/login");
    await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
    const summary = page.getByRole("alert").filter({ hasText: "Popraw pola: 2" });
    await expect(summary).toBeFocused();
    expect(api.requests.filter((r) => r.method === "POST")).toEqual([]);
    await exercise("login.error.email", async () => {
      await summary.getByRole("link", { name: "Wpisz adres e-mail." }).click();
      return [await outcome.focus(field(page, "Adres e-mail"))];
    });
    await exercise("login.error.password", async () => {
      await summary.getByRole("link", { name: "Wpisz hasło." }).click();
      return [await outcome.focus(field(page, "Hasło"))];
    });
    await expect(field(page, "Adres e-mail")).toHaveAttribute("aria-invalid", "true");
  });

  test("a Google account the API cannot vouch for leads to the e-mail link", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login");
    await expect(heading(page, "Zaloguj się")).toBeVisible();
    await nextGoogleCredential(page, "fake-confirm-credential-0123456789");
    await page.getByRole("button", { name: "Zaloguj się przez Google" }).click();
    await exercise("login.use-link", async () => {
      await page.getByRole("button", { name: "Użyj linku e-mail" }).click();
      return [await outcome.focus(field(page, "Adres e-mail do linku"))];
    });
  });

  test("the e-mail link is requested without saying whether the address has an account", async ({
    page,
    serve,
  }) => {
    const { api } = await start(serve);
    await page.goto("/login");
    await field(page, "Adres e-mail do linku").fill(EMAIL);
    await exercise("login.link-submit", async () => {
      await page.getByRole("button", { name: "Wyślij link do logowania" }).click();
      return [
        await outcome.request(api, { method: "POST", path: "/api/auth/email/start", body: { email: EMAIL } }),
      ];
    });
    await expect(page.getByText("Jeśli ten adres ma konto albo może je założyć")).toBeVisible();
  });

  test("the forgot-password and sign-up links go there", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login");
    await exercise("login.forgot", async () => {
      await page.getByRole("link", { name: "Nie pamiętam hasła" }).click();
      return [await outcome.url(page, /\/password\/forgot$/)];
    });
    await page.goto("/login");
    await exercise("login.signup", async () => {
      await page.getByRole("link", { name: "Zarejestruj się", exact: true }).click();
      return [await outcome.url(page, /\/signup$/)];
    });
  });

  test("someone already signed in is sent to the app", async ({ page, serve }) => {
    const { flow } = await start(serve);
    flow.state.signedIn = true;
    await page.goto("/login");
    await expect(page).toHaveURL(/\/app$/);
  });
});

// ----------------------------------------------------------------------------------------------- signup
test.describe("signup", () => {
  test("Google sign-up sends the credential", async ({ page, serve }) => {
    const { api } = await start(serve);
    await page.goto("/signup");
    await expect(heading(page, "Załóż konto")).toBeVisible();
    await exercise("signup.google", async () => {
      await page.getByRole("button", { name: "Zarejestruj się przez Google" }).click();
      return [await outcome.request(api, { method: "POST", path: "/api/auth/google" })];
    });
    await expect(page).toHaveURL(/\/app$/);
  });

  test("the fields hold what is typed; the password is hidden and a hint says what is needed", async ({
    page,
    serve,
  }) => {
    await start(serve);
    await page.goto("/signup");
    await exercise("signup.email", async () => {
      await field(page, "Adres e-mail").fill(EMAIL);
      return [await outcome.value(field(page, "Adres e-mail"), EMAIL)];
    });
    await exercise("signup.password", async () => {
      await field(page, "Hasło").fill(SAMPLE_PHRASE);
      return [await outcome.value(field(page, "Hasło"), SAMPLE_PHRASE)];
    });
    await expect(field(page, "Hasło")).toHaveAttribute("type", "password");
    await expect(field(page, "Hasło")).toHaveAccessibleDescription(/co najmniej 10 znaków/i);
  });

  test("a valid registration asks the API once and says to check the mailbox, never whether the address exists", async ({
    page,
    serve,
  }) => {
    const { api } = await start(serve);
    await page.goto("/signup");
    await field(page, "Adres e-mail").fill(EMAIL);
    await field(page, "Hasło").fill(SAMPLE_PHRASE);
    await exercise("signup.submit", async () => {
      await page.getByRole("button", { name: "Załóż konto" }).click();
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/auth/register",
          body: { email: EMAIL, password: SAMPLE_PHRASE },
        }),
      ];
    });
    await expect(heading(page, "Sprawdź skrzynkę")).toBeVisible();
    expect(api.requests.filter((r) => r.path === "/api/auth/register")).toHaveLength(1);
  });

  test("a new link can be requested, and the address can be changed", async ({ page, serve }) => {
    const { api } = await start(serve);
    await page.goto("/signup");
    await field(page, "Adres e-mail").fill(EMAIL);
    await field(page, "Hasło").fill(SAMPLE_PHRASE);
    await page.getByRole("button", { name: "Załóż konto" }).click();
    await expect(heading(page, "Sprawdź skrzynkę")).toBeVisible();
    await exercise("signup.resend", async () => {
      await page.getByRole("button", { name: "Wyślij link ponownie" }).click();
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/auth/register/resend",
          body: { email: EMAIL },
        }),
      ];
    });
    await exercise("signup.change-address", async () => {
      await page.getByRole("button", { name: "Zmień adres" }).click();
      return [await outcome.text(heading(page, "Załóż konto"), "Załóż konto")];
    });
    await expect(field(page, "Adres e-mail")).toHaveValue(EMAIL);
  });

  test("an empty submit shows a summary with a link to each problem", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/signup");
    await page.getByRole("button", { name: "Załóż konto" }).click();
    const summary = page.getByRole("alert").filter({ hasText: "Popraw pola: 2" });
    await expect(summary).toBeFocused();
    await exercise("signup.error.email", async () => {
      await summary.getByRole("link", { name: "Wpisz adres e-mail." }).click();
      return [await outcome.focus(field(page, "Adres e-mail"))];
    });
    await exercise("signup.error.password", async () => {
      await summary.getByRole("link", { name: "Wpisz hasło." }).click();
      return [await outcome.focus(field(page, "Hasło"))];
    });
  });

  test("a too-short password is caught before the request, with the rule in words", async ({
    page,
    serve,
  }) => {
    const { api } = await start(serve);
    await page.goto("/signup");
    await field(page, "Adres e-mail").fill(EMAIL);
    await field(page, "Hasło").fill("short");
    await page.getByRole("button", { name: "Załóż konto" }).click();
    await expect(
      page.getByRole("alert").getByRole("link", { name: "Hasło musi mieć co najmniej 10 znaków." }),
    ).toBeVisible();
    expect(api.requests.filter((r) => r.method === "POST")).toEqual([]);
  });

  test("the server's weak-password answer becomes the password field's message and keeps the form", async ({
    page,
    serve,
  }) => {
    await start(serve);
    await page.goto("/signup");
    await field(page, "Adres e-mail").fill(EMAIL);
    await field(page, "Hasło").fill("password1234");
    await page.getByRole("button", { name: "Załóż konto" }).click();
    const summary = page.getByRole("alert").filter({ hasText: "Popraw 1 pole" });
    await expect(summary).toBeFocused();
    await exercise("signup.error.weak", async () => {
      await summary.getByRole("link", { name: /popularne/ }).click();
      return [await outcome.focus(field(page, "Hasło"))];
    });
    await expect(field(page, "Adres e-mail")).toHaveValue(EMAIL);
    await expect(field(page, "Hasło")).toHaveAccessibleDescription(/popularne/);
  });

  test("the documents and the sign-in link are reachable", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/signup");
    await exercise("signup.terms", async () => {
      await page.getByRole("main").getByRole("link", { name: "Regulamin" }).click();
      return [await outcome.url(page, /\/terms$/)];
    });
    await page.goto("/signup");
    await exercise("signup.privacy", async () => {
      await page
        .getByRole("main")
        .getByRole("link", { name: /^Polityk[aą] prywatności$/ })
        .click();
      return [await outcome.url(page, /\/privacy$/)];
    });
    await page.goto("/signup");
    await exercise("signup.login", async () => {
      await page.getByRole("link", { name: "Zaloguj się" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });
});

// ------------------------------------------------------------------------------------ password recovery
test.describe("password recovery", () => {
  test("asking for a link answers the same for every address", async ({ page, serve }) => {
    const { api } = await start(serve);
    await page.goto("/password/forgot");
    await exercise("forgot.email", async () => {
      await field(page, "Adres e-mail").fill(EMAIL);
      return [await outcome.value(field(page, "Adres e-mail"), EMAIL)];
    });
    await exercise("forgot.submit", async () => {
      await page.getByRole("button", { name: "Wyślij link" }).click();
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/auth/password/forgot",
          body: { email: EMAIL },
        }),
      ];
    });
    await expect(page.getByText("Jeśli to konto istnieje")).toBeVisible();
  });

  test("the back link returns to sign-in", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/password/forgot");
    await exercise("forgot.back", async () => {
      await page.getByRole("link", { name: "Wróć do logowania" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });

  test("a mailed reset link opens the form, removes the token from the address bar and sets the password once", async ({
    page,
    serve,
  }) => {
    const { api, flow } = await start(serve);
    await page.goto(`/password/reset#t=${TOKEN}`);
    await expect(heading(page, "Ustaw nowe hasło")).toBeVisible();
    await expect(page).toHaveURL(/\/password\/reset$/);
    expect(await page.evaluate(() => window.location.hash)).toBe("");
    await exercise("reset.password", async () => {
      await field(page, "Nowe hasło").fill("a-brand-new-passphrase-77");
      return [await outcome.value(field(page, "Nowe hasło"), "a-brand-new-passphrase-77")];
    });
    await exercise("reset.submit", async () => {
      await page.getByRole("button", { name: "Zapisz hasło" }).click();
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/auth/password/reset",
          body: { token: TOKEN, password: "a-brand-new-passphrase-77" },
        }),
      ];
    });
    await expect(heading(page, "Hasło zostało zmienione")).toBeVisible();
    expect(flow.calls.filter((c) => c.startsWith("reset:"))).toEqual([`reset:${TOKEN}`]);
    await exercise("reset.done.login", async () => {
      await page.getByRole("link", { name: "Zaloguj się" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });

  test("a weak new password does not spend the link", async ({ page, serve }) => {
    await start(serve);
    await page.goto(`/password/reset#t=${TOKEN}`);
    await field(page, "Nowe hasło").fill("password1234");
    await page.getByRole("button", { name: "Zapisz hasło" }).click();
    const summary = page.getByRole("alert").filter({ hasText: "Popraw 1 pole" });
    await exercise("reset.error.weak", async () => {
      await summary.getByRole("link", { name: /popularne/ }).click();
      return [await outcome.focus(field(page, "Nowe hasło"))];
    });
    await expect(page.getByRole("button", { name: "Zapisz hasło" })).toBeVisible();
  });

  test("the back link of the form returns to sign-in", async ({ page, serve }) => {
    await start(serve);
    await page.goto(`/password/reset#t=${TOKEN}`);
    await exercise("reset.back", async () => {
      await page.getByRole("link", { name: "Wróć do logowania" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });

  test("a reset link that is invalid or expired offers a new one", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/password/reset#t=invalid12345678901234567890");
    await field(page, "Nowe hasło").fill("a-brand-new-passphrase-77");
    await page.getByRole("button", { name: "Zapisz hasło" }).click();
    await expect(page.getByText("Link jest nieprawidłowy lub wygasł").first()).toBeVisible();
    await page.goto("/password/reset");
    await exercise("reset-invalid.new-link", async () => {
      await page.getByRole("link", { name: "Poproś o nowy link" }).click();
      return [await outcome.url(page, /\/password\/forgot$/)];
    });
    await page.goto("/password/reset");
    await exercise("reset-invalid.back", async () => {
      await page.getByRole("link", { name: "Wróć do logowania" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });
});

// ------------------------------------------------------------------------------- the links the API mails
test.describe("mailed sign-in and sign-up links", () => {
  test("a sign-in link signs in once, removes the token from the address bar and keeps it out of storage", async ({
    page,
    serve,
  }) => {
    const { api, flow } = await start(serve);
    await page.goto(`/login/email#t=${TOKEN}`);
    await expect(heading(page, "Pulpit")).toBeVisible();
    await expect(page).toHaveURL(/\/app$/);
    expect(flow.calls.filter((c) => c.startsWith("email-verify:"))).toEqual([`email-verify:${TOKEN}`]);
    // The token only ever travels in the body of the one verify call: never in a URL, a query string or a referrer.
    expect(api.requests.filter((r) => r.path.includes(TOKEN) || r.query.includes(TOKEN))).toEqual([]);
    expect(await page.evaluate(() => document.referrer)).not.toContain(TOKEN);
    expect(api.requests.filter((r) => r.path === "/api/auth/email/verify")).toHaveLength(1);
    expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(
      TOKEN,
    );
  });

  test("a sign-in link that is invalid says so and offers a new one", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login/email#t=invalid12345678901234567890");
    await expect(
      page.getByRole("alert").filter({ hasText: "Link jest nieprawidłowy lub wygasł" }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Poproś o nowy link" })).toBeVisible();
  });

  test("a sign-in link opened without its token explains and offers a new link", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login/email");
    await expect(page.getByText("Ten link jest niepełny")).toBeVisible();
    await exercise("login-email.new-link", async () => {
      await page.getByRole("link", { name: "Poproś o nowy link" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
    await page.goto("/login/email");
    await exercise("login-email.back", async () => {
      await page.getByRole("link", { name: "Wróć do logowania" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });

  test("a sign-up link creates the session and opens the app", async ({ page, serve }) => {
    const { flow } = await start(serve);
    await page.goto(`/signup/verify#t=${TOKEN}`);
    await expect(heading(page, "Pulpit")).toBeVisible();
    expect(flow.calls.filter((c) => c.startsWith("register-verify:"))).toEqual([`register-verify:${TOKEN}`]);
  });

  test("a sign-up link for an address that already has an account leads to sign-in", async ({
    page,
    serve,
  }) => {
    await start(serve);
    await page.goto("/signup/verify#t=exists12345678901234567890");
    await expect(page.getByText("Masz już konto z tym adresem")).toBeVisible();
    await exercise("signup-verify.exists.login", async () => {
      await page.getByRole("link", { name: "Zaloguj się" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });

  test("a sign-up link without a token offers to register again", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/signup/verify");
    await exercise("signup-verify.again", async () => {
      await page.getByRole("link", { name: "Zarejestruj się ponownie" }).click();
      return [await outcome.url(page, /\/signup$/)];
    });
    await page.goto("/signup/verify");
    await exercise("signup-verify.back", async () => {
      await page.getByRole("link", { name: "Wróć do logowania" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
  });
});

// --------------------------------------------------------------------------------- the session boundary
test.describe("the session boundary", () => {
  test("signing out asks the API, empties the session and leaves for sign-in (desktop)", async ({
    page,
    serve,
    isMobile,
  }) => {
    test.skip(isMobile, "the rail is desktop");
    const { api, flow } = await start(serve);
    flow.state.signedIn = true;
    await page.goto("/app");
    await expect(heading(page, "Pulpit")).toBeVisible();
    await expect(page.getByText("7 raportów na koncie")).toBeVisible();
    await exercise("shell.signout", async () => {
      await page.getByRole("button", { name: "Wyloguj się" }).click();
      return [await outcome.url(page, /\/login$/)];
    });
    expect(api.requests.some((r) => r.method === "POST" && r.path === "/api/auth/signout")).toBe(true);
    await page.goto("/app");
    await expect(page).toHaveURL(/\/login\?next=%2Fapp$/);
  });

  test("signing out from the mobile menu does the same", async ({ page, serve, isMobile }) => {
    test.skip(!isMobile, "the sheet is mobile");
    const { flow } = await start(serve);
    flow.state.signedIn = true;
    await page.goto("/app");
    await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
    await exercise("shell.menu.signout", async () => {
      await page
        .getByRole("dialog", { name: "Nawigacja" })
        .getByRole("button", { name: "Wyloguj się" })
        .click();
      return [await outcome.url(page, /\/login$/)];
    });
  });

  test("an unconfirmed address shows a banner with a resend", async ({ page, serve }) => {
    const api = await serve("unverified");
    await page.goto("/app");
    await expect(page.getByText("Potwierdź adres e-mail")).toBeVisible();
    await exercise("shell.verify.resend", async () => {
      await page.getByRole("button", { name: "Wyślij link ponownie" }).click();
      return [await outcome.request(api, { method: "POST", path: "/api/auth/register/resend" })];
    });
    await expect(page.getByText("Jeśli to możliwe, wysłaliśmy nowy link.")).toBeVisible();
  });

  test("signing out in one tab signs out the others", async ({ page, serve, context, isMobile }) => {
    test.skip(isMobile, "uses the desktop rail");
    const { flow } = await start(serve);
    flow.state.signedIn = true;
    await page.goto("/app");
    await expect(heading(page, "Pulpit")).toBeVisible();
    const other = await context.newPage();
    await mockApi(other, flow); // a second tab of the same browser: same API, same session state
    await other.goto("/app/market");
    await expect(heading(other, "Rynek")).toBeVisible();
    await page.getByRole("button", { name: "Wyloguj się" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(other).toHaveURL(/\/login\?next=%2Fapp%2Fmarket$/);
  });

  test("after a whole journey nothing but the theme is in browser storage", async ({ page, serve }) => {
    await start(serve);
    await page.goto("/login");
    await fillLogin(page);
    await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
    await expect(heading(page, "Pulpit")).toBeVisible();
    const stored = await page.evaluate(() => ({
      local: { ...localStorage },
      session: { ...sessionStorage },
    }));
    expect(
      Object.keys(stored.local).filter((k) => k !== "renti-theme" && k !== "renti-session-signal"),
    ).toEqual([]);
    expect(stored.session).toEqual({});
    expect(JSON.stringify([stored.local, stored.session])).not.toMatch(
      /session|token|cookie|credential|password/i,
    );
    expect(await page.evaluate(() => document.cookie)).toBe("");
  });
});
