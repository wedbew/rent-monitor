import { t } from "../../i18n";
import type { CohortKey } from "./filters";

/**
 * The two ways the source groups flats, and only those: by area or by number of rooms. A statistic exists for each
 * group on its own, not for a combination, so a choice is one key and picking from one family replaces the other.
 * Area groups include their lower bound and exclude the upper (45 m² is in "45 do 60", not "30 do 45"), which is how
 * the server draws them.
 */
export const SIZE_KEYS = ["size_lt30", "size_30_45", "size_45_60", "size_60_80", "size_80plus"] as const;
export const ROOMS_KEYS = ["rooms_1", "rooms_2", "rooms_3", "rooms_4plus"] as const;
export type SizeKey = (typeof SIZE_KEYS)[number];
export type RoomsKey = (typeof ROOMS_KEYS)[number];

export const isSize = (key: CohortKey): key is SizeKey => (SIZE_KEYS as readonly string[]).includes(key);
export const isRooms = (key: CohortKey): key is RoomsKey => (ROOMS_KEYS as readonly string[]).includes(key);

export function cohortLabel(key: CohortKey): string {
  if (key === "all") return t.rynek.filters.all;
  return isSize(key) ? t.rynek.filters.sizes[key] : t.rynek.filters.roomsOptions[key];
}

/** The family a key belongs to, or null for "all". */
export const familyOf = (key: CohortKey): "area" | "rooms" | null =>
  isSize(key) ? "area" : isRooms(key) ? "rooms" : null;
