import { t } from "../i18n";
import type { components } from "./schema.generated";

export type Problem = components["schemas"]["Problem"];
export type ProblemCode = components["schemas"]["ProblemCode"];

/** What the screen should offer next. The page decides how to render it; this says which one applies. */
export type ProblemAction =
  | "none"
  | "retry"
  | "waitAndRetry"
  | "signIn"
  | "buyReports"
  | "verifyEmail"
  | "fixInput"
  | "openAnalysis"
  | "contactSupport"
  | "useEmailLink"
  | "requestNewLink"
  | "reload"
  | "goBack";

export interface ProblemCopy {
  readonly title: string;
  readonly detail: string;
  readonly action: ProblemAction;
}

/** What each problem code offers next: behaviour, not copy (the words are in the catalog). */
export const PROBLEM_ACTIONS = {
  INVALID_LISTING_REF: "fixInput",
  QUOTA_EXHAUSTED: "buyReports",
  AUDIT_IN_PROGRESS: "openAnalysis",
  RENT_NOT_DEAL: "none",
  FRACTIONAL_OWNERSHIP: "none",
  LISTING_GONE: "none",
  UPSTREAM_BLOCKED: "waitAndRetry",
  UPSTREAM_SCHEMA_DRIFT: "contactSupport",
  VISION_UNAVAILABLE: "none",
  CONTEXT_UNAVAILABLE: "none",
  INTERNAL: "retry",
  VALIDATION_ERROR: "fixInput",
  NOT_FOUND: "goBack",
  HTTP_ERROR: "retry",
  NOT_READY: "waitAndRetry",
  INVALID_GOOGLE_TOKEN: "retry",
  GOOGLE_EMAIL_UNVERIFIED: "useEmailLink",
  EMAIL_CONFIRMATION_REQUIRED: "useEmailLink",
  MAGIC_LINK_INVALID: "requestNewLink",
  INVALID_CREDENTIALS: "fixInput",
  WEAK_PASSWORD: "fixInput",
  AUTH_TOKEN_INVALID: "requestNewLink",
  ACCOUNT_EXISTS: "signIn",
  BILLING_UNAVAILABLE: "none",
  IDEMPOTENCY_CONFLICT: "reload",
  BILLING_PROVIDER_ERROR: "retry",
  INVALID_WEBHOOK_SIGNATURE: "contactSupport",
  BILLING_HOLD: "contactSupport",
  PURCHASE_NOT_REFUNDABLE: "none",
  REFUND_NEEDS_REVIEW: "contactSupport",
  EMAIL_NOT_VERIFIED: "verifyEmail",
  FEATURE_NOT_IN_PLAN: "none",
  ADMIN_ONLY: "goBack",
  ALREADY_SUBSCRIBED: "none",
  INVALID_STRIPE_SIGNATURE: "contactSupport",
  UNAUTHENTICATED: "signIn",
  RATE_LIMITED: "waitAndRetry",
  ORIGIN_NOT_ALLOWED: "reload",
  CONFIRMATION_MISMATCH: "fixInput",
  CREDIT_BELOW_ZERO: "none",
  SAVED_LIMIT_REACHED: "none",
} as const satisfies Record<ProblemCode, ProblemAction>;

/**
 * Polish copy for every stable problem code: the words from the catalog (i18n/pl.ts `problems.codes`), the next
 * action from `PROBLEM_ACTIONS`. `satisfies Record<ProblemCode, ...>` makes a new code in the API a compile error
 * here (after `pnpm generate:api`), and `problems.test.ts` reads the enum from docs/openapi.json so the table cannot
 * lag the committed schema either. Where a failure releases the reserved credit the text says so.
 */
export const PROBLEM_COPY = Object.fromEntries(
  (Object.keys(PROBLEM_ACTIONS) as ProblemCode[]).map((code) => [
    code,
    { ...t.problems.codes[code], action: PROBLEM_ACTIONS[code] },
  ]),
) as Record<ProblemCode, ProblemCopy>;

/** Failures that never reach the API's problem format. */
export type TransportFailure = "network" | "timeout" | "aborted" | "invalid-response";

const TRANSPORT_ACTIONS = {
  network: "retry",
  timeout: "retry",
  aborted: "none",
  "invalid-response": "reload",
} as const satisfies Record<TransportFailure, ProblemAction>;

export const TRANSPORT_COPY = Object.fromEntries(
  (Object.keys(TRANSPORT_ACTIONS) as TransportFailure[]).map((kind) => [
    kind,
    { ...t.problems.transport[kind], action: TRANSPORT_ACTIONS[kind] },
  ]),
) as Record<TransportFailure, ProblemCopy>;

export interface DescribedProblem extends ProblemCopy {
  /** Kept so support can find the request in the logs; shown small, never as the headline. */
  readonly requestId: string | null;
  readonly retryAfterS: number | null;
}

export function isProblemCode(value: unknown): value is ProblemCode {
  return typeof value === "string" && Object.hasOwn(PROBLEM_COPY, value);
}

export function describeProblem(
  code: ProblemCode,
  extra: { requestId?: string | null; retryAfterS?: number | null } = {},
): DescribedProblem {
  return {
    ...PROBLEM_COPY[code],
    requestId: extra.requestId ?? null,
    retryAfterS: extra.retryAfterS ?? null,
  };
}

export function describeTransport(kind: TransportFailure): DescribedProblem {
  return { ...TRANSPORT_COPY[kind], requestId: null, retryAfterS: null };
}
