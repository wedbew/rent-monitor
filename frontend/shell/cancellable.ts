import { TransportError } from "../api/errors";
import { isCurrentSession, registerTenantCleanup, sessionGeneration } from "./tenant";

/**
 * Run a request that must stop when the session ends (sign-out here or in another tab, expiry, deletion): its abort
 * is a tenant cleanup for as long as it runs, so a request of the previous person is cancelled before the next
 * person renders (rules/frontend.md section 3: every mutation has an explicit cancel path).
 *
 * The guarantee does not depend on `run` honouring the signal: once the session ended the caller gets a typed
 * `TransportError("aborted")`, never a late result (success or failure) of the previous person's work. Aborting
 * does not undo a server mutation that already happened; callers say "unknown", not "failed", for it.
 */
export async function whileSignedIn<T>(run: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const generation = sessionGeneration();
  const controller = new AbortController();
  const cancelled = () => new TransportError("aborted");
  let onAbort: (() => void) | undefined;
  const ended = new Promise<never>((_resolve, reject) => {
    onAbort = () => reject(cancelled());
    controller.signal.addEventListener("abort", onAbort, { once: true });
  });
  const release = registerTenantCleanup(() => controller.abort());
  // A late answer of a session that moved on is dropped, and the request still running for it is stopped.
  const late = () => {
    if (controller.signal.aborted) return true;
    if (isCurrentSession(generation)) return false;
    controller.abort();
    return true;
  };
  try {
    // `run` may throw before returning a promise; that failure goes through the same path, so `finally` still releases.
    const work = new Promise<T>((resolve) => resolve(run(controller.signal)));
    work.catch(() => undefined); // a rejection that arrives after the race was settled is not an unhandled one
    const result = await Promise.race([work, ended]);
    if (late()) throw cancelled();
    return result;
  } catch (error) {
    if (late()) throw cancelled();
    throw error;
  } finally {
    release();
    if (onAbort !== undefined) controller.signal.removeEventListener("abort", onAbort);
  }
}
