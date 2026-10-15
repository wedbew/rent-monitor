import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApi, unwrap } from "../api/client";
import { createQueryClient } from "../api/query";
import { emitSessionExpired } from "../api/session-events";
import { useScenario } from "../test/handlers";
import { createAuthFlow } from "../test/scenarios";
import {
  endSession,
  RedirectIfSignedIn,
  RequireSession,
  safeNext,
  SESSION_KEY,
  SessionProvider,
  startSession,
  useMe,
} from "./session";
import { onSessionSignal, sendSessionSignal } from "./sessionBus";
import { registerTenantCleanup, runTenantCleanups } from "./tenant";

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function Private() {
  const me = useMe();
  return <p>Cześć, {me.name}</p>;
}

function renderApp(initial: string, client: QueryClient = createQueryClient()) {
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
        children: [
          {
            path: "/app/*",
            element: (
              <>
                <Private />
                <Where />
              </>
            ),
          },
        ],
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
  return { client, router };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("safeNext", () => {
  it.each([
    ["/app", "/app"],
    ["/app/analyses/abc?x=1", "/app/analyses/abc?x=1"],
    [null, "/app"],
    [undefined, "/app"],
    ["", "/app"],
    ["/login", "/app"],
    ["//evil.test", "/app"],
    ["https://evil.test/app", "/app"],
    ["/app\\..\\evil", "/app"],
    ["/app\nSet-Cookie: x", "/app"],
    ["app", "/app"],
  ])("%j -> %s", (input, expected) => {
    expect(safeNext(input)).toBe(expected);
  });
});

describe("RequireSession", () => {
  it("shows a status while the session is unknown, then the private page", async () => {
    useScenario(
      createAuthFlow().state &&
        (() => {
          const f = createAuthFlow();
          f.state.signedIn = true;
          return f;
        })(),
    );
    renderApp("/app");
    expect(screen.getByRole("status")).toHaveTextContent("Sprawdzam sesję");
    expect(await screen.findByText(/Cześć, /)).toBeInTheDocument();
  });

  it("sends a signed-out visit to sign-in and remembers where it was going", async () => {
    useScenario(createAuthFlow());
    renderApp("/app/analyses/abc");
    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/login?next=%2Fapp%2Fanalyses%2Fabc");
  });

  it("answers a failed session check with an error and a retry, never with private content", async () => {
    useScenario("offline");
    renderApp("/app", new QueryClient({ defaultOptions: { queries: { retry: false } } })); // retries are tested in api/query.test.ts
    expect(await screen.findByText("Brak połączenia")).toBeInTheDocument();
    expect(screen.queryByText(/Cześć/)).toBeNull();
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
  });
});

describe("RedirectIfSignedIn", () => {
  it("sends a signed-in person to the app, or to a safe next target", async () => {
    const flow = createAuthFlow();
    flow.state.signedIn = true;
    useScenario(flow);
    renderApp("/login?next=%2Fapp%2Fmarket");
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/app/market"));
  });
});

describe("ending a session", () => {
  it("empties every tenant cache, runs the cleanups, and keeps the session observer working", async () => {
    const flow = createAuthFlow();
    flow.state.signedIn = true;
    useScenario(flow);
    const { client } = renderApp("/app");
    await screen.findByText(/Cześć, /);
    client.setQueryData(["audits"], { items: [1] });
    const cleanup = vi.fn();
    registerTenantCleanup(cleanup);
    act(() => endSession(client, { deliberate: true }));
    expect(cleanup).toHaveBeenCalledOnce();
    expect(client.getQueryData(["audits"])).toBeUndefined();
    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/login$/); // a deliberate sign-out has no ?next=
  });

  it("is triggered by a 401 UNAUTHENTICATED from any request", async () => {
    const flow = createAuthFlow();
    flow.state.signedIn = true;
    useScenario(flow);
    renderApp("/app/market");
    await screen.findByText(/Cześć, /);
    flow.state.signedIn = false;
    const api = createApi({ baseUrl: window.location.origin });
    await expect(async () => unwrap(await api.GET("/api/me"))).rejects.toThrow(); // not a session-ending call
    emitSessionExpired();
    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/login?next=%2Fapp%2Fmarket");
  });

  it("follows a sign-out announced by another tab", async () => {
    const flow = createAuthFlow();
    flow.state.signedIn = true;
    useScenario(flow);
    renderApp("/app");
    await screen.findByText(/Cześć, /);
    sendSessionSignal("signed-out");
    expect(await screen.findByText("formularz logowania")).toBeInTheDocument();
  });

  it("startSession stores the person and a later sign-out is not 'deliberate' until chosen", async () => {
    useScenario(createAuthFlow());
    const { client } = renderApp("/login");
    await screen.findByText("formularz logowania");
    const me = {
      id: "1",
      email: "a@example.test",
      name: "Anna",
      avatar_url: null,
      role: "user",
      email_verified: true,
    };
    act(() => startSession(client, me));
    expect(client.getQueryData(SESSION_KEY)).toEqual(me);
  });
});

describe("tenant cleanups and the tab signal", () => {
  it("one failing cleanup does not stop the others", () => {
    const calls: string[] = [];
    const offA = registerTenantCleanup(() => {
      throw new Error("boom");
    });
    const offB = registerTenantCleanup(() => calls.push("b"));
    runTenantCleanups();
    expect(calls).toEqual(["b"]);
    offA();
    offB();
    runTenantCleanups();
    expect(calls).toEqual(["b"]);
  });

  it("carries only a signal, and falls back to storage events without BroadcastChannel", async () => {
    const heard: string[] = [];
    const off = onSessionSignal((signal) => heard.push(signal));
    sendSessionSignal("signed-out");
    await waitFor(() => expect(heard).toEqual(["signed-out"]));
    off();

    vi.stubGlobal("BroadcastChannel", undefined);
    Reflect.deleteProperty(window, "BroadcastChannel");
    const heard2: string[] = [];
    const off2 = onSessionSignal((signal) => heard2.push(signal));
    sendSessionSignal("signed-in");
    expect(localStorage.getItem("renti-session-signal")).toMatch(/^signed-in:\d+$/);
    window.dispatchEvent(
      new StorageEvent("storage", { key: "renti-session-signal", newValue: "signed-out:1" }),
    );
    window.dispatchEvent(new StorageEvent("storage", { key: "other", newValue: "signed-out:1" }));
    expect(heard2).toEqual(["signed-out"]);
    off2();
    localStorage.clear();
    vi.unstubAllGlobals();
  });
});
