import { formatCount } from "../../../api/format";
import { t } from "../../../i18n";

/**
 * Otodom's own codes for a listing's attributes (`gas`, `floor_1`, `plastic`) turned into Polish words. The same raw
 * string can mean different things under different attributes, so every lookup is by attribute. The report keeps the
 * provider's value untouched; this is presentation only. A value we do not know is said to be unrecognised, never
 * printed raw.
 */
export type AttributeKind = "heating" | "windows" | "buildingType" | "floor";

const A = t.analyses.report.attributes;

const TABLES: Readonly<Record<AttributeKind, Readonly<Record<string, string>>>> = {
  heating: A.heating,
  windows: A.windows,
  buildingType: A.buildingType,
  floor: A.floor,
};

/** `floor_3` is Otodom's code; a bare `3` is what an advert's free field sometimes holds. Neither exceeds a tower. */
const FLOOR_CODE = /^(?:floor_)?(\d{1,3})$/;

const isMissing = (raw: string | null | undefined): raw is null | undefined | "" =>
  raw === null || raw === undefined || raw.trim() === "";

interface Floor {
  readonly label: string;
  /** A numbered storey ("3. piętro"): the only kind that reads naturally as "of N floors". */
  readonly numbered: boolean;
}

function parseFloor(raw: string): Floor {
  const key = raw.trim().toLowerCase();
  const code = FLOOR_CODE.exec(key);
  if (code?.[1] !== undefined) {
    const n = Number(code[1]);
    if (n === 0) return { label: A.floor["ground_floor"] ?? A.unrecognised, numbered: false };
    return { label: A.floorNumber({ floor: formatCount(n) }), numbered: true };
  }
  const known = Object.hasOwn(A.floor, key) ? A.floor[key as keyof typeof A.floor] : undefined;
  return { label: known ?? A.unrecognised, numbered: false };
}

/** The Polish label for one attribute value, or null when the listing has none. */
export function attributeLabel(kind: AttributeKind, raw: string | null | undefined): string | null {
  if (isMissing(raw)) return null;
  if (kind === "floor") return parseFloor(raw).label;
  const table = TABLES[kind];
  const key = raw.trim().toLowerCase();
  return Object.hasOwn(table, key) ? (table[key] ?? A.unrecognised) : A.unrecognised;
}

/**
 * The storey for the summary line: "3. piętro z 5" for a numbered storey in a building of known height, otherwise the
 * storey alone ("parter", "poddasze"). Null when the listing has no storey or we cannot read it.
 */
export function floorSummary(raw: string | null | undefined, buildingFloors: number | null): string | null {
  if (isMissing(raw)) return null;
  const floor = parseFloor(raw);
  if (floor.label === A.unrecognised) return null;
  if (floor.numbered && buildingFloors !== null) {
    return A.floorOf({ floor: floor.label, floors: formatCount(buildingFloors) });
  }
  return floor.label;
}
