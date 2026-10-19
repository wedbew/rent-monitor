/**
 * Reads the persisted vision evidence (`vision.equipment`, `vision.floor_plan_text`, `vision.notes`, RM-387) from an
 * untrusted report value. Network data is checked field by field before it is shown (`rules/frontend.md` §5): a
 * malformed field is dropped or reported as unreadable, and nothing here throws. Display only: no number is derived.
 */

export type EvidenceProvenance = "photo" | "floor_plan" | "unattributed";
export type EvidenceSaleStatus = "included" | "visible_only" | "unknown";

export interface EquipmentRow {
  readonly item: string;
  /** Zero-based position in the selected media list (photos in listing order, then plans); null when unknown. */
  readonly mediaOrdinal: number | null;
  readonly provenance: EvidenceProvenance;
  readonly saleStatus: EvidenceSaleStatus;
  /** The model's confidence as the engine wrote it ("0.85"), or null when it is not a readable ratio. */
  readonly confidence: string | null;
}

/**
 * What the report can say about the vision evidence, one state at a time:
 * - `not-run`: no vision answer was used and the audit was not degraded (nothing was attempted);
 * - `failed`: no vision answer and the audit is `succeeded_degraded` (the analysis of photos did not complete);
 * - `older`: the vision record predates the evidence fields (no `equipment`, `floor_plan_text` or `notes` key);
 * - `unreadable`: the vision value is not an object the page can read;
 * - `empty`: the evidence fields exist but hold nothing to show;
 * - `ready`: at least one readable item, text or note.
 */
export type VisionEvidence =
  | { readonly kind: "not-run" }
  | { readonly kind: "failed" }
  | { readonly kind: "older" }
  | { readonly kind: "unreadable" }
  | { readonly kind: "empty" }
  | {
      readonly kind: "ready";
      readonly equipment: readonly EquipmentRow[];
      /** Items that were present but malformed; counted, never shown. */
      readonly skipped: number;
      readonly floorPlanText: string | null;
      readonly notes: string | null;
    };

const PROVENANCE: readonly EvidenceProvenance[] = ["photo", "floor_plan", "unattributed"];
const SALE_STATUS: readonly EvidenceSaleStatus[] = ["included", "visible_only", "unknown"];
const MAX_EQUIPMENT = 40;
const MAX_TEXT = 4000;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** Drops control characters (kept: line breaks and tabs). Rendering is plain text in any case. */
export function stripControls(value: string): string {
  return [...value].filter((ch) => ch === "\n" || ch === "\t" || !/\p{Cc}/u.test(ch)).join("");
}

function readText(value: unknown, maxLength: number): string | null {
  if (typeof value !== "string") return null;
  const cleaned = stripControls(value).trim();
  if (cleaned === "" || cleaned.length > maxLength) return null;
  return cleaned;
}

function readRatio(value: unknown): string | null {
  if (typeof value !== "string" || !/^(0|1)(\.\d{1,6})?$/.test(value.trim())) return null;
  return value.trim();
}

function readEquipmentRow(value: unknown): EquipmentRow | null {
  if (!isRecord(value)) return null;
  const item = readText(value["item"], 80);
  if (item === null) return null;
  const ordinal = value["media_ordinal"];
  const mediaOrdinal =
    typeof ordinal === "number" && Number.isInteger(ordinal) && ordinal >= 0 ? ordinal : null;
  const provenance = PROVENANCE.find((p) => p === value["provenance"]) ?? "unattributed";
  const saleStatus = SALE_STATUS.find((s) => s === value["sale_status"]) ?? "unknown";
  return { item, mediaOrdinal, provenance, saleStatus, confidence: readRatio(value["confidence"]) };
}

/** Reads the vision value of a report. `hasOwn` keys decide between "older" and "empty". */
export function readVisionEvidence(vision: unknown, degraded: boolean): VisionEvidence {
  if (vision === null || vision === undefined) return degraded ? { kind: "failed" } : { kind: "not-run" };
  if (!isRecord(vision)) return { kind: "unreadable" };
  const hasEquipment = "equipment" in vision;
  const hasText = "floor_plan_text" in vision;
  const hasNotes = "notes" in vision;
  if (!hasEquipment && !hasText && !hasNotes) return { kind: "older" };

  const rawEquipment = hasEquipment ? vision["equipment"] : [];
  const list = Array.isArray(rawEquipment) ? rawEquipment.slice(0, MAX_EQUIPMENT) : [];
  const equipment: EquipmentRow[] = [];
  let skipped = Array.isArray(rawEquipment) ? Math.max(0, rawEquipment.length - MAX_EQUIPMENT) : 0;
  for (const raw of list) {
    const row = readEquipmentRow(raw);
    if (row === null) skipped += 1;
    else equipment.push(row);
  }
  if (!Array.isArray(rawEquipment) && hasEquipment && rawEquipment !== null) skipped += 1;

  const floorPlanText = hasText ? readText(vision["floor_plan_text"], MAX_TEXT) : null;
  const notes = hasNotes ? readText(vision["notes"], 1000) : null;
  if (equipment.length === 0 && floorPlanText === null && notes === null && skipped === 0)
    return { kind: "empty" };
  return { kind: "ready", equipment, skipped, floorPlanText, notes };
}
