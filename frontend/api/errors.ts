import type { Problem, ProblemCode, TransportFailure } from "./problems";
import { isProblemCode } from "./problems";

/** The API answered with an error status. `problem` is its RFC 9457 body when it sent one we recognise. */
export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem | null;
  readonly retryAfterS: number | null;

  constructor(status: number, problem: Problem | null, retryAfterS: number | null = null) {
    super(problem ? `${problem.code}: ${problem.title}` : `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
    this.retryAfterS = retryAfterS;
  }

  get code(): ProblemCode | null {
    return this.problem?.code ?? null;
  }

  get requestId(): string | null {
    return this.problem?.request_id ?? null;
  }
}

/** The request never produced an API answer: no connection, a timeout, an abort, or a body we cannot read. */
export class TransportError extends Error {
  readonly kind: TransportFailure;

  constructor(kind: TransportFailure, options?: ErrorOptions) {
    super(kind, options);
    this.name = "TransportError";
    this.kind = kind;
  }
}

const isNullableString = (value: unknown) =>
  value === undefined || value === null || typeof value === "string";

/** One entry of a 422's `errors`: FastAPI's `loc` mixes field names and list indexes. */
function isProblemField(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return (
    Array.isArray(item["loc"]) &&
    item["loc"].every((part) => typeof part === "string" || typeof part === "number") &&
    typeof item["msg"] === "string"
  );
}

/**
 * Narrow an unknown JSON value to a Problem. Every field the app reads is checked (code, status, title, instance,
 * detail, request_id and each `errors` entry); anything else is not trusted as one, so a malformed body becomes
 * "unexpected response" copy instead of an exception while an error is being shown (audit F11).
 */
export function asProblem(value: unknown): Problem | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (!isProblemCode(record["code"]) || typeof record["status"] !== "number") return null;
  if (typeof record["title"] !== "string" || typeof record["instance"] !== "string") return null;
  const detail = record["detail"];
  const requestId = record["request_id"];
  if (!isNullableString(detail) || !isNullableString(requestId)) return null;
  const errors = record["errors"];
  if (errors !== undefined && errors !== null && !(Array.isArray(errors) && errors.every(isProblemField)))
    return null;
  return {
    ...record,
    detail: detail ?? null,
    request_id: requestId ?? null,
    errors: (errors as Problem["errors"] | undefined) ?? null,
  } as Problem;
}

/**
 * A failure after which the request MAY have been applied: the connection dropped, it timed out, the answer could not
 * be read, or the server failed after starting. A refusal (4xx) and an abort by this app are not ambiguous.
 */
export function isAmbiguousFailure(error: unknown): boolean {
  if (error instanceof TransportError) return error.kind !== "aborted";
  return error instanceof ApiError && error.status >= 500;
}
