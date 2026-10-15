import { useEffect, useState } from "react";
import { Link } from "react-router";

import { PageHeading } from "../../shell/PageHeading";
import { Button, LinkButton } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError } from "../../ui/FormErrors";
import { InlineNotice } from "../../ui/Status";
import { emailError, newPasswordError, PASSWORD_MIN, readFailure } from "./forms";
import { ProblemNotice } from "./ProblemNotice";
import { clearCapturedToken, readCapturedToken } from "./token";
import { usePasswordForgot, usePasswordReset } from "./useAuthMutations";
import styles from "./auth.module.css";

/** `/password/forgot`: always answers the same, whether or not the address has an account. */
export function ForgotPasswordPage() {
  const forgot = usePasswordForgot();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const problem = emailError(email);
    setError(problem);
    if (problem === null) forgot.mutate(email.trim());
  };
  const failure = forgot.isError ? readFailure(forgot.error) : null;

  return (
    <div className={styles["stack"]}>
      <PageHeading
        title="Nie pamiętam hasła"
        lead="Podaj adres e-mail konta. Wyślemy link do ustawienia nowego hasła."
      />
      {forgot.isSuccess ? (
        <InlineNotice tone="success" title="Sprawdź skrzynkę" live="status">
          Jeśli to konto istnieje, wysłaliśmy na nie link do ustawienia hasła. Jest ważny krótko i działa raz.
        </InlineNotice>
      ) : (
        <form className={styles["form"]} onSubmit={submit} noValidate aria-label="Reset hasła">
          {failure?.general ? <ProblemNotice problem={failure.general} /> : null}
          <TextField
            label="Adres e-mail"
            type="email"
            name="email"
            autoComplete="email"
            inputMode="email"
            value={email}
            onValueChange={setEmail}
            error={error}
          />
          <Button type="submit" variant="primary" fill busy={forgot.isPending} icon="arrow">
            Wyślij link
          </Button>
        </form>
      )}
      <p className={styles["muted"]}>
        <Link to="/login">Wróć do logowania</Link>
      </p>
    </div>
  );
}

const PASSWORD_ID = "reset-password";

/** `/password/reset#t=...`: set a new password with the token from the mailed link; it signs everyone out. */
export function ResetPasswordPage() {
  const reset = usePasswordReset();
  const [token] = useState(readCapturedToken);
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<readonly FieldError[]>([]);
  const [submitCount, setSubmitCount] = useState(0);

  useEffect(() => clearCapturedToken, []);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (token === null) return;
    const problem = newPasswordError(password);
    const found = problem ? [{ fieldId: PASSWORD_ID, message: problem }] : [];
    setErrors(found);
    if (found.length > 0) {
      setSubmitCount((n) => n + 1);
      return;
    }
    reset.mutate({ token, password }, { onError: () => setSubmitCount((n) => n + 1) });
  };

  const failure = reset.isError ? readFailure(reset.error) : null;
  const serverError = failure?.fields["password"];
  const shown =
    errors.length > 0 ? errors : serverError ? [{ fieldId: PASSWORD_ID, message: serverError }] : [];
  const invalidLink = token === null || failure?.code === "AUTH_TOKEN_INVALID";

  if (reset.isSuccess) {
    return (
      <div className={styles["stack"]}>
        <PageHeading title="Hasło zostało zmienione" />
        <InlineNotice tone="success" title="Możesz się zalogować" live="status">
          Ze względów bezpieczeństwa wylogowaliśmy Cię ze wszystkich urządzeń. Zaloguj się nowym hasłem.
        </InlineNotice>
        <LinkButton to="/login" variant="primary" icon="arrow">
          Zaloguj się
        </LinkButton>
      </div>
    );
  }

  return (
    <div className={styles["stack"]}>
      <PageHeading title="Ustaw nowe hasło" />
      {invalidLink ? (
        <>
          <InlineNotice tone="danger" title="Link jest nieprawidłowy lub wygasł" live="alert">
            Poproś o nowy link do ustawienia hasła.
          </InlineNotice>
          <LinkButton to="/password/forgot" variant="primary" icon="arrow">
            Poproś o nowy link
          </LinkButton>
        </>
      ) : (
        <form className={styles["form"]} onSubmit={submit} noValidate aria-label="Nowe hasło">
          <FormErrorSummary errors={shown} submitCount={submitCount} />
          {failure?.general ? <ProblemNotice problem={failure.general} /> : null}
          <TextField
            fieldId={PASSWORD_ID}
            label="Nowe hasło"
            type="password"
            name="new-password"
            autoComplete="new-password"
            hint={`Co najmniej ${PASSWORD_MIN} znaków. Unikaj popularnych haseł i swojego adresu e-mail.`}
            value={password}
            onValueChange={setPassword}
            error={shown[0]?.message}
          />
          <Button type="submit" variant="primary" fill busy={reset.isPending} icon="arrow">
            Zapisz hasło
          </Button>
        </form>
      )}
      <p className={styles["muted"]}>
        <Link to="/login">Wróć do logowania</Link>
      </p>
    </div>
  );
}
