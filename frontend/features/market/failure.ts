import { ApiError, TransportError } from "../../api/errors";
import { describeProblem, describeTransport } from "../../api/problems";

/** The Polish title and detail for whatever a request threw: a problem code, or a transport failure. */
export function failureOf(error: unknown) {
  return error instanceof ApiError && error.code !== null
    ? describeProblem(error.code, { requestId: error.requestId })
    : describeTransport(error instanceof TransportError ? error.kind : "invalid-response");
}

export const isNotFound = (error: unknown): boolean => error instanceof ApiError && error.status === 404;
