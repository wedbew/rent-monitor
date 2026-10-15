/**
 * One server-sent frame of an analysis, as the API writes it (services/rm_api/sse.py): `progress` while it runs,
 * then exactly one `done` or `error`. Everything is read defensively: a frame that does not fit is dropped, never
 * guessed at, and no number is ever computed here (stage and percentage are the server's).
 */
export type FrameKind = "progress" | "done" | "error";

export interface Frame {
  /** The server's event id (monotonic per audit). Null only for a synthesised terminal frame. */
  readonly id: number | null;
  readonly kind: FrameKind;
  readonly stage: string | null;
  readonly pct: number | null;
  /** For `error`: the stable error code (`RENT_NOT_DEAL`, `UPSTREAM_BLOCKED`, ...). */
  readonly code: string | null;
  /** For `done` and `error`: the audit's final status. */
  readonly status: string | null;
}

export const TERMINAL: readonly FrameKind[] = ["done", "error"];

export const isTerminal = (frame: Frame): boolean => TERMINAL.includes(frame.kind);

const text = (value: unknown, max = 64): string | null =>
  typeof value === "string" && value.length > 0 && value.length <= max ? value : null;

const percent = (value: unknown): number | null =>
  typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 100 ? value : null;

export function parseFrame(kind: string, lastEventId: string, data: unknown): Frame | null {
  if (kind !== "progress" && kind !== "done" && kind !== "error") return null;
  if (typeof data !== "string" || data.length > 4096) return null;
  let body: unknown;
  try {
    body = JSON.parse(data);
  } catch {
    return null;
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) return null;
  const record = body as Record<string, unknown>;
  const id = /^\d{1,15}$/.test(lastEventId) ? Number(lastEventId) : null;
  return {
    id,
    kind,
    stage: text(record["stage"]),
    pct: percent(record["pct"]),
    code: text(record["code"]),
    status: text(record["status"]),
  };
}

/** Human names of the pipeline stages (CONTEXT.md section 7). An unknown stage keeps its raw name out of the UI. */
const STAGES: Readonly<Record<string, string>> = {
  fetch: "Pobieranie ogłoszenia",
  extract: "Odczyt danych z ogłoszenia",
  context: "Dane rynkowe i czynsze",
  vision: "Analiza zdjęć",
  ocr: "Odczyt rzutu mieszkania",
  anchors: "Ceny odniesienia",
  synthesize: "Wyliczenia inwestycji",
  persist: "Zapis raportu",
};

export function stageLabel(stage: string | null): string {
  return (stage !== null ? STAGES[stage] : undefined) ?? "Przetwarzanie";
}
