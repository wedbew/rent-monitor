import type { AuditState } from "../status";
import { t } from "../../../i18n";

/**
 * The state of the collection lives in the address, so Back, Refresh and a shared link restore it. Everything is
 * validated against a closed vocabulary: an unknown value in the URL is ignored, never sent to the API.
 */
export type View = "cards" | "table";

export const STATUS_GROUPS = {
  ready: ["succeeded", "succeeded_degraded"],
  active: ["queued", "running"],
  rejected: ["rejected"],
  failed: ["failed_input", "failed_upstream", "failed_internal", "cancelled"],
} as const satisfies Record<string, readonly AuditState[]>;

export type StatusGroup = keyof typeof STATUS_GROUPS;

export const STATUS_OPTIONS: readonly { value: "" | StatusGroup; label: string }[] = [
  { value: "", label: t.analyses.list.statusOptions.all },
  { value: "ready", label: t.analyses.list.statusOptions.ready },
  { value: "active", label: t.analyses.list.statusOptions.active },
  { value: "rejected", label: t.analyses.list.statusOptions.rejected },
  { value: "failed", label: t.analyses.list.statusOptions.failed },
];

export const GRADES = ["A", "B", "C", "D", "E", "N"] as const;
export type GradeFilter = (typeof GRADES)[number];

export const GRADE_OPTIONS: readonly { value: "" | GradeFilter; label: string }[] = [
  { value: "", label: t.analyses.list.gradeOptions.all },
  ...GRADES.map((g) => ({ value: g, label: g === "N" ? t.analyses.list.gradeOptions.none : g })),
];

/** The API's `q` is an Otodom id prefix: letters and digits only, bounded. */
const QUERY = /^[A-Za-z0-9]{1,20}$/;

export interface CollectionFilters {
  readonly view: View;
  readonly status: "" | StatusGroup;
  readonly grade: "" | GradeFilter;
  readonly q: string;
  /** Show the saved listings (`GET /api/saved`) instead of the analyses collection. */
  readonly saved: boolean;
}

export const DEFAULT_FILTERS: CollectionFilters = {
  view: "cards",
  status: "",
  grade: "",
  q: "",
  saved: false,
};

export function readFilters(params: URLSearchParams): CollectionFilters {
  const view = params.get("view") === "table" ? "table" : "cards";
  const statusParam = params.get("status") ?? "";
  const status = (Object.keys(STATUS_GROUPS) as StatusGroup[]).find((g) => g === statusParam) ?? "";
  const gradeParam = params.get("grade") ?? "";
  const grade = GRADES.find((g) => g === gradeParam) ?? "";
  const q = (params.get("q") ?? "").trim();
  return { view, status, grade, q: QUERY.test(q) ? q : "", saved: params.get("saved") === "1" };
}

/** Only non-default values are written, so the plain collection keeps its plain address. */
export function writeFilters(filters: CollectionFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.view !== "cards") params.set("view", filters.view);
  if (filters.status !== "") params.set("status", filters.status);
  if (filters.grade !== "") params.set("grade", filters.grade);
  if (filters.q !== "") params.set("q", filters.q);
  if (filters.saved) params.set("saved", "1");
  return params;
}

export const hasActiveFilters = (f: CollectionFilters): boolean =>
  f.status !== "" || f.grade !== "" || f.q !== "";

/** The API query for these filters (a status group is several repeated `status` parameters). */
export function apiQuery(filters: CollectionFilters, limit: number, cursor: string | null) {
  return {
    limit,
    ...(cursor !== null ? { cursor } : {}),
    ...(filters.status !== "" ? { status: [...STATUS_GROUPS[filters.status]] } : {}),
    ...(filters.grade !== "" ? { grade: filters.grade } : {}),
    ...(filters.q !== "" ? { q: filters.q } : {}),
  };
}
