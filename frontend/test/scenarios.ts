/**
 * The scenario registry: named, typed states of the API that screens are built and tested against (#268).
 * A scenario is plain data (routes and replies), so the same registry feeds Vitest (through MSW, test/handlers.ts),
 * the component catalog and the Playwright mocked lane. A request no route matches is a test failure, never an
 * empty success.
 *
 * Replies come from sanitised fixtures. The loaded states are built from the five distinct `succeeded` audits of the
 * capture so a list row, its detail and its progress stream tell one consistent story.
 */
import type { components } from "../api/schema.generated";
import { bodyOf, eventStreamText, fx, type Fixture, type HttpMethod } from "./fixtures";

type AuditOut = components["schemas"]["AuditOut"];
type AuditPage = components["schemas"]["AuditPage"];
type AuditSummary = components["schemas"]["AuditSummary"];
type MeDetail = components["schemas"]["MeDetailOut"];

export interface MockRequest {
  readonly method: HttpMethod;
  readonly url: URL;
  readonly params: Readonly<Record<string, string>>;
  readonly body: unknown;
}

export interface Reply {
  readonly status: number;
  readonly body?: unknown;
  readonly text?: string;
  readonly contentType?: string;
  readonly headers?: Readonly<Record<string, string>>;
  /** The request fails before any answer, like a dropped connection. */
  readonly networkError?: true;
}

export interface Route {
  /** `"GET /api/audits/{audit_id}"`: the OpenAPI operation key. */
  readonly operation: string;
  readonly reply: Reply | ((request: MockRequest) => Reply);
}

export interface Scenario {
  readonly name: string;
  readonly description: string;
  readonly routes: readonly Route[];
}

export function replyFrom(fixture: Fixture): Reply {
  if (fixture.events !== undefined) {
    return {
      status: fixture.status,
      text: eventStreamText(fixture.events),
      contentType: "text/event-stream",
      headers: fixture.headers,
    };
  }
  return {
    status: fixture.status,
    body: fixture.body,
    contentType: fixture.content_type,
    headers: fixture.headers,
  };
}

const fromFixture = (operation: string, scenario: string): Route => ({
  operation,
  reply: replyFrom(fx(operation, scenario)),
});

// ------------------------------------------------------------------------------------------------ audits
export const SUCCEEDED_SCENARIOS = ["warszawa", "krakow", "lodz", "gdansk", "torun"].map(
  (c) => `succeeded_${c}`,
);

/** Spread creation times so ordering is visible: audit 0 is the newest. */
function stamped(audit: AuditOut, index: number): AuditOut {
  const base = Date.parse("2026-10-01T10:00:00Z") - index * 3_600_000;
  const at = (offsetS: number) => new Date(base + offsetS * 1000).toISOString().replace(".000Z", "Z");
  return { ...audit, created_at: at(0), started_at: at(2), finished_at: at(38) };
}

export function summaryOf(audit: AuditOut): AuditSummary {
  return {
    audit_id: audit.audit_id,
    otodom_id: audit.otodom_id,
    status: audit.status,
    error_code: audit.error_code,
    created_at: audit.created_at,
    finished_at: audit.finished_at,
    grade: audit.grade,
    asking_price_pln: audit.asking_price_pln,
    max_bid_pln: audit.max_bid_pln,
  };
}

/** Five distinct finished audits, newest first, each with its progress stream. */
export const SUCCEEDED_AUDITS: readonly AuditOut[] = SUCCEEDED_SCENARIOS.map((name, i) =>
  stamped(bodyOf<AuditOut>(fx("GET /api/audits/{audit_id}", name)), i),
);

function page(audits: readonly AuditOut[]): AuditPage {
  return { items: audits.map(summaryOf), next_cursor: null };
}

function auditRoutes(audits: readonly AuditOut[]): Route[] {
  return [
    { operation: "GET /api/audits", reply: { status: 200, body: page(audits) } },
    {
      operation: "GET /api/audits/{audit_id}",
      reply: (request) => {
        const found = audits.find((a) => a.audit_id === request.params["audit_id"]);
        return found === undefined
          ? replyFrom(fx("GET /api/audits/{audit_id}", "unknown_audit"))
          : { status: 200, body: found };
      },
    },
    fromFixture("GET /api/audits/{audit_id}/events", "success_transcript"),
  ];
}

// -------------------------------------------------------------------------------------------------- base
const me = (scenario: string): Route => fromFixture("GET /api/me", scenario);

function withMe(patch: (body: MeDetail) => MeDetail, scenario = "with_credits_and_flags"): Route {
  const body = patch(bodyOf<MeDetail>(fx("GET /api/me", scenario)));
  return { operation: "GET /api/me", reply: { status: 200, body } };
}

const PACKS = fromFixture("GET /api/billing/packs", "three_packs");
const SAVED_EMPTY = fromFixture("GET /api/saved", "empty");
export const EMPTY_PAGE: Route = {
  operation: "GET /api/audits",
  reply: { status: 200, body: { items: [], next_cursor: null } satisfies AuditPage },
};

/** Routes any signed-in screen needs. A scenario replaces a route by repeating its operation. */
const SIGNED_IN: readonly Route[] = [me("with_credits_and_flags"), PACKS, SAVED_EMPTY];

function scenario(
  name: string,
  description: string,
  routes: readonly Route[],
  base: readonly Route[] = SIGNED_IN,
): Scenario {
  const replaced = new Set(routes.map((r) => r.operation));
  return { name, description, routes: [...routes, ...base.filter((r) => !replaced.has(r.operation))] };
}

export const SCENARIOS = {
  firstVisit: scenario(
    "firstVisit",
    "Nobody is signed in: every session route answers 401.",
    [me("no_session")],
    [],
  ),
  empty: scenario("empty", "Signed in with credits and no analyses yet.", [EMPTY_PAGE]),
  loaded: scenario("loaded", "Five distinct finished analyses, newest first.", auditRoutes(SUCCEEDED_AUDITS)),
  pending: scenario("pending", "An analysis was accepted and has not run yet.", [
    EMPTY_PAGE,
    fromFixture("GET /api/audits/{audit_id}", "queued_not_yet_run"),
    fromFixture("POST /api/audits", "accepted"),
  ]),
  degraded: scenario("degraded", "A finished analysis without photo assessment.", [
    fromFixture("GET /api/audits/{audit_id}", "succeeded_degraded"),
  ]),
  rejectedRent: scenario("rejectedRent", "The listing is a rental: rejected, no charge.", [
    fromFixture("GET /api/audits/{audit_id}", "rejected_rent_is_not_a_deal"),
    fromFixture("GET /api/audits/{audit_id}/events", "rejected_transcript"),
  ]),
  rejectedFractional: scenario("rejectedFractional", "A fractional share: rejected, no charge.", [
    fromFixture("GET /api/audits/{audit_id}", "rejected_fractional_ownership"),
  ]),
  failedUpstream: scenario("failedUpstream", "Otodom blocked the fetch: failed, charge released.", [
    fromFixture("GET /api/audits/{audit_id}", "failed_upstream_blocked"),
    fromFixture("GET /api/audits/{audit_id}/events", "failure_transcript"),
  ]),
  failedInput: scenario("failedInput", "The listing is gone: failed input, charge released.", [
    fromFixture("GET /api/audits/{audit_id}", "failed_input_listing_gone"),
  ]),
  insufficientCredits: scenario("insufficientCredits", "No reports left: submitting answers 402.", [
    withMe((m) => ({ ...m, credit_balance: 0 })),
    fromFixture("POST /api/audits", "no_credits"),
  ]),
  unverified: scenario("unverified", "Signed in, but the e-mail address is not confirmed yet.", [
    withMe((m) => ({ ...m, email_verified: false })),
    EMPTY_PAGE,
    fromFixture("POST /api/auth/register/resend", "accepted"),
  ]),
  breakerOpen: scenario("breakerOpen", "Otodom is rate-limiting us: the breaker is open.", [
    fromFixture("GET /api/me", "upstream_breaker_open"),
  ]),
  billingDisabled: scenario("billingDisabled", "Purchases are not enabled yet.", [
    fromFixture("GET /api/billing/packs", "billing_disabled"),
    fromFixture("POST /api/billing/checkout", "billing_disabled"),
  ]),
  sessionExpired: scenario("sessionExpired", "The session ended: every session route answers 401.", [
    me("no_session"),
    fromFixture("GET /api/audits", "no_session"),
  ]),
  offline: scenario(
    "offline",
    "The network is down: every request fails before any answer.",
    ["GET /api/me", "GET /api/audits", "GET /api/billing/packs", "GET /api/saved"].map((operation) => ({
      operation,
      reply: { status: 0, networkError: true },
    })),
    [],
  ),
  reconnecting: scenario("reconnecting", "The progress stream is interrupted.", [
    ...auditRoutes(SUCCEEDED_AUDITS).filter((r) => r.operation !== "GET /api/audits/{audit_id}/events"),
    { operation: "GET /api/audits/{audit_id}/events", reply: { status: 0, networkError: true } },
  ]),
} as const satisfies Record<string, Scenario>;

export type ScenarioName = keyof typeof SCENARIOS;
export const SCENARIO_NAMES = Object.keys(SCENARIOS) as ScenarioName[];

// ----------------------------------------------------------------------------------------------- matching
const PARAM = /\{([a-z_]+)\}/g;

/** `/api/audits/{audit_id}` -> a matcher that also returns the path parameters. */
export function compileTemplate(template: string): (path: string) => Record<string, string> | null {
  const names: string[] = [];
  const pattern = new RegExp(
    `^${template.replace(PARAM, (_, name: string) => (names.push(name), "([^/]+)"))}$`,
  );
  return (path) => {
    const match = pattern.exec(path);
    if (match === null) return null;
    return Object.fromEntries(names.map((name, i) => [name, decodeURIComponent(match[i + 1] ?? "")]));
  };
}

export interface Matched {
  readonly route: Route;
  readonly params: Record<string, string>;
}

/** The scenario's route for a request, or null: the caller turns null into a loud failure. */
export function matchRoute(scenario: Scenario, method: string, path: string): Matched | null {
  for (const route of scenario.routes) {
    const [routeMethod, template] = route.operation.split(" ", 2);
    if (routeMethod !== method || template === undefined) continue;
    const params = compileTemplate(template)(path);
    if (params !== null) return { route, params };
  }
  return null;
}

export function resolveReply(matched: Matched, request: MockRequest): Reply {
  const { reply } = matched.route;
  return typeof reply === "function" ? reply(request) : reply;
}

// ------------------------------------------------------------------------------------------- auth flow
const wrongPassword = "wrong-password-1";
const WEAK = "password1234";

export interface AuthFlow extends Scenario {
  /** Mutable: a successful sign-in flips it, so a following GET /api/me answers like the real API would. */
  readonly state: { signedIn: boolean };
  readonly calls: string[];
}

/**
 * The sign-in surface as one stateful scenario: GET /api/me answers 401 until a sign-in succeeds, then the
 * signed-in profile, and 401 again after sign-out. Tokens and passwords steer the answer: a token starting with
 * `invalid` is refused, `exists` is an account that already exists, `wrong-password-1` is a bad password and
 * `password1234` a weak one. Built fresh per test (the state is the point), from the same fixtures as the others.
 */
export function createAuthFlow(overrides: Record<string, Reply> = {}): AuthFlow {
  const state = { signedIn: false };
  const calls: string[] = [];
  const me = bodyOf<MeDetail>(fx("GET /api/me", "with_credits_and_flags"));
  const reply = (operation: string, scenarioName: string): Reply =>
    overrides[operation] ?? replyFrom(fx(operation, scenarioName));
  const signIn = (operation: string, scenarioName: string): Reply => {
    state.signedIn = true;
    return reply(operation, scenarioName);
  };
  const tokenOf = (request: MockRequest): string => {
    const token = (request.body as { token?: unknown } | null)?.token;
    return typeof token === "string" ? token : "";
  };
  const routes: Route[] = [
    {
      operation: "GET /api/me",
      reply: () => (state.signedIn ? { status: 200, body: me } : replyFrom(fx("GET /api/me", "no_session"))),
    },
    {
      operation: "POST /api/auth/login",
      reply: (request) => {
        calls.push("login");
        const password = (request.body as { password?: string } | null)?.password;
        if (overrides["POST /api/auth/login"] !== undefined) return overrides["POST /api/auth/login"];
        return password === wrongPassword
          ? replyFrom(fx("POST /api/auth/login", "wrong_password"))
          : signIn("POST /api/auth/login", "signed_in");
      },
    },
    {
      operation: "POST /api/auth/google",
      reply: (request) => {
        calls.push("google");
        const credential = (request.body as { credential?: string } | null)?.credential ?? "";
        if (credential.includes("unverified"))
          return replyFrom(fx("POST /api/auth/google", "email_unverified"));
        if (credential.includes("confirm"))
          return replyFrom(fx("POST /api/auth/google", "email_confirmation_required"));
        return signIn("POST /api/auth/google", "new_account");
      },
    },
    {
      operation: "POST /api/auth/email/start",
      reply: () => (calls.push("email-start"), reply("POST /api/auth/email/start", "accepted")),
    },
    {
      operation: "POST /api/auth/email/verify",
      reply: (request) => {
        calls.push(`email-verify:${tokenOf(request)}`);
        return tokenOf(request).startsWith("invalid")
          ? replyFrom(fx("POST /api/auth/email/verify", "link_invalid"))
          : signIn("POST /api/auth/email/verify", "signed_in");
      },
    },
    {
      operation: "POST /api/auth/register",
      reply: (request) => {
        calls.push("register");
        const password = (request.body as { password?: string } | null)?.password;
        return password === WEAK
          ? replyFrom(fx("POST /api/auth/register", "weak_password"))
          : reply("POST /api/auth/register", "accepted");
      },
    },
    {
      operation: "POST /api/auth/register/resend",
      reply: () => (calls.push("register-resend"), reply("POST /api/auth/register/resend", "accepted")),
    },
    {
      operation: "POST /api/auth/register/verify",
      reply: (request) => {
        const token = tokenOf(request);
        calls.push(`register-verify:${token}`);
        if (token.startsWith("invalid"))
          return replyFrom(fx("POST /api/auth/register/verify", "link_invalid"));
        if (token.startsWith("exists"))
          return replyFrom(fx("POST /api/auth/register/verify", "account_exists"));
        return signIn("POST /api/auth/register/verify", "account_created");
      },
    },
    {
      operation: "POST /api/auth/password/forgot",
      reply: () => (calls.push("forgot"), reply("POST /api/auth/password/forgot", "accepted")),
    },
    {
      operation: "POST /api/auth/password/reset",
      reply: (request) => {
        const token = tokenOf(request);
        calls.push(`reset:${token}`);
        const password = (request.body as { password?: string } | null)?.password;
        if (token.startsWith("invalid"))
          return replyFrom(fx("POST /api/auth/password/reset", "link_invalid"));
        return password === WEAK
          ? replyFrom(fx("POST /api/auth/password/reset", "weak_password"))
          : reply("POST /api/auth/password/reset", "password_set");
      },
    },
    {
      operation: "POST /api/auth/signout",
      reply: () => {
        calls.push("signout");
        state.signedIn = false;
        return reply("POST /api/auth/signout", "signed_out");
      },
    },
    SAVED_EMPTY,
    PACKS,
    EMPTY_PAGE,
  ];
  return {
    name: "authFlow",
    description: "Sign-in methods against a stateful session.",
    routes,
    state,
    calls,
  };
}
