import type { Page } from "@playwright/test";

import { createSettings, SETTINGS_EMAIL } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

const PHRASE = "correct-horse-battery-staple-91";

const sessionList = (page: Page) => page.getByRole("list", { name: "Aktywne sesje" });
const passwordForm = (page: Page) => page.getByRole("form", { name: "Zmiana hasła" });

test.describe("settings", () => {
  test("shows the account and every signed-in browser, the current one marked and first", async ({
    page,
    serve,
  }) => {
    await serve("settings");
    await page.goto("/app/settings");
    await expect(page.getByRole("heading", { level: 1, name: "Ustawienia" })).toBeVisible();
    await expect(page.getByText(SETTINGS_EMAIL)).toBeVisible();
    const items = sessionList(page).getByRole("listitem");
    await expect(items).toHaveCount(3);
    await expect(items.first()).toContainText("Ta przeglądarka");
    await expect(page.getByText("Ta przeglądarka")).toHaveCount(1);
  });

  test("one session is a list of one; an unreadable list says so and asks again", async ({ page, serve }) => {
    await serve("settingsOneSession");
    await page.goto("/app/settings");
    await expect(sessionList(page).getByRole("listitem")).toHaveCount(1);

    await page.unrouteAll();
    const api = await serve("settingsSessionsFailing");
    await page.goto("/app/settings");
    await expect(page.getByText("Nie udało się wczytać sesji")).toBeVisible();
    await exercise("settings.sessions.retry", async () => {
      const before = api.requests.filter((r) => r.path === "/api/auth/sessions").length;
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      await expect
        .poll(() => api.requests.filter((r) => r.path === "/api/auth/sessions").length)
        .toBeGreaterThan(before);
      return [await outcome.request(api, { method: "GET", path: "/api/auth/sessions" })];
    });
  });

  test("sign out everywhere asks first: the close button and Anuluj leave everything as it was", async ({
    page,
    serve,
  }) => {
    const api = await serve("settings");
    await page.goto("/app/settings");
    const dialog = page.getByRole("dialog", { name: "Wylogować ze wszystkich urządzeń?" });
    await exercise("settings.signout-all", async () => {
      await page.getByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }).click();
      return [await outcome.dialog(dialog, "open")];
    });
    await exercise("settings.signout-all.close", async () => {
      await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    await page.getByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }).click();
    await exercise("settings.signout-all.cancel", async () => {
      await dialog.getByRole("button", { name: "Anuluj" }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    expect(api.requests.filter((r) => r.path === "/api/auth/signout-all")).toHaveLength(0);
    await expect(page).toHaveURL(/\/app\/settings$/);
  });

  test("confirming signs out everywhere and lands on sign-in with nothing of the account left", async ({
    page,
    serve,
  }) => {
    const api = await serve("settings");
    await page.goto("/app/settings");
    await page.getByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }).click();
    await exercise("settings.signout-all.confirm", async () => {
      await page.getByRole("dialog").getByRole("button", { name: "Wyloguj wszędzie" }).click();
      return [
        await outcome.url(page, /\/login$/),
        await outcome.request(api, { method: "POST", path: "/api/auth/signout-all" }),
      ];
    });
    await expect(page.getByText(SETTINGS_EMAIL)).toHaveCount(0);
  });

  test("the password form: blank fields are refused with a summary that leads to each field", async ({
    page,
    serve,
  }) => {
    const api = await serve("settings");
    await page.goto("/app/settings");
    await passwordForm(page).getByRole("button", { name: "Zmień hasło" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Popraw pola: 2" })).toBeFocused();
    await exercise("settings.error.current", async () => {
      await page.getByRole("link", { name: "Wpisz obecne hasło." }).click();
      return [await outcome.focus(passwordForm(page).getByLabel("Obecne hasło"))];
    });
    await exercise("settings.error.next", async () => {
      await page.getByRole("link", { name: "Wpisz hasło." }).click();
      return [await outcome.focus(passwordForm(page).getByLabel(/Nowe hasło/))];
    });
    expect(api.requests.filter((r) => r.path === "/api/auth/password/change")).toHaveLength(0);
  });

  test("a valid change sends both passwords and ends the session", async ({ page, serve }) => {
    const api = await serve("settings");
    await page.goto("/app/settings");
    const form = passwordForm(page);
    await exercise("settings.password.current", async () => {
      await form.getByLabel("Obecne hasło").fill("my-current-password");
      return [await outcome.value(form.getByLabel("Obecne hasło"), "my-current-password")];
    });
    await exercise("settings.password.next", async () => {
      await form.getByLabel(/Nowe hasło/).fill(PHRASE);
      return [await outcome.value(form.getByLabel(/Nowe hasło/), PHRASE)];
    });
    await exercise("settings.password.submit", async () => {
      await form.getByRole("button", { name: "Zmień hasło" }).click();
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/auth/password/change",
          body: { current_password: "my-current-password", new_password: PHRASE },
        }),
      ];
    });
    await expect(page).toHaveURL(/\/login$/);
  });

  test("a wrong current password stays on the page and says so on that field", async ({ page, serve }) => {
    const { fx } = await import("../test/fixtures");
    const { replyFrom } = await import("../test/scenarios");
    await serve(
      createSettings([
        {
          operation: "POST /api/auth/password/change",
          reply: replyFrom(fx("POST /api/auth/password/change", "wrong_current_password")),
        },
      ]),
    );
    await page.goto("/app/settings");
    const form = passwordForm(page);
    await form.getByLabel("Obecne hasło").fill("not-my-password");
    await form.getByLabel(/Nowe hasło/).fill(PHRASE);
    await form.getByRole("button", { name: "Zmień hasło" }).click();
    await expect(
      page.getByRole("alert").filter({ hasText: "To nie jest Twoje obecne hasło." }),
    ).toBeFocused();
    await expect(page).toHaveURL(/\/app\/settings$/);
  });

  test("a person without a password is pointed to recovery", async ({ page, serve }) => {
    await serve("settings");
    await page.goto("/app/settings");
    await exercise("settings.password.recover", async () => {
      await page.getByRole("link", { name: "Ustaw hasło przez e-mail" }).click();
      return [await outcome.url(page, /\/password\/forgot$/)];
    });
  });

  test("the export downloads one JSON file with the person's data", async ({ page, serve }) => {
    const api = await serve("settings");
    await page.goto("/app/settings");
    await exercise("settings.export", async () => {
      const download = page.waitForEvent("download");
      await page.getByRole("button", { name: "Pobierz moje dane" }).click();
      const file = await download;
      expect(file.suggestedFilename()).toMatch(/^renti-moje-dane-\d{4}-\d{2}-\d{2}\.json$/);
      await expect(page.getByText("Plik został pobrany.")).toBeVisible();
      return [await outcome.request(api, { method: "GET", path: "/api/me/export" })];
    });
  });

  test("deleting the account asks for the address, refuses another one, then erases and signs out", async ({
    page,
    serve,
  }) => {
    const api = await serve("settings");
    await page.goto("/app/settings");
    const dialog = page.getByRole("dialog", { name: "Usunąć konto na stałe?" });
    await exercise("settings.erase.open", async () => {
      await page.getByRole("button", { name: "Usuń konto", exact: true }).click();
      return [await outcome.dialog(dialog, "open")];
    });
    await exercise("settings.erase.close", async () => {
      await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    await page.getByRole("button", { name: "Usuń konto", exact: true }).click();
    await exercise("settings.erase.cancel", async () => {
      await dialog.getByRole("button", { name: "Anuluj" }).click();
      return [await outcome.dialog(dialog, "closed")];
    });

    await page.getByRole("button", { name: "Usuń konto", exact: true }).click();
    const email = dialog.getByRole("textbox", { name: "Adres e-mail konta" });
    await exercise("settings.erase.email", async () => {
      await email.fill("ktos@example.test");
      return [await outcome.value(email, "ktos@example.test")];
    });
    await dialog.getByRole("button", { name: "Usuń konto na stałe" }).click();
    await expect(dialog.getByRole("alert").filter({ hasText: "Popraw 1 pole" })).toBeFocused();
    expect(api.requests.filter((r) => r.method === "DELETE")).toHaveLength(0);

    await email.fill(SETTINGS_EMAIL);
    await exercise("settings.erase.confirm", async () => {
      await dialog.getByRole("button", { name: "Usuń konto na stałe" }).click();
      return [
        await outcome.url(page, /\/login$/),
        await outcome.request(api, {
          method: "DELETE",
          path: "/api/me",
          body: { confirm_email: SETTINGS_EMAIL },
        }),
      ];
    });
  });
});
