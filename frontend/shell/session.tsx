import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { api, unwrap } from "../api/client";
import { ApiError } from "../api/errors";
import { clearTenantState } from "../api/query";
import type { components } from "../api/schema.generated";
import { onSessionExpired } from "../api/session-events";
import { Button } from "../ui/Button";
import { InlineNotice } from "../ui/Status";
import { onSessionSignal, sendSessionSignal } from "./sessionBus";
import { runTenantCleanups } from "./tenant";
import styles from "./session.module.css";

export type Me = components["schemas"]["MeDetailOut"];

/** The one session query. `null` data means "nobody is signed in" (a 401 from /api/me is an answer, not a failure). */
export const SESSION_KEY = ["session"] as const;
/** Whether the person chose to sign out (then the sign-in page does not offer to go back where they were). */
const SESSION_ENDED_KEY = ["session", "ended-by-choice"] as const;

async function fetchMe(): Promise<Me | null> {
  const result = await api.GET("/api/me");
  if (result.response.status === 401) return null;
  return unwrap(result);
}

export type SessionState =
  | { readonly status: "loading" }
  | { readonly status: "signedOut"; readonly deliberate: boolean }
  | { readonly status: "signedIn"; readonly me: Me }
  | { readonly status: "error"; readonly error: unknown; readonly retry: () => void };

const SessionContext = createContext<SessionState>({ status: "loading" });

/** End the session in this tab: close streams and release media, empty every tenant cache, show signed out. */
export function endSession(client: QueryClient, options: { readonly deliberate?: boolean } = {}): void {
  runTenantCleanups();
  clearTenantState(client, SESSION_KEY);
  client.setQueryData(SESSION_ENDED_KEY, options.deliberate === true);
  client.setQueryData(SESSION_KEY, null);
}

/** A session started in this tab (sign-in, sign-up verification): remember who, tell the other tabs. */
export function startSession(client: QueryClient, me: Me | components["schemas"]["MeOut"]): void {
  client.setQueryData(SESSION_ENDED_KEY, false);
  client.setQueryData(SESSION_KEY, me);
  sendSessionSignal("signed-in");
}

export function SessionProvider({ children }: { readonly children: ReactNode }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: SESSION_KEY,
    queryFn: fetchMe,
    // The session is the one thing worth checking when the tab comes back: a revoked session should be noticed.
    refetchOnWindowFocus: true,
    staleTime: 10_000,
  });

  useEffect(() => {
    const offExpired = onSessionExpired(() => endSession(client));
    const offSignal = onSessionSignal((signal) => {
      if (signal === "signed-out") endSession(client);
      else void client.invalidateQueries({ queryKey: SESSION_KEY });
    });
    return () => {
      offExpired();
      offSignal();
    };
  }, [client]);

  const retry = useCallback(() => {
    void query.refetch();
  }, [query]);

  const state = useMemo<SessionState>(() => {
    if (query.data !== undefined && query.data !== null) return { status: "signedIn", me: query.data };
    if (query.data === null)
      return { status: "signedOut", deliberate: client.getQueryData(SESSION_ENDED_KEY) === true };
    if (query.isError) return { status: "error", error: query.error, retry };
    return { status: "loading" };
  }, [client, query.data, query.isError, query.error, retry]);

  return <SessionContext.Provider value={state}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  return useContext(SessionContext);
}

/** The signed-in person; throws outside RequireSession, where it cannot be absent. */
export function useMe(): Me {
  const state = useSession();
  if (state.status !== "signedIn") throw new Error("useMe() outside a signed-in route");
  return state.me;
}

/** Only an in-app path may be a `next` target: never another origin (no open redirect). */
export function safeNext(next: string | null | undefined): string {
  if (typeof next !== "string" || !next.startsWith("/app")) return "/app";
  if (next.startsWith("//") || next.includes("\\") || [...next].some((c) => c.charCodeAt(0) < 32))
    return "/app";
  return next;
}

function FullPage({ children }: { readonly children: ReactNode }) {
  return <div className={styles["full"]}>{children}</div>;
}

/** Private routes. Signed out: go to sign-in and come back; unknown: a status, never a flash of private content. */
export function RequireSession() {
  const state = useSession();
  const location = useLocation();
  switch (state.status) {
    case "loading":
      return (
        <FullPage>
          <p role="status" aria-live="polite">
            Sprawdzam sesję…
          </p>
        </FullPage>
      );
    case "error":
      return (
        <FullPage>
          <InlineNotice
            tone="danger"
            title={state.error instanceof ApiError ? "Nie udało się sprawdzić sesji" : "Brak połączenia"}
            live="alert"
            actions={
              <Button type="button" variant="primary" icon="refresh" onClick={state.retry}>
                Spróbuj ponownie
              </Button>
            }
          >
            Spróbuj ponownie za chwilę.
          </InlineNotice>
        </FullPage>
      );
    case "signedOut":
      return (
        <Navigate
          to={
            state.deliberate
              ? "/login"
              : `/login?next=${encodeURIComponent(location.pathname + location.search)}`
          }
          replace
        />
      );
    case "signedIn":
      return <Outlet />;
  }
}

/** Sign-in pages: someone already signed in has nothing to do here. */
export function RedirectIfSignedIn({ children }: { readonly children: ReactNode }) {
  const state = useSession();
  const [search] = [new URLSearchParams(useLocation().search)];
  if (state.status === "signedIn") return <Navigate to={safeNext(search.get("next"))} replace />;
  return <>{children}</>;
}
