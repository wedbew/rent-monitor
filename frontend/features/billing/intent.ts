import { PACK_CODES, type PackCode } from "./guards";

/**
 * The purchase the person is in the middle of starting: the pack and the `Idempotency-Key` of the request. It is saved
 * BEFORE the request is sent and removed when the server gave a definite answer, so a reload or a navigation after a
 * lost answer can still ask the server about exactly that request (`GET /api/billing/purchases?request_key=`), which
 * is the only proof of what happened. It holds a pack code and a random id: no personal data, no price.
 *
 * `sessionStorage` is a per-tab convenience that can be empty or throw (private windows, blocked storage): then the
 * intent is simply not remembered, and the next click starts a new order, which is harmless (an unpaid order). It is
 * keyed by the user id and cleared when the session ends.
 */
export interface Intent {
  readonly pack: PackCode;
  readonly key: string;
  /**
   * The server said no order with this key exists. Not proof the request will never arrive, so the same pack is
   * still bought with this key (a late arrival then answers with that one order); another pack may be chosen freely.
   */
  readonly parked?: boolean;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const storageKey = (userId: string) => `rm:checkout-intent:${userId}`;

export function loadIntent(userId: string): Intent | null {
  try {
    const raw = window.sessionStorage.getItem(storageKey(userId));
    if (raw === null) return null;
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null) return null;
    const { pack, key, parked } = value as Record<string, unknown>;
    if (typeof key !== "string" || !UUID.test(key)) return null;
    const known = PACK_CODES.find((code) => code === pack);
    if (known === undefined) return null;
    return parked === true ? { pack: known, key, parked: true } : { pack: known, key };
  } catch {
    return null;
  }
}

export function saveIntent(userId: string, intent: Intent): void {
  try {
    window.sessionStorage.setItem(storageKey(userId), JSON.stringify(intent));
  } catch {
    // Storage unavailable: the intent lives in memory only.
  }
}

export function clearIntent(userId: string): void {
  try {
    window.sessionStorage.removeItem(storageKey(userId));
  } catch {
    // Nothing stored, nothing to clear.
  }
}
