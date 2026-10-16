/**
 * Network data is untrusted (rules/frontend.md section 5): the generated types describe the contract and validate
 * nothing. Every field the billing pages read is checked here; anything else is dropped or the whole answer is `null`.
 * Money stays the API's exact decimal string: the pages format it and never calculate with it.
 */
export const PACK_CODES = ["reports_1", "reports_5", "reports_10"] as const;
export type PackCode = (typeof PACK_CODES)[number];

export const PURCHASE_STATES = [
  "intent",
  "creating",
  "created",
  "creation_unknown",
  "failed",
  "paid",
  "granted",
  "review",
  "refunded",
] as const;
export type PurchaseState = (typeof PURCHASE_STATES)[number];

export interface Pack {
  readonly code: PackCode;
  readonly reports: number;
  /** Gross PLN as the API sends it (an exact decimal string). */
  readonly grossPln: string;
}

export interface Purchase {
  readonly id: string;
  readonly packCode: PackCode;
  readonly reports: number;
  readonly grossPln: string;
  readonly state: PurchaseState;
  readonly transactionId: string | null;
  readonly checkoutUrl: string | null;
  readonly createdAt: string;
  readonly grantedAt: string | null;
  readonly refundedAt: string | null;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const DECIMAL = /^\d{1,9}(\.\d{1,4})?$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** A Paddle transaction id (`txn_` and lowercase letters or digits). */
export const TRANSACTION_ID = /^txn_[a-z0-9]{10,40}$/;
const nullableText = (value: unknown): value is string | null => value === null || typeof value === "string";

const isPackCode = (value: unknown): value is PackCode => PACK_CODES.some((c) => c === value);
const isState = (value: unknown): value is PurchaseState => PURCHASE_STATES.some((s) => s === value);

export function readPack(value: unknown): Pack | null {
  if (!isRecord(value)) return null;
  const { code, reports, gross_pln: gross } = value;
  if (
    !isPackCode(code) ||
    typeof reports !== "number" ||
    !Number.isInteger(reports) ||
    reports < 1 ||
    typeof gross !== "string" ||
    !DECIMAL.test(gross)
  )
    return null;
  return { code, reports, grossPln: gross };
}

export interface Packs {
  readonly enabled: boolean;
  readonly packs: readonly Pack[];
}

export function readPacks(value: unknown): Packs | null {
  if (!isRecord(value) || typeof value["enabled"] !== "boolean" || !Array.isArray(value["packs"]))
    return null;
  const packs = (value["packs"] as unknown[]).map(readPack).filter((p): p is Pack => p !== null);
  // A catalog with entries that are all unreadable is a broken answer, not an empty shop.
  if (packs.length === 0 && (value["packs"] as unknown[]).length > 0) return null;
  return { enabled: value["enabled"], packs };
}

export function readPurchase(value: unknown): Purchase | null {
  if (!isRecord(value)) return null;
  const id = value["purchase_id"];
  const code = value["pack_code"];
  const state = value["state"];
  const reports = value["reports"];
  const gross = value["gross_pln"];
  const { transaction_id: txn, checkout_url: url, created_at: created } = value;
  const { granted_at: granted, refunded_at: refunded } = value;
  if (
    typeof id !== "string" ||
    !UUID.test(id) ||
    !isPackCode(code) ||
    !isState(state) ||
    typeof reports !== "number" ||
    !Number.isInteger(reports) ||
    typeof gross !== "string" ||
    !DECIMAL.test(gross) ||
    !nullableText(txn) ||
    !nullableText(url) ||
    typeof created !== "string" ||
    !nullableText(granted) ||
    !nullableText(refunded)
  )
    return null;
  return {
    id,
    packCode: code,
    reports,
    grossPln: gross,
    state,
    // A transaction id that is not one of Paddle's is never handed to Paddle.js.
    transactionId: typeof txn === "string" && TRANSACTION_ID.test(txn) ? txn : null,
    checkoutUrl: url,
    createdAt: created,
    grantedAt: granted,
    refundedAt: refunded,
  };
}

export function readPurchases(value: unknown): readonly Purchase[] | null {
  if (!isRecord(value) || !Array.isArray(value["purchases"])) return null;
  const raw = value["purchases"] as unknown[];
  const purchases = raw.map(readPurchase).filter((p): p is Purchase => p !== null);
  return purchases.length === 0 && raw.length > 0 ? null : purchases;
}

/** The invoice answer: a link to the document Paddle issued. Only an https address is ever opened. */
export function readInvoiceUrl(value: unknown): string | null {
  if (!isRecord(value) || typeof value["url"] !== "string") return null;
  try {
    const url = new URL(value["url"]);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

/** States after which nothing more will change by itself. */
export const SETTLED: ReadonlySet<PurchaseState> = new Set(["granted", "failed", "review", "refunded"]);
