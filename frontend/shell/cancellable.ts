import { registerTenantCleanup } from "./tenant";

/**
 * Run a request that must stop when the session ends (sign-out here or in another tab, expiry, deletion): its abort
 * is a tenant cleanup for as long as it runs, so a request of the previous person is cancelled before the next
 * person renders (rules/frontend.md section 3: every mutation has an explicit cancel path).
 */
export async function whileSignedIn<T>(run: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const controller = new AbortController();
  const release = registerTenantCleanup(() => controller.abort());
  try {
    return await run(controller.signal);
  } finally {
    release();
  }
}
