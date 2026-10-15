import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { api, unwrap } from "../api/client";
import { ApiError } from "../api/errors";
import { clearTenantState, invalidateAudits } from "../api/query";
import type { components } from "../api/schema.generated";
import { onSessionExpired } from "../api/session-events";
import { Button } from "../ui/Button";
import { InlineNotice } from "../ui/Status";
import { onSessionSignal, sendSessionSignal } from "./sessionBus";
import { advanceSessionGeneration, runTenantCleanups } from "./tenant";
import styles from "./session.module.css";

export type Me = components["schemas"]["MeDetailOut"];

/** The one session query. `null` data means "nobody is signed in" (a 401 from /api/me is an answer, not a failure). */
export const SESSION_KEY = ["session"] as const;
/** Whether the person chose to sign out (then the sign-in page does not offer to go back where they were). */
const SESSION_ENDED_KEY = ["session", "ended-by-choice"] as const;

/**
 * The one door every change of person goes through: a 401 here, another tab's sign-in, a sign-in in this tab. When
 * the answer is somebody else (or nobody) the previous person's state is purged BEFORE the answer is stored, so no
 * component ever renders the new person next to the old person's cache.
 */
function sessionQueryFn(client: QueryClient) {
  return async ({ signal }: { readonly signal: AbortSignal }): Promise<Me | null> => {
    const result = await api.GET("/api/me", { signal });
    const next = result.response.status === 401 ? null : unwrap(result);
    const previous = client.getQueryData<Me | null>(SESSION_KEY);
    if (previous !== undefined && previous !== null && previous.id !== next?.id) purgeTenant(client);
    return next;
  };
}

/** Close streams and release resources, forget every tenant answer and mutation, and make earlier work late. */
function purgeTenant(client: QueryClient): void {
  advanceSessionGeneration();
  runTenantCleanups();
  clearTenantState(client, SESSION_KEY);
}

export type SessionState =
  | { readonly status: "loading" }
  | { readonly status: "signedOut"; readonly deliberate: boolean }
  | { readonly status: "signedIn"; readonly me: Me }
  | { readonly status: "error"; readonly error: unknown; readonly retry: () => void };

const SessionContext = createContext<SessionState>({ status: "loading" });

/** End the session in this tab: close streams and release media, empty every tenant cache, show signed out. */
export function endSession(client: QueryClient, options: { readonly deliberate?: boolean } = {}): void {
  void client.cancelQueries({ queryKey: SESSION_KEY });
  purgeTenant(client);
  client.setQueryData(SESSION_ENDED_KEY, options.deliberate === true);
  client.setQueryData(SESSION_KEY, null);
}

/**
 * A session started in this tab (sign-in, sign-up verification). The sign-in routes answer with a short profile
 * (`MeOut`); the app needs the full one (balance, flags, Otodom state), so it is fetched BEFORE anyone navigates:
 * the private routes never see a half-filled session, and never bounce a freshly signed-in person back to sign-in.
 */
export async function startSession(client: QueryClient): Promise<void> {
  client.setQueryData(SESSION_ENDED_KEY, false);
  await client.fetchQuery({ queryKey: SESSION_KEY, queryFn: sessionQueryFn(client), staleTime: 0 });
  sendSessionSignal("signed-in");
}

/**
 * The balance and the lists belong to the server: after anything that changes them (an analysis settled, a pack
 * granted) ask again instead of adding or subtracting locally.
 */
export function refreshAccount(client: QueryClient): void {
  refreshBalance(client);
  void invalidateAudits(client);
}

/** Only the profile (balance, flags, Otodom state): safe to call from inside a query function of `["audits", ...]`. */
export function refreshBalance(client: QueryClient): void {
  void client.invalidateQueries({ queryKey: SESSION_KEY });
}

export function SessionProvider({ children }: { readonly children: ReactNode }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: SESSION_KEY,
    queryFn: sessionQueryFn(client),
    // The session is the one thing worth checking when the tab comes back: a revoked session should be noticed.
    refetchOnWindowFocus: true,
    staleTime: 10_000,
  });

  useEffect(() => {
    const offExpired = onSessionExpired(() => endSession(client));
    const offSignal = onSessionSignal((signal) => {
      if (signal === "signed-out") endSession(client);
      // Possibly somebody else: the session query compares the id and purges before the new person shows.
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
