/** One saved listing, as the pages show it. */
export interface SavedItem {
  readonly otodomId: string;
  readonly note: string | null;
  /** The person's newest analysis of this listing, when the API names one. */
  readonly latestAuditId: string | null;
  readonly createdAt: string;
}

/** The API's own pattern for an Otodom id in a path (`^[A-Za-z0-9]{4,16}$`). */
const OTODOM_ID = /^[A-Za-z0-9]{4,16}$/;
const AUDIT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Network data is untrusted (rules/frontend.md section 5). A row missing a field the pages read, with an id that is
 * not an Otodom id, or with a link target that is not an audit id, is dropped; an answer that is not a list, or whose
 * rows are all malformed, is `null` (a controlled failure, never an exception while rendering).
 */
export function readSaved(value: unknown): readonly SavedItem[] | null {
  if (!Array.isArray(value)) return null;
  const items: SavedItem[] = [];
  for (const entry of value as unknown[]) {
    if (typeof entry !== "object" || entry === null) continue;
    const row = entry as Record<string, unknown>;
    const { otodom_id: id, note, latest_audit_id: audit, created_at: created } = row;
    if (
      typeof id === "string" &&
      OTODOM_ID.test(id) &&
      (note === null || typeof note === "string") &&
      (audit === null || (typeof audit === "string" && AUDIT_ID.test(audit))) &&
      typeof created === "string"
    ) {
      items.push({ otodomId: id, note, latestAuditId: audit, createdAt: created });
    }
  }
  return items.length === 0 && value.length > 0 ? null : items;
}

/** The API stores at most this many characters of a note (`SavedPut.note`). */
export const NOTE_MAX = 2000;

/** Length as the server counts it: characters (code points), not UTF-16 units. */
export const noteLength = (note: string): number => [...note].length;
