import { QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { createQueryClient, tenantKey } from "../api/query";
import { useRecentAudits } from "../features/analyses/queries";
import { submission, useCreateAudit } from "../features/analyses/new/useCreateAudit";
import { bodyOf, fx } from "../test/fixtures";
import { server, useScenario } from "../test/handlers";
import { replyFrom, type Reply, type Scenario } from "../test/scenarios";
import { endSession, RequireSession, SESSION_KEY, SessionProvider, useMe, type Me } from "./session";
import { sendSessionSignal } from "./sessionBus";
import { registerTenantCleanup } from "./tenant";

/**
 * Audit F02 and F10 (frontend/docs/AUDIT-2026-10-15.md): every change of person, however it is noticed, purges the
 * previous person's state before the new one renders, cancels their requests, and makes their late answers inert.
 */

const base = bodyOf<Me>(fx("GET /api/me", "with_credits_and_flags"));
const alice: Me = { ...base, id: "00000000-0000-4000-8000-00000000000a", name: "Alicja" };
const bob: Me = { ...base, id: "00000000-0000-4000-8000-00000000000b", name: "Bogdan" };

/** The server's idea of who holds the cookie; tests change it to simulate expiry or another account. */
function signedIn(initial: Me | null) {
  const state: { current: Me | null } = { current: initial };
  const scenario: Scenario = {
    name: "session-transitions",
    description: "a session that can expire or change person",
    routes: [
      {
        operation: "GET /api/me",
        reply: (): Reply =>
          state.current === null
            ? replyFrom(fx("GET /api/me", "no_session"))
            : { status: 200, body: state.current },
      },
    ],
  };
  return { state, scenario };
}

/** Records, on every render, who is shown and whether the previous person's cached answer is still there. */
const seen: { name: string | null; aliceData: boolean }[] = [];
function Who() {
  const me = useMe();
  const client = useQueryClient();
  seen.push({ name: me.name, aliceData: client.getQueryData(tenantKey(alice.id, "probe")) !== undefined });
  return <p>Cześć, {me.name}</p>;
}

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderApp(element: React.ReactNode = <Who />) {
  const client = createQueryClient();
  const router = createMemoryRouter(
    [
      {
        path: "/login",
        element: (
          <>
            <p>formularz logowania</p>
            <Where />
          </>
        ),
      },
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app/*",
            element: (
              <>
                {element}
                <Where />
              </>
            ),
          },
        ],
      },
    ],
    { initialEntries: ["/app"] },
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

describe("a change of person purges the previous person's state", () => {
  it("expiry noticed by re-reading /api/me (401) runs the cleanups and empties the tenant cache", async () => {
    const { state: server, scenario } = signedIn(alice);
    useScenario(scenario);
    const client = renderApp();
    await screen.findByText("Cześć, Alicja");
    client.setQueryData(tenantKey(alice.id, "probe"), { secret: true });
    const cleanup = vi.fn();
    const off = registerTenantCleanup(cleanup);

    server.current = null; // the cookie expired on the server
    await act(async () => client.invalidateQueries({ queryKey: SESSION_KEY }));

    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
    expect(cleanup).toHaveBeenCalledOnce();
    expect(client.getQueryData(tenantKey(alice.id, "probe"))).toBeUndefined();
    off();
  });

  it("another tab signing in as somebody else: the new person never renders next to the old person's data", async () => {
    const { state: server, scenario } = signedIn(alice);
    useScenario(scenario);
    seen.length = 0;
    const client = renderApp();
    await screen.findByText("Cześć, Alicja");
    client.setQueryData(tenantKey(alice.id, "probe"), { secret: true });
    const cleanup = vi.fn();
    const off = registerTenantCleanup(cleanup);

    server.current = bob; // signed in as Bogdan in another tab: the cookie now belongs to him
    sendSessionSignal("signed-in");

    expect(await screen.findByText("Cześć, Bogdan")).toBeInTheDocument();
    expect(cleanup).toHaveBeenCalledOnce();
    expect(client.getQueryData(tenantKey(alice.id, "probe"))).toBeUndefined();
    expect(seen.filter((render) => render.name === "Bogdan" && render.aliceData)).toEqual([]);
    off();
  });

  it("the same person signing in again keeps their state (no needless purge)", async () => {
    useScenario(signedIn(alice).scenario);
    const client = renderApp();
    await screen.findByText("Cześć, Alicja");
    client.setQueryData(tenantKey(alice.id, "probe"), { kept: true });
    const cleanup = vi.fn();
    const off = registerTenantCleanup(cleanup);

    sendSessionSignal("signed-in");
    await act(async () => client.invalidateQueries({ queryKey: SESSION_KEY }));

    expect(cleanup).not.toHaveBeenCalled();
    expect(client.getQueryData(tenantKey(alice.id, "probe"))).toEqual({ kept: true });
    off();
  });
});

describe("requests and late answers of a session that ended", () => {
  it("ending the session aborts the HTTP request of a tenant read in flight", async () => {
    useScenario(signedIn(alice).scenario);
    let signal: AbortSignal | null = null;
    server.use(
      http.get("*/api/audits", async ({ request }) => {
        signal = request.signal;
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );
    function Recent() {
      useRecentAudits();
      return <Who />;
    }
    const client = renderApp(<Recent />);
    await screen.findByText("Cześć, Alicja");
    await waitFor(() => expect(signal).not.toBeNull());

    act(() => endSession(client));

    await waitFor(() => expect(signal?.aborted).toBe(true));
  });

  it("a creation answered after sign-out does not navigate to the analysis", async () => {
    let release: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      release = resolve;
    });
    useScenario(signedIn(alice).scenario);
    server.use(
      http.post("*/api/audits", async () => {
        await answered;
        const accepted = fx("POST /api/audits", "accepted");
        return new HttpResponse(JSON.stringify(accepted.body), {
          status: accepted.status,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    function Create() {
      const create = useCreateAudit();
      return (
        <>
          <Who />
          <button type="button" onClick={() => create.mutate(submission("ID4abcd"))}>
            Utwórz
          </button>
        </>
      );
    }
    const client = renderApp(<Create />);
    await screen.findByText("Cześć, Alicja");

    fireEvent.click(screen.getByRole("button", { name: "Utwórz" }));
    act(() => endSession(client, { deliberate: true }));
    await screen.findByText("formularz logowania");
    release();
    await act(async () => delay(20));

    // Still the sign-in page of a deliberate exit: a late navigation would bounce back as ?next=/app/analyses/<id>.
    expect(screen.getByText("formularz logowania")).toBeInTheDocument();
    expect(screen.getByTestId("where")).not.toHaveTextContent("analyses");
  });
});
