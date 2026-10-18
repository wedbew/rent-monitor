/** One signed-in browser, as the settings page shows it. */
export interface SessionRow {
  readonly id: number;
  readonly current: boolean;
  /** `created_hint` in the API: the last time the session was seen. */
  readonly lastSeen: string;
  readonly expiresAt: string;
  readonly userAgent: string | null;
  readonly ip: string | null;
}

const isText = (value: unknown): value is string => typeof value === "string";
const isNullableText = (value: unknown): value is string | null =>
  value === null || typeof value === "string";

/**
 * Network data is untrusted (rules/frontend.md section 5): the generated type describes the contract and validates
 * nothing. A row that does not have every field the page reads is dropped; an answer that is not a list, or whose
 * rows are all malformed, is `null` (the page shows a controlled failure, never throws while rendering).
 */
export function readSessions(value: unknown): readonly SessionRow[] | null {
  if (!Array.isArray(value)) return null;
  const rows: SessionRow[] = [];
  for (const item of value as unknown[]) {
    if (typeof item !== "object" || item === null) continue;
    const row = item as Record<string, unknown>;
    const { id, current, created_hint: lastSeen, expires_at: expiresAt } = row;
    const { user_agent: userAgent, ip } = row;
    if (
      typeof id === "number" &&
      typeof current === "boolean" &&
      isText(lastSeen) &&
      isText(expiresAt) &&
      isNullableText(userAgent) &&
      isNullableText(ip)
    ) {
      rows.push({ id, current, lastSeen, expiresAt, userAgent, ip });
    }
  }
  return rows.length === 0 && value.length > 0 ? null : rows;
}

/** The current browser first, then the most recently seen. Never mutates its input. */
export function orderSessions(rows: readonly SessionRow[]): readonly SessionRow[] {
  return [...rows].sort(
    (a, b) => Number(b.current) - Number(a.current) || Date.parse(b.lastSeen) - Date.parse(a.lastSeen),
  );
}
