/**
 * Everything that belongs to the signed-in person and lives outside the query cache registers a cleanup here: an
 * open progress stream, object URLs of previewed photos, a pending timer. The session boundary runs them all when
 * the session ends (sign-out here or in another tab, expiry, account deletion), so nothing of one person's
 * state outlives them (docs/FRONTEND-PLAN.md section 6).
 */
type Cleanup = () => void;
const cleanups = new Set<Cleanup>();

export function registerTenantCleanup(cleanup: Cleanup): () => void {
  cleanups.add(cleanup);
  return () => {
    cleanups.delete(cleanup);
  };
}

export function runTenantCleanups(): void {
  for (const cleanup of [...cleanups]) {
    try {
      cleanup();
    } catch {
      // One failing cleanup must not stop the others: the rest of the state still has to go.
    }
  }
}
