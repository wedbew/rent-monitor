import type { components } from "../../api/schema.generated";

export type AuditState = components["schemas"]["AuditState"];
export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export interface StatusCopy {
  readonly label: string;
  readonly tone: Tone;
  /** One line that says what happened to the person's report credit, when that is knowable from the state. */
  readonly credit: string | null;
}

const REJECTIONS: Record<string, string> = {
  RENT_NOT_DEAL: "To ogłoszenie wynajmu",
  FRACTIONAL_OWNERSHIP: "Sprzedaż udziału",
};

const FAILURES: Record<string, string> = {
  LISTING_GONE: "Ogłoszenie nieaktywne",
  UPSTREAM_BLOCKED: "Otodom zablokował pobranie",
  UPSTREAM_SCHEMA_DRIFT: "Nie udało się odczytać ogłoszenia",
  CONTEXT_UNAVAILABLE: "Brak danych rynkowych",
  TIMEOUT: "Przekroczono czas",
};

/**
 * What an analysis's state means in words, in one place for the dashboard, the collection and the report. The
 * `switch` is exhaustive: a new state in the API is a compile error here, not a silent blank.
 */
export function statusCopy(status: AuditState, errorCode: string | null): StatusCopy {
  switch (status) {
    case "queued":
      return { label: "W kolejce", tone: "neutral", credit: "Raport jest zarezerwowany." };
    case "running":
      return { label: "W trakcie", tone: "info", credit: "Raport jest zarezerwowany." };
    case "succeeded":
      return { label: "Analiza gotowa", tone: "success", credit: "Raport został pobrany z konta." };
    case "succeeded_degraded":
      return { label: "Gotowa, mniej pewna", tone: "warning", credit: "Raport został pobrany z konta." };
    case "rejected":
      return {
        label: (errorCode !== null ? REJECTIONS[errorCode] : undefined) ?? "Odrzucona",
        tone: "warning",
        credit: "Raport nie został pobrany.",
      };
    case "failed_input":
    case "failed_upstream":
    case "failed_internal":
      return {
        label: (errorCode !== null ? FAILURES[errorCode] : undefined) ?? "Nie udało się",
        tone: "danger",
        credit: "Raport nie został pobrany.",
      };
    case "cancelled":
      return { label: "Anulowana", tone: "neutral", credit: "Raport nie został pobrany." };
  }
}

/** Finished with a usable report. */
export function hasReport(status: AuditState): boolean {
  return status === "succeeded" || status === "succeeded_degraded";
}

export function isActive(status: AuditState): boolean {
  return status === "queued" || status === "running";
}
