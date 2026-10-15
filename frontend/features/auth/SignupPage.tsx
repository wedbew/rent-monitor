import { useState } from "react";
import { Link } from "react-router";

import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError, useFormAttempt } from "../../ui/FormErrors";
import { InlineNotice } from "../../ui/Status";
import { PageHeading } from "../../shell/PageHeading";
import { emailError, newPasswordError, PASSWORD_MIN, readFailure } from "./forms";
import { GoogleButton } from "./GoogleButton";
import { ProblemNotice } from "./ProblemNotice";
import { useGoogleSignIn, useRegister, useRegisterResend } from "./useAuthMutations";
import styles from "./auth.module.css";

const IDS = { email: "signup-email", password: "signup-password" } as const;

/** Create an account with an e-mail and password; the account exists only once the mailed link is used. */
export function SignupPage() {
  const register = useRegister();
  const resend = useRegisterResend();
  const google = useGoogleSignIn();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<readonly FieldError[]>([]);
  const [attempt, markInvalid] = useFormAttempt();
  const [sentTo, setSentTo] = useState<string | null>(null);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const found: FieldError[] = [];
    const e = emailError(email);
    const p = newPasswordError(password);
    if (e) found.push({ fieldId: IDS.email, message: e });
    if (p) found.push({ fieldId: IDS.password, message: p });
    setErrors(found);
    if (found.length > 0) {
      markInvalid();
      return;
    }
    const address = email.trim();
    register.mutate(
      { email: address, password },
      { onSuccess: () => setSentTo(address), onError: markInvalid },
    );
  };

  const failure = register.isError ? readFailure(register.error) : null;
  const serverErrors: FieldError[] = failure
    ? Object.entries(failure.fields).map(([name, message]) => ({
        fieldId: name === "email" ? IDS.email : IDS.password,
        message,
      }))
    : [];
  const shown = errors.length > 0 ? errors : serverErrors;
  const messageFor = (id: string) => shown.find((x) => x.fieldId === id)?.message;
  const googleFailure = google.isError ? readFailure(google.error) : null;
  const resendFailure = resend.isError ? readFailure(resend.error) : null;

  if (sentTo !== null) {
    return (
      <div className={styles["stack"]}>
        <PageHeading title="Sprawdź skrzynkę" />
        <InlineNotice tone="success" title="Wysłaliśmy link potwierdzający" live="status">
          Jeśli {sentTo} może założyć konto, znajdziesz tam wiadomość z linkiem. Konto powstanie dopiero po
          jego otwarciu. Jeśli wiadomość nie dotarła, sprawdź spam albo poproś o nowy link.
        </InlineNotice>
        {resend.isSuccess ? (
          <InlineNotice tone="info" title="Poprosiliśmy o nowy link" live="status">
            Jeśli czekała na Ciebie rejestracja, wysłaliśmy nową wiadomość. Poprzedni link przestał działać.
          </InlineNotice>
        ) : null}
        {resendFailure?.general ? <ProblemNotice problem={resendFailure.general} /> : null}
        <div className={styles["links"]}>
          <Button type="button" busy={resend.isPending} onClick={() => resend.mutate(sentTo)}>
            Wyślij link ponownie
          </Button>
          <Button type="button" onClick={() => setSentTo(null)}>
            Zmień adres
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles["stack"]}>
      <PageHeading title="Załóż konto" lead="Pierwsze analizy dostajesz po potwierdzeniu adresu e-mail." />
      {googleFailure?.general ? <ProblemNotice problem={googleFailure.general} tone="info" /> : null}
      <GoogleButton text="signup_with" onCredential={(credential) => google.mutate(credential)} />
      <form className={styles["form"]} onSubmit={submit} noValidate aria-label="Rejestracja">
        <FormErrorSummary errors={shown} attempt={attempt} />
        {failure?.general ? <ProblemNotice key={attempt} problem={failure.general} /> : null}
        <TextField
          fieldId={IDS.email}
          label="Adres e-mail"
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          value={email}
          onValueChange={setEmail}
          error={messageFor(IDS.email)}
        />
        <TextField
          fieldId={IDS.password}
          label="Hasło"
          type="password"
          name="new-password"
          autoComplete="new-password"
          hint={`Co najmniej ${PASSWORD_MIN} znaków. Unikaj popularnych haseł i swojego adresu e-mail.`}
          value={password}
          onValueChange={setPassword}
          error={messageFor(IDS.password)}
        />
        <Button type="submit" variant="primary" fill busy={register.isPending} icon="arrow">
          Załóż konto
        </Button>
        <p className={styles["muted"]}>
          Zakładając konto, akceptujesz <Link to="/terms">Regulamin</Link> i zapoznajesz się z{" "}
          <Link to="/privacy">Polityką prywatności</Link>.
        </p>
      </form>
      <p className={styles["muted"]}>
        Masz już konto? <Link to="/login">Zaloguj się</Link>
      </p>
    </div>
  );
}
