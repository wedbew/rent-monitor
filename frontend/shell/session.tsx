import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { api, unwrap, unwrapEmpty } from "../api/client";
import { ApiError } from "../api/errors";
import { clearTenantState, invalidateAudits } from "../api/query";
import type { components } from "../api/schema.generated";
import { onSessionExpired } from "../api/session-events";
import { Button } from "../ui/Button";
import { InlineNotice } from "../ui/Status";
import { onSessionSignal, sendSessionSignal } from "./sessionBus";
import { advanceSessionGeneration, runTenantCleanups } from "./tenant";
import styles from "./session.module.css";
import { t } from "../i18n";

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
    // The server says there is no session while a sign-out was unconfirmed: in effect it happened (the provider
    // then settles the pending state, after this null is stored).
    if (next === null && client.getQueryData(SIGNOUT_PENDING_KEY) === true)
      client.setQueryData(SESSION_ENDED_KEY, true);
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
  /** Sign-out was asked for but the server has not confirmed it: the cookie may still work. Nothing private shows. */
  | { readonly status: "signOutPending"; readonly retrying: boolean; readonly retry: () => void }
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
  // Last: whatever ended it (this tab, another tab, a 401), there is no session left. Cleared after the session is
  // already null, so no render ever sees "not pending" next to the old profile.
  setSignOutPending(client, false);
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
 * Sign-out that the server has not confirmed. Kept in the cache for this tab and in sessionStorage so a reload of
 * the tab neither shows the private pages again nor claims the session ended: it retries the sign-out first. Only
 * a flag is stored ("1"), never a token or anything about the person; the key carries no word like "session".
 */
const SIGNOUT_PENDING_KEY = ["session", "sign-out-pending"] as const;
const SIGNOUT_PENDING_STORAGE = "renti-signout-unconfirmed";

function readPendingFlag(): boolean {
  try {
    return sessionStorage.getItem(SIGNOUT_PENDING_STORAGE) === "1";
  } catch {
    return false;
  }
}

function writePendingFlag(pending: boolean): void {
  try {
    if (pending) sessionStorage.setItem(SIGNOUT_PENDING_STORAGE, "1");
    else sessionStorage.removeItem(SIGNOUT_PENDING_STORAGE);
  } catch {
    // Storage blocked: the pending state still holds for this page's life; a reload asks the server again.
  }
}

function setSignOutPending(client: QueryClient, pending: boolean): void {
  writePendingFlag(pending);
  client.setQueryData(SIGNOUT_PENDING_KEY, pending);
}

/**
 * Sign out. The person's data is hidden at once (purge), but "signed out" is only shown once the server confirmed
 * it revoked the session: a 2xx, or a 401 (there was no session to revoke). Any other outcome (no connection, a
 * timeout, a 5xx) leaves the tab in the pending state with a retry, and throws so the caller can tell.
 */
export async function signOut(client: QueryClient): Promise<void> {
  setSignOutPending(client, true);
  void client.cancelQueries({ queryKey: SESSION_KEY });
  purgeTenant(client);
  const result = await api.POST("/api/auth/signout");
  if (!result.response.ok && result.response.status !== 401) unwrapEmpty(result); // throws ApiError
  endSession(client, { deliberate: true });
  sendSessionSignal("signed-out");
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

  const pending = useQuery({
    queryKey: SIGNOUT_PENDING_KEY,
    queryFn: () => readPendingFlag(),
    initialData: readPendingFlag,
    staleTime: Number.POSITIVE_INFINITY,
  }).data;
  const retrySignOut = useMutation({ mutationFn: () => signOut(client) });

  // No session on the server while the sign-out was unconfirmed: nothing is left to revoke.
  useEffect(() => {
    if (pending && query.data === null) setSignOutPending(client, false);
  }, [client, pending, query.data]);

  // A tab reloaded while a sign-out was unconfirmed tries it again before anything else.
  const { mutate: retryMutate } = retrySignOut;
  useEffect(() => {
    if (readPendingFlag()) retryMutate();
  }, [retryMutate]);

  useEffect(() => {
    const offExpired = onSessionExpired(() => endSession(client));
    const offSignal = onSessionSignal((signal) => {
      // A BroadcastChannel also reaches this tab's own listener: a tab already signed out has nothing to end, and
      // must keep how it ended (a deliberate sign-out goes to /login without ?next=).
      if (signal === "signed-out") {
        if (client.getQueryData(SESSION_KEY) !== null)
          endSession(client, { deliberate: client.getQueryData(SIGNOUT_PENDING_KEY) === true });
      }
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
    if (pending && query.data === null) return { status: "signedOut", deliberate: true };
    if (pending)
      return { status: "signOutPending", retrying: retrySignOut.isPending, retry: () => retryMutate() };
    if (query.data !== undefined && query.data !== null) return { status: "signedIn", me: query.data };
    if (query.data === null)
      return { status: "signedOut", deliberate: client.getQueryData(SESSION_ENDED_KEY) === true };
    if (query.isError) return { status: "error", error: query.error, retry };
    return { status: "loading" };
  }, [client, pending, retrySignOut.isPending, retryMutate, query.data, query.isError, query.error, retry]);

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
            {t.shell.session.checking}
          </p>
        </FullPage>
      );
    case "error":
      return (
        <FullPage>
          <InlineNotice
            tone="danger"
            title={state.error instanceof ApiError ? t.shell.session.checkFailed : t.shell.session.offline}
            live="alert"
            actions={
              <Button type="button" variant="primary" icon="refresh" onClick={state.retry}>
                {t.shell.session.retry}
              </Button>
            }
          >
            {t.shell.session.retryLater}
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
    case "signOutPending":
      return (
        <FullPage>
          <SignOutPending retrying={state.retrying} retry={state.retry} />
        </FullPage>
      );
    case "signedIn":
      return <Outlet />;
  }
}

/** The server has not confirmed the sign-out: say so plainly, keep everything private hidden, offer to try again. */
function SignOutPending({ retrying, retry }: { readonly retrying: boolean; readonly retry: () => void }) {
  return (
    <InlineNotice
      tone="warning"
      title={t.shell.session.signOutUnconfirmed.title}
      live="alert"
      actions={
        <Button type="button" variant="primary" icon="refresh" busy={retrying} onClick={retry}>
          {t.shell.session.signOutUnconfirmed.retry}
        </Button>
      }
    >
      {t.shell.session.signOutUnconfirmed.body}
    </InlineNotice>
  );
}

/** Sign-in pages: someone already signed in has nothing to do here. */
export function RedirectIfSignedIn({ children }: { readonly children: ReactNode }) {
  const state = useSession();
  const [search] = [new URLSearchParams(useLocation().search)];
  if (state.status === "signOutPending") return <Navigate to="/app" replace />;
  if (state.status === "signedIn") return <Navigate to={safeNext(search.get("next"))} replace />;
  return <>{children}</>;
}
