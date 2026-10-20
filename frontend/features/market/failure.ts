import { ApiError, TransportError } from "../../api/errors";
import { describeProblem, describeTransport } from "../../api/problems";

/** The Polish title and detail for whatever a request threw: a problem code, or a transport failure. */
export function failureOf(error: unknown) {
  return error instanceof ApiError && error.code !== null
    ? describeProblem(error.code, { requestId: error.requestId })
    : describeTransport(error instanceof TransportError ? error.kind : "invalid-response");
}

export const isNotFound = (error: unknown): boolean => error instanceof ApiError && error.status === 404;

/** The free tier's closed place: 403 `FEATURE_NOT_IN_PLAN`, shown as an offer to unlock, never as a failure. */
export const isClosed = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 403 && error.code === "FEATURE_NOT_IN_PLAN";
