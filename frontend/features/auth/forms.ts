import { ApiError } from "../../api/errors";
import { describeProblem, describeTransport, type DescribedProblem } from "../../api/problems";
import { TransportError } from "../../api/errors";
import { plural } from "../../api/format";

/** Loose on purpose: delivery is the real check, the server is authoritative (rm_contracts EMAIL_PATTERN). */
const EMAIL =
  /^[^@\s<>"',;()[\]\\]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

export const PASSWORD_MIN = 10;
export const PASSWORD_MAX = 128;

export function emailError(value: string): string | null {
  const email = value.trim();
  if (email === "") return "Wpisz adres e-mail.";
  return email.length <= 254 && EMAIL.test(email)
    ? null
    : "Wpisz poprawny adres e-mail, na przykład anna@example.com.";
}

export function newPasswordError(value: string): string | null {
  if (value === "") return "Wpisz hasło.";
  if ([...value].length < PASSWORD_MIN) return `Hasło musi mieć co najmniej ${PASSWORD_MIN} znaków.`;
  if ([...value].length > PASSWORD_MAX) return `Hasło może mieć najwyżej ${PASSWORD_MAX} znaków.`;
  return null;
}

export function currentPasswordError(value: string): string | null {
  return value === "" ? "Wpisz hasło." : null;
}

/** The API's closed vocabulary for `WEAK_PASSWORD.reason` (services/rm_api/auth/passwords.py). */
const REASONS: Record<string, string> = {
  too_short: `Hasło jest za krótkie: użyj co najmniej ${PASSWORD_MIN} znaków.`,
  too_long: `Hasło jest za długie: użyj najwyżej ${PASSWORD_MAX} znaków.`,
  common: "To hasło jest zbyt popularne. Wybierz inne, najlepiej kilka słów.",
  contains_email: "Hasło nie może zawierać Twojego adresu e-mail.",
};

export function weakPasswordMessage(reason: unknown): string {
  return (
    // Own keys only: a reason like "toString" must not reach the prototype (a function is not copy).
    (typeof reason === "string" && Object.hasOwn(REASONS, reason) ? REASONS[reason] : undefined) ??
    "Hasło jest zbyt słabe. Wybierz dłuższe, mniej oczywiste hasło."
  );
}

/** "za 42 sekundy", "za 2 minuty": how long until a throttled action may be retried. */
export function retryIn(seconds: number): string {
  if (seconds < 90) return `za ${seconds} ${plural(seconds, ["sekundę", "sekundy", "sekund"])}`;
  const minutes = Math.ceil(seconds / 60);
  return `za ${minutes} ${plural(minutes, ["minutę", "minuty", "minut"])}`;
}

export interface FailedSubmit {
  /** Messages for fields, by the API field name (`email`, `password`, `token`...). */
  readonly fields: Readonly<Record<string, string>>;
  /** What to tell the person about the form as a whole, when no single field is at fault. */
  readonly general: DescribedProblem | null;
  readonly code: string | null;
}

/**
 * One reading of a failed request for every auth form: 422s become field messages (the server's `loc` says which
 * field), a weak password becomes the password field's message with its reason, a throttle shows the retry time,
 * anything else is a general problem with the stable copy and the request id for support.
 */
export function readFailure(error: unknown): FailedSubmit {
  if (error instanceof TransportError)
    return { fields: {}, general: describeTransport(error.kind), code: null };
  if (!(error instanceof ApiError) || error.problem === null) {
    return { fields: {}, general: describeTransport("invalid-response"), code: null };
  }
  const { problem } = error;
  if (problem.code === "WEAK_PASSWORD") {
    const reason = (problem as unknown as Record<string, unknown>)["reason"];
    return { fields: { password: weakPasswordMessage(reason) }, general: null, code: problem.code };
  }
  if (problem.code === "VALIDATION_ERROR" && problem.errors !== null && problem.errors.length > 0) {
    const fields: Record<string, string> = {};
    for (const item of problem.errors) {
      const name = String(item.loc.at(-1) ?? "");
      fields[name] ??= "Sprawdź tę wartość.";
    }
    return { fields, general: null, code: problem.code };
  }
  return {
    fields: {},
    general: describeProblem(problem.code, { requestId: problem.request_id, retryAfterS: error.retryAfterS }),
    code: problem.code,
  };
}
