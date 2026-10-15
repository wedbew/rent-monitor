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

/** Narrow an unknown JSON value to a Problem; anything else is not trusted as one. */
export function asProblem(value: unknown): Problem | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  if (!isProblemCode(record["code"]) || typeof record["status"] !== "number") return null;
  if (typeof record["title"] !== "string" || typeof record["instance"] !== "string") return null;
  return value as Problem;
}
