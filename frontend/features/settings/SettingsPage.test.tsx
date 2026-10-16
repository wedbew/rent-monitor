import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../api/query";
import { endSession, RequireSession, SessionProvider } from "../../shell/session";
import { fx } from "../../test/fixtures";
import { server, useScenario as serveScenario } from "../../test/handlers";
import {
  createSettings,
  replyFrom,
  SETTINGS_EMAIL,
  type MockRequest,
  type Reply,
  type Route,
} from "../../test/scenarios";
import { SettingsPage } from "./SettingsPage";

/**
 * RM-278: the settings page against the registry's settings scenarios, through the real session boundary. A request
 * that ends the session must land on the sign-in page; a refusal must stay on the page with the person's words.
 */

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname}</p>;
}

function renderPage(routes: readonly Route[] = []) {
  serveScenario(createSettings(routes));
  const client = createQueryClient();
  const router = createMemoryRouter(
    [
      { path: "/login", element: <p>formularz logowania</p> },
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app/settings",
            element: (
              <>
                <SettingsPage />
                <Where />
              </>
            ),
          },
        ],
      },
    ],
    { initialEntries: ["/app/settings"] },
  );
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
  return client;
}

const PHRASE = "correct-horse-battery-staple-91";

const fixtureRoute = (operation: string, name: string): Route => ({
  operation,
  reply: replyFrom(fx(operation, name)),
});

/** A route that records what it was sent and answers with a fixture. */
function recording(operation: string, name: string, sent: MockRequest[]): Route {
  return {
    operation,
    reply: (request): Reply => {
      sent.push(request);
      return replyFrom(fx(operation, name));
    },
  };
}

describe("settings page", () => {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:fixture");
  const anchorClick = vi.fn();

  beforeEach(() => {
    createObjectURL.mockClear();
    anchorClick.mockClear();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(anchorClick);
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = vi.fn();
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows the account and the browsers, the current one first and marked", async () => {
    renderPage();
    expect(await screen.findByText(SETTINGS_EMAIL)).toBeInTheDocument();
    const list = await screen.findByRole("list", { name: "Aktywne sesje" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[0] as HTMLElement).getByText("Ta przeglądarka")).toBeInTheDocument();
    expect(screen.getAllByText("Ta przeglądarka")).toHaveLength(1);
  });

  it("says so when the sessions cannot be read, and asks again on request", async () => {
    let calls = 0;
    renderPage([
      {
        operation: "GET /api/auth/sessions",
        reply: () => {
          calls += 1;
          return calls === 1
            ? { status: 200, body: { not: "a list" } }
            : replyFrom(fx("GET /api/auth/sessions", "three_sessions"));
        },
      },
    ]);
    expect(await screen.findByText("Nie udało się wczytać sesji")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByRole("list", { name: "Aktywne sesje" })).toBeInTheDocument();
  });

  describe("sign out everywhere", () => {
    it("asks first; cancelling sends nothing", async () => {
      const sent: MockRequest[] = [];
      renderPage([recording("POST /api/auth/signout-all", "signed_out_everywhere", sent)]);
      await userEvent.click(await screen.findByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }));
      const dialog = await screen.findByRole("dialog", { name: "Wylogować ze wszystkich urządzeń?" });
      await userEvent.click(within(dialog).getByRole("button", { name: "Anuluj" }));
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
      expect(sent).toHaveLength(0);
      expect(screen.getByTestId("where")).toHaveTextContent("/app/settings");
    });

    it("confirming ends the session here and goes to sign-in", async () => {
      const sent: MockRequest[] = [];
      renderPage([recording("POST /api/auth/signout-all", "signed_out_everywhere", sent)]);
      await userEvent.click(await screen.findByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }));
      await userEvent.click(await screen.findByRole("button", { name: "Wyloguj wszędzie" }));
      expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
      expect(sent).toHaveLength(1);
    });

    it("a second activation while the request is pending sends nothing more", async () => {
      let calls = 0;
      renderPage([
        {
          operation: "POST /api/auth/signout-all",
          reply: () => {
            calls += 1;
            return { ...replyFrom(fx("POST /api/auth/signout-all", "signed_out_everywhere")), delayMs: 300 };
          },
        },
      ]);
      await userEvent.click(await screen.findByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }));
      const confirm = await screen.findByRole("button", { name: "Wyloguj wszędzie" });
      await userEvent.click(confirm);
      await userEvent.click(confirm);
      await screen.findByText("formularz logowania");
      expect(calls).toBe(1);
    });

    it("a refusal stays in the dialog and the session stays", async () => {
      renderPage([fixtureRoute("POST /api/auth/signout-all", "wrong_origin")]);
      await userEvent.click(await screen.findByRole("button", { name: "Wyloguj ze wszystkich urządzeń" }));
      await userEvent.click(await screen.findByRole("button", { name: "Wyloguj wszędzie" }));
      expect(await within(await screen.findByRole("dialog")).findByRole("alert")).toBeInTheDocument();
      expect(screen.queryByText("formularz logowania")).toBeNull();
    });
  });

  describe("password", () => {
    const fill = async (current: string, next: string) => {
      const form = await screen.findByRole("form", { name: "Zmiana hasła" });
      if (current) await userEvent.type(within(form).getByLabelText("Obecne hasło"), current);
      if (next) await userEvent.type(within(form).getByLabelText(/Nowe hasło/), next);
      await userEvent.click(within(form).getByRole("button", { name: "Zmień hasło" }));
    };

    it("blank fields are refused in the browser, with a summary, and nothing is sent", async () => {
      const sent: MockRequest[] = [];
      renderPage([recording("POST /api/auth/password/change", "changed", sent)]);
      await fill("", "");
      expect(await screen.findByText("Popraw pola: 2")).toBeInTheDocument();
      expect(sent).toHaveLength(0);
    });

    it("a wrong current password is said on that field", async () => {
      renderPage([fixtureRoute("POST /api/auth/password/change", "wrong_current_password")]);
      await fill("not-my-password", PHRASE);
      expect((await screen.findAllByText("To nie jest Twoje obecne hasło.")).length).toBeGreaterThan(0);
      expect(screen.queryByText("formularz logowania")).toBeNull();
    });

    it("a weak new password is said on the new-password field, with the reason", async () => {
      renderPage([fixtureRoute("POST /api/auth/password/change", "weak_new_password")]);
      await fill("my-current-password", "password1234");
      expect((await screen.findAllByText(/zbyt popularne/i)).length).toBeGreaterThan(0);
    });

    it("a change sends both passwords and ends the session (the server signed every browser out)", async () => {
      const sent: MockRequest[] = [];
      renderPage([recording("POST /api/auth/password/change", "changed", sent)]);
      await fill("my-current-password", PHRASE);
      expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
      expect(sent[0]?.body).toEqual({
        current_password: "my-current-password",
        new_password: PHRASE,
      });
    });

    it("points a person without a password to recovery", async () => {
      renderPage();
      const link = await screen.findByRole("link", { name: "Ustaw hasło przez e-mail" });
      expect(link).toHaveAttribute("href", "/password/forgot");
    });
  });

  describe("data export", () => {
    it("saves the document as a file, keeps nothing, and says it was saved", async () => {
      renderPage();
      await userEvent.click(await screen.findByRole("button", { name: "Pobierz moje dane" }));
      expect(await screen.findByText("Plik został pobrany.")).toBeInTheDocument();
      expect(createObjectURL).toHaveBeenCalledOnce();
      const blob = createObjectURL.mock.calls[0]?.[0] as Blob;
      expect(JSON.parse(await blob.text())).toHaveProperty("profile");
      expect(anchorClick).toHaveBeenCalledOnce();
    });

    it("a throttled export says when to try again and saves nothing", async () => {
      renderPage([fixtureRoute("GET /api/me/export", "rate_limited")]);
      await userEvent.click(await screen.findByRole("button", { name: "Pobierz moje dane" }));
      expect(await screen.findByText(/Zbyt wiele prób/)).toBeInTheDocument();
      expect(screen.getByText(/za 5 minut/)).toBeInTheDocument();
      expect(createObjectURL).not.toHaveBeenCalled();
    });

    it("an answer that arrives after the session ended is dropped, not saved for the next person", async () => {
      const client = renderPage();
      server.use(
        http.get("*/api/me/export", async () => {
          await delay(200);
          return HttpResponse.json(fx("GET /api/me/export", "export").body as Record<string, unknown>);
        }),
      );
      await userEvent.click(await screen.findByRole("button", { name: "Pobierz moje dane" }));
      act(() => {
        endSession(client);
      });
      await delay(350);
      expect(createObjectURL).not.toHaveBeenCalled();
    });
  });

  describe("delete the account", () => {
    const open = async () => {
      await userEvent.click(await screen.findByRole("button", { name: "Usuń konto" }));
      return screen.findByRole("dialog", { name: "Usunąć konto na stałe?" });
    };

    it("refuses a different address in the browser and sends nothing", async () => {
      const sent: MockRequest[] = [];
      renderPage([recording("DELETE /api/me", "erased", sent)]);
      const dialog = await open();
      await userEvent.type(within(dialog).getByLabelText("Adres e-mail konta"), "ktos@example.test");
      await userEvent.click(within(dialog).getByRole("button", { name: "Usuń konto na stałe" }));
      expect(
        (await within(dialog).findAllByText("Wpisz dokładnie adres e-mail swojego konta.")).length,
      ).toBeGreaterThan(0);
      expect(sent).toHaveLength(0);
    });

    it("the server's own mismatch answer is shown on the field too", async () => {
      renderPage([fixtureRoute("DELETE /api/me", "confirmation_mismatch")]);
      const dialog = await open();
      await userEvent.type(within(dialog).getByLabelText("Adres e-mail konta"), SETTINGS_EMAIL);
      await userEvent.click(within(dialog).getByRole("button", { name: "Usuń konto na stałe" }));
      expect(
        (await within(dialog).findAllByText("Wpisz dokładnie adres e-mail swojego konta.")).length,
      ).toBeGreaterThan(0);
      expect(screen.queryByText("formularz logowania")).toBeNull();
    });

    it("the typed address (any case) deletes the account, ends the session and leaves", async () => {
      const sent: MockRequest[] = [];
      renderPage([recording("DELETE /api/me", "erased", sent)]);
      const dialog = await open();
      await userEvent.type(within(dialog).getByLabelText("Adres e-mail konta"), SETTINGS_EMAIL.toUpperCase());
      await userEvent.click(within(dialog).getByRole("button", { name: "Usuń konto na stałe" }));
      expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
      expect(sent[0]?.body).toEqual({ confirm_email: SETTINGS_EMAIL.toUpperCase() });
    });
  });
});
