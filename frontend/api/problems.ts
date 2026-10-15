import type { components } from "./schema.generated";

export type Problem = components["schemas"]["Problem"];
export type ProblemCode = components["schemas"]["ProblemCode"];

/** What the screen should offer next. The page decides how to render it; this says which one applies. */
export type ProblemAction =
  | "none"
  | "retry"
  | "waitAndRetry"
  | "signIn"
  | "buyReports"
  | "verifyEmail"
  | "fixInput"
  | "openAnalysis"
  | "contactSupport"
  | "useEmailLink"
  | "requestNewLink"
  | "reload"
  | "goBack";

export interface ProblemCopy {
  readonly title: string;
  readonly detail: string;
  readonly action: ProblemAction;
}

/**
 * Polish copy for every stable problem code. `satisfies Record<ProblemCode, ...>` makes a new code in the API a
 * compile error here (after `pnpm generate:api`), and `problems.test.ts` reads the enum from docs/openapi.json so
 * the table cannot lag the committed schema either. Where a failure releases the reserved credit the text says so.
 */
export const PROBLEM_COPY = {
  INVALID_LISTING_REF: {
    title: "To nie jest ogłoszenie z Otodom",
    detail: "Wklej adres ogłoszenia sprzedaży z Otodom albo jego numer.",
    action: "fixInput",
  },
  QUOTA_EXHAUSTED: {
    title: "Nie masz już raportów",
    detail: "Kup pakiet raportów, aby przeanalizować kolejne ogłoszenie.",
    action: "buyReports",
  },
  AUDIT_IN_PROGRESS: {
    title: "Ta analiza już trwa",
    detail: "Dla tego ogłoszenia analiza jest w toku. Otwórz ją zamiast zaczynać nową.",
    action: "openAnalysis",
  },
  RENT_NOT_DEAL: {
    title: "To ogłoszenie wynajmu",
    detail: "Analizujemy tylko ogłoszenia sprzedaży. Raport nie został pobrany z konta.",
    action: "none",
  },
  FRACTIONAL_OWNERSHIP: {
    title: "To sprzedaż udziału",
    detail: "Nie analizujemy udziałów w nieruchomości ani spadków. Raport nie został pobrany z konta.",
    action: "none",
  },
  LISTING_GONE: {
    title: "Ogłoszenie jest już nieaktywne",
    detail: "Nie znaleźliśmy tego ogłoszenia, mogło zostać usunięte. Raport nie został pobrany z konta.",
    action: "none",
  },
  UPSTREAM_BLOCKED: {
    title: "Otodom chwilowo nas blokuje",
    detail: "Spróbuj ponownie za kilka minut. Raport nie został pobrany z konta.",
    action: "waitAndRetry",
  },
  UPSTREAM_SCHEMA_DRIFT: {
    title: "Nie udało się odczytać ogłoszenia",
    detail:
      "Strona Otodom wygląda inaczej niż oczekiwaliśmy. Zajmiemy się tym; raport nie został pobrany z konta.",
    action: "contactSupport",
  },
  VISION_UNAVAILABLE: {
    title: "Bez oceny zdjęć",
    detail: "Raport powstał bez analizy zdjęć, więc jest mniej pewny. Koszt remontu to założenie.",
    action: "none",
  },
  CONTEXT_UNAVAILABLE: {
    title: "Brakuje danych rynkowych",
    detail: "Nie mamy dość czynszów z tej okolicy, by wycenić najem. Raport nie został pobrany z konta.",
    action: "none",
  },
  INTERNAL: {
    title: "Coś poszło nie tak po naszej stronie",
    detail: "Spróbuj ponownie. Jeśli problem wraca, podaj numer zgłoszenia.",
    action: "retry",
  },
  VALIDATION_ERROR: {
    title: "Sprawdź wpisane dane",
    detail: "Niektóre pola są niepoprawne. Popraw je i spróbuj jeszcze raz.",
    action: "fixInput",
  },
  NOT_FOUND: {
    title: "Nie znaleziono",
    detail: "Ten zasób nie istnieje albo nie masz do niego dostępu.",
    action: "goBack",
  },
  HTTP_ERROR: {
    title: "Nieoczekiwany błąd żądania",
    detail: "Spróbuj ponownie. Jeśli problem wraca, podaj numer zgłoszenia.",
    action: "retry",
  },
  NOT_READY: {
    title: "Usługa jest chwilowo niedostępna",
    detail: "Spróbuj ponownie za chwilę.",
    action: "waitAndRetry",
  },
  INVALID_GOOGLE_TOKEN: {
    title: "Logowanie przez Google nie powiodło się",
    detail: "Spróbuj ponownie albo zaloguj się linkiem wysłanym e-mailem.",
    action: "retry",
  },
  GOOGLE_EMAIL_UNVERIFIED: {
    title: "Adres e-mail w Google nie jest potwierdzony",
    detail: "Zaloguj się linkiem, który wyślemy na ten adres.",
    action: "useEmailLink",
  },
  EMAIL_CONFIRMATION_REQUIRED: {
    title: "Potwierdź adres e-mail",
    detail: "Wyślemy Ci link do logowania, który to potwierdzi.",
    action: "useEmailLink",
  },
  MAGIC_LINK_INVALID: {
    title: "Link jest nieprawidłowy lub wygasł",
    detail: "Poproś o nowy link do logowania.",
    action: "requestNewLink",
  },
  INVALID_CREDENTIALS: {
    title: "Nieprawidłowy e-mail lub hasło",
    detail: "Sprawdź dane albo zresetuj hasło.",
    action: "fixInput",
  },
  WEAK_PASSWORD: {
    title: "Hasło jest zbyt słabe",
    detail: "Użyj co najmniej 10 znaków i nie używaj popularnych haseł ani swojego adresu e-mail.",
    action: "fixInput",
  },
  AUTH_TOKEN_INVALID: {
    title: "Link jest nieprawidłowy lub wygasł",
    detail: "Poproś o nowy link.",
    action: "requestNewLink",
  },
  ACCOUNT_EXISTS: {
    title: "Konto z tym adresem już istnieje",
    detail: "Zaloguj się albo zresetuj hasło.",
    action: "signIn",
  },
  BILLING_UNAVAILABLE: {
    title: "Zakupy nie są jeszcze dostępne",
    detail: "Płatności zostaną uruchomione wkrótce. Nic nie zostało pobrane.",
    action: "none",
  },
  IDEMPOTENCY_CONFLICT: {
    title: "Ta próba zakupu dotyczy innego pakietu",
    detail: "Odśwież stronę i wybierz pakiet jeszcze raz.",
    action: "reload",
  },
  BILLING_PROVIDER_ERROR: {
    title: "Operator płatności nie odpowiada",
    detail: "Nic nie zostało pobrane. Spróbuj ponownie za chwilę.",
    action: "retry",
  },
  INVALID_WEBHOOK_SIGNATURE: {
    title: "Odrzucone powiadomienie płatnicze",
    detail: "To zgłoszenie nie pochodzi od operatora płatności.",
    action: "contactSupport",
  },
  BILLING_HOLD: {
    title: "Konto czeka na weryfikację rozliczeń",
    detail: "Nowe analizy i zakupy są wstrzymane. Skontaktuj się z pomocą.",
    action: "contactSupport",
  },
  PURCHASE_NOT_REFUNDABLE: {
    title: "Tej operacji nie można wykonać",
    detail: "Faktura jest dostępna dopiero po opłaceniu zakupu, a zwrot tylko dla niewykorzystanego pakietu.",
    action: "none",
  },
  REFUND_NEEDS_REVIEW: {
    title: "Zwrot wymaga ręcznej decyzji",
    detail: "Część raportów z pakietu została już wykorzystana.",
    action: "contactSupport",
  },
  EMAIL_NOT_VERIFIED: {
    title: "Potwierdź adres e-mail",
    detail: "Zanim kupisz raporty, potwierdź adres e-mail linkiem z wiadomości.",
    action: "verifyEmail",
  },
  FEATURE_NOT_IN_PLAN: {
    title: "Ta funkcja nie jest jeszcze dostępna",
    detail: "Pracujemy nad nią. Nic nie zostało pobrane.",
    action: "none",
  },
  ADMIN_ONLY: {
    title: "Tylko dla administratorów",
    detail: "Nie masz uprawnień do tej operacji.",
    action: "goBack",
  },
  ALREADY_SUBSCRIBED: {
    title: "Masz już aktywny abonament",
    detail: "Abonamenty nie są już sprzedawane; korzystaj z pakietów raportów.",
    action: "none",
  },
  INVALID_STRIPE_SIGNATURE: {
    title: "Odrzucone powiadomienie płatnicze",
    detail: "To zgłoszenie nie pochodzi od operatora płatności.",
    action: "contactSupport",
  },
  UNAUTHENTICATED: {
    title: "Sesja wygasła",
    detail: "Zaloguj się ponownie, aby kontynuować.",
    action: "signIn",
  },
  RATE_LIMITED: {
    title: "Zbyt wiele prób",
    detail: "Odczekaj chwilę i spróbuj ponownie.",
    action: "waitAndRetry",
  },
  ORIGIN_NOT_ALLOWED: {
    title: "Żądanie odrzucone ze względów bezpieczeństwa",
    detail: "Odśwież stronę i spróbuj ponownie.",
    action: "reload",
  },
  CONFIRMATION_MISMATCH: {
    title: "Adres e-mail się nie zgadza",
    detail: "Wpisz dokładnie adres e-mail swojego konta.",
    action: "fixInput",
  },
  CREDIT_BELOW_ZERO: {
    title: "Saldo nie może spaść poniżej zera",
    detail: "Zmień wartość korekty.",
    action: "none",
  },
  SAVED_LIMIT_REACHED: {
    title: "Osiągnięto limit zapisanych ogłoszeń",
    detail: "Usuń część zapisanych ogłoszeń (limit to 500), aby dodać kolejne.",
    action: "none",
  },
} as const satisfies Record<ProblemCode, ProblemCopy>;

/** Failures that never reach the API's problem format. */
export type TransportFailure = "network" | "timeout" | "aborted" | "invalid-response";

export const TRANSPORT_COPY = {
  network: {
    title: "Brak połączenia",
    detail: "Nie udało się połączyć z serwerem. Sprawdź internet i spróbuj ponownie.",
    action: "retry",
  },
  timeout: {
    title: "Serwer odpowiada zbyt wolno",
    detail: "Spróbuj ponownie za chwilę.",
    action: "retry",
  },
  aborted: { title: "Anulowano", detail: "Żądanie zostało przerwane.", action: "none" },
  "invalid-response": {
    title: "Nieoczekiwana odpowiedź serwera",
    detail: "Odpowiedź ma nieznany format. Spróbuj ponownie lub odśwież stronę.",
    action: "reload",
  },
} as const satisfies Record<TransportFailure, ProblemCopy>;

export interface DescribedProblem extends ProblemCopy {
  /** Kept so support can find the request in the logs; shown small, never as the headline. */
  readonly requestId: string | null;
  readonly retryAfterS: number | null;
}

export function isProblemCode(value: unknown): value is ProblemCode {
  return typeof value === "string" && Object.hasOwn(PROBLEM_COPY, value);
}

export function describeProblem(
  code: ProblemCode,
  extra: { requestId?: string | null; retryAfterS?: number | null } = {},
): DescribedProblem {
  return {
    ...PROBLEM_COPY[code],
    requestId: extra.requestId ?? null,
    retryAfterS: extra.retryAfterS ?? null,
  };
}

export function describeTransport(kind: TransportFailure): DescribedProblem {
  return { ...TRANSPORT_COPY[kind], requestId: null, retryAfterS: null };
}
