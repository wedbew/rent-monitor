import { QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryClient, tenantKey } from "../api/query";
import { useScenario } from "../test/handlers";
import { createAuthFlow, type Reply } from "../test/scenarios";
import { RedirectIfSignedIn, RequireSession, SESSION_KEY, SessionProvider, signOut, useMe } from "./session";
import { onSessionSignal } from "./sessionBus";
import { registerTenantCleanup } from "./tenant";

/**
 * Audit F03 (frontend/docs/AUDIT-2026-10-15.md): a sign-out the server did not confirm is never shown as done.
 * The person's data is hidden at once; "signed out" waits for the server; a reload retries before anything else.
 */

const FLAG = "renti-signout-unconfirmed";
const DROPPED: Reply = { status: 0, networkError: true };
const BROKEN: Reply = { status: 503, text: "<html>maintenance</html>", contentType: "text/html" };

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function Private() {
  const me = useMe();
  return <p>Cześć, {me.name}</p>;
}

function renderApp(initial = "/app") {
  const client = createQueryClient();
  const router = createMemoryRouter(
    [
      {
        path: "/login",
        element: (
          <RedirectIfSignedIn>
            <p>formularz logowania</p>
            <Where />
          </RedirectIfSignedIn>
        ),
      },
      {
        element: <RequireSession />,
        children: [{ path: "/app/*", element: <Private /> }],
      },
    ],
    { initialEntries: [initial] },
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

afterEach(() => {
  sessionStorage.clear();
});

describe("a sign-out the server did not confirm", () => {
  it.each([
    ["the request never arrives", DROPPED],
    ["the server fails", BROKEN],
  ])("%s: data hidden, no claim of success, a retry offered", async (_, failure) => {
    const flow = createAuthFlow({ "POST /api/auth/signout": failure });
    flow.state.signedIn = true;
    useScenario(flow);
    const client = renderApp();
    await screen.findByText(/Cześć, /);
    client.setQueryData(tenantKey("someone", "audits"), { items: [1] });
    const cleanup = vi.fn();
    const off = registerTenantCleanup(cleanup);
    const heard: string[] = [];
    const offSignal = onSessionSignal((signal) => heard.push(signal));

    await act(async () => expect(signOut(client)).rejects.toThrow());

    expect(await screen.findByText("Nie udało się potwierdzić wylogowania")).toBeInTheDocument();
    expect(screen.queryByText(/Cześć, /)).toBeNull();
    expect(screen.queryByText("formularz logowania")).toBeNull();
    expect(cleanup).toHaveBeenCalled();
    expect(client.getQueryData(tenantKey("someone", "audits"))).toBeUndefined();
    expect(sessionStorage.getItem(FLAG)).toBe("1");
    expect(heard).toEqual([]); // other tabs are not told the session ended: it has not
    off();
    offSignal();
  });

  it("re-reading the session while it still works (focus) does not restore the private pages", async () => {
    const flow = createAuthFlow({ "POST /api/auth/signout": DROPPED });
    flow.state.signedIn = true;
    useScenario(flow);
    const client = renderApp();
    await screen.findByText(/Cześć, /);
    await act(async () => expect(signOut(client)).rejects.toThrow());

    await act(async () => client.invalidateQueries({ queryKey: SESSION_KEY }));

    expect(screen.getByText("Nie udało się potwierdzić wylogowania")).toBeInTheDocument();
    expect(screen.queryByText(/Cześć, /)).toBeNull();
  });

  it("the sign-in page does not offer itself while the old session may still be alive", async () => {
    sessionStorage.setItem(FLAG, "1");
    const flow = createAuthFlow({ "POST /api/auth/signout": DROPPED });
    flow.state.signedIn = true;
    useScenario(flow);
    renderApp("/login");
    expect(await screen.findByText("Nie udało się potwierdzić wylogowania")).toBeInTheDocument();
    expect(screen.queryByText("formularz logowania")).toBeNull();
  });

  it("a retry that the server confirms leads to sign-in and forgets the pending state", async () => {
    const overrides: Record<string, Reply> = { "POST /api/auth/signout": DROPPED };
    const flow = createAuthFlow(overrides);
    flow.state.signedIn = true;
    useScenario(flow);
    const client = renderApp();
    await screen.findByText(/Cześć, /);
    await act(async () => expect(signOut(client)).rejects.toThrow());
    const heard: string[] = [];
    const offSignal = onSessionSignal((signal) => heard.push(signal));

    delete overrides["POST /api/auth/signout"]; // the connection is back
    fireEvent.click(await screen.findByRole("button", { name: "Spróbuj wylogować ponownie" }));

    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/login$/);
    expect(sessionStorage.getItem(FLAG)).toBeNull();
    await waitFor(() => expect(heard).toEqual(["signed-out"]));
    offSignal();
  });

  it("a reload of the tab retries the sign-out before showing anything private", async () => {
    sessionStorage.setItem(FLAG, "1");
    const flow = createAuthFlow();
    flow.state.signedIn = true; // the cookie survived the failed attempt
    useScenario(flow);
    renderApp();

    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
    expect(flow.calls).toContain("signout");
    expect(screen.queryByText(/Cześć, /)).toBeNull();
    expect(sessionStorage.getItem(FLAG)).toBeNull();
  });

  it("a session the server already ended (401) settles the pending state as signed out", async () => {
    const flow = createAuthFlow({ "POST /api/auth/signout": DROPPED });
    flow.state.signedIn = true;
    useScenario(flow);
    const client = renderApp();
    await screen.findByText(/Cześć, /);
    await act(async () => expect(signOut(client)).rejects.toThrow());

    flow.state.signedIn = false; // it expired, or another device signed out everywhere
    await act(async () => client.invalidateQueries({ queryKey: SESSION_KEY }));

    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/login$/);
    expect(sessionStorage.getItem(FLAG)).toBeNull();
  });
});
