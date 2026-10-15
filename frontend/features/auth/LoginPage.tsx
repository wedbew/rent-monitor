import { useRef, useState } from "react";
import { Link } from "react-router";

import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError, useFormAttempt } from "../../ui/FormErrors";
import { InlineNotice } from "../../ui/Status";
import { PageHeading } from "../../shell/PageHeading";
import { currentPasswordError, emailError, readFailure } from "./forms";
import { GoogleButton } from "./GoogleButton";
import { ProblemNotice } from "./ProblemNotice";
import { useGoogleSignIn, useLogin, useMagicLinkRequest } from "./useAuthMutations";
import styles from "./auth.module.css";

const IDS = { email: "login-email", password: "login-password", linkEmail: "link-email" } as const;

/** Sign in: Google, e-mail and password, or a link sent to the mailbox. The same page for every method. */
export function LoginPage() {
  const login = useLogin();
  const google = useGoogleSignIn();
  const link = useMagicLinkRequest();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [linkEmail, setLinkEmail] = useState("");
  const [errors, setErrors] = useState<readonly FieldError[]>([]);
  const [attempt, markInvalid] = useFormAttempt();
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkAttempt, markLinkInvalid] = useFormAttempt();
  const linkField = useRef<HTMLInputElement>(null);

  const submitPassword = (event: React.FormEvent) => {
    event.preventDefault();
    const found: FieldError[] = [];
    const e = emailError(email);
    const p = currentPasswordError(password);
    if (e) found.push({ fieldId: IDS.email, message: e });
    if (p) found.push({ fieldId: IDS.password, message: p });
    setErrors(found);
    if (found.length > 0) {
      markInvalid();
      return;
    }
    login.mutate({ email: email.trim(), password }, { onError: markInvalid });
  };

  const submitLink = (event: React.FormEvent) => {
    event.preventDefault();
    const problem = emailError(linkEmail);
    setLinkError(problem);
    if (problem !== null) {
      markLinkInvalid();
      return;
    }
    link.mutate(linkEmail.trim(), { onError: markLinkInvalid });
  };

  const loginFailure = login.isError ? readFailure(login.error) : null;
  const googleFailure = google.isError ? readFailure(google.error) : null;
  const needsLink =
    googleFailure?.code === "EMAIL_CONFIRMATION_REQUIRED" ||
    googleFailure?.code === "GOOGLE_EMAIL_UNVERIFIED";
  const linkFailure = link.isError ? readFailure(link.error) : null;
  // Client errors while the person is fixing them; otherwise the server's field errors. One list, one summary.
  const serverErrors: FieldError[] = Object.entries(loginFailure?.fields ?? {}).map(([name, message]) => ({
    fieldId: name === "password" ? IDS.password : IDS.email,
    message,
  }));
  const shown = errors.length > 0 ? errors : serverErrors;
  const fieldMessage = (id: string) => shown.find((x) => x.fieldId === id)?.message;
  const linkMessage = linkError ?? linkFailure?.fields["email"] ?? null;
  const linkShown: FieldError[] = linkMessage ? [{ fieldId: IDS.linkEmail, message: linkMessage }] : [];

  return (
    <div className={styles["stack"]}>
      <PageHeading title="Zaloguj się" lead="Wróć do swoich analiz mieszkań." />

      {googleFailure?.general ? (
        <ProblemNotice
          problem={googleFailure.general}
          tone={needsLink ? "info" : "danger"}
          actions={
            needsLink ? (
              <Button type="button" onClick={() => linkField.current?.focus()}>
                Użyj linku e-mail
              </Button>
            ) : undefined
          }
        />
      ) : null}
      <GoogleButton text="signin_with" onCredential={(credential) => google.mutate(credential)} />

      <form className={styles["form"]} onSubmit={submitPassword} noValidate aria-label="Logowanie hasłem">
        <FormErrorSummary errors={shown} attempt={attempt} />
        {loginFailure?.general ? <ProblemNotice key={attempt} problem={loginFailure.general} /> : null}
        <TextField
          fieldId={IDS.email}
          label="Adres e-mail"
          type="email"
          name="email"
          autoComplete="email"
          inputMode="email"
          value={email}
          onValueChange={setEmail}
          error={fieldMessage(IDS.email)}
        />
        <TextField
          fieldId={IDS.password}
          label="Hasło"
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onValueChange={setPassword}
          error={fieldMessage(IDS.password)}
        />
        <Button type="submit" variant="primary" fill busy={login.isPending} icon="arrow">
          Zaloguj się
        </Button>
        <p className={styles["links"]}>
          <Link to="/password/forgot">Nie pamiętam hasła</Link>
        </p>
      </form>

      <section className={styles["section"]} aria-labelledby="link-heading">
        <h2 id="link-heading">Albo wyślij sobie link</h2>
        {link.isSuccess ? (
          <InlineNotice tone="success" title="Sprawdź skrzynkę" live="status">
            Jeśli ten adres ma konto albo może je założyć, wysłaliśmy na niego link do logowania. Jest ważny
            przez ograniczony czas i działa raz.
          </InlineNotice>
        ) : (
          <form className={styles["form"]} onSubmit={submitLink} noValidate aria-label="Logowanie linkiem">
            <FormErrorSummary errors={linkShown} attempt={linkAttempt} />
            {linkFailure?.general ? <ProblemNotice key={linkAttempt} problem={linkFailure.general} /> : null}
            <TextField
              fieldId={IDS.linkEmail}
              inputRef={linkField}
              label="Adres e-mail do linku"
              type="email"
              name="link-email"
              autoComplete="email"
              inputMode="email"
              hint="Bez hasła: kliknij link w wiadomości."
              value={linkEmail}
              onValueChange={setLinkEmail}
              error={linkMessage}
            />
            <Button type="submit" fill busy={link.isPending}>
              Wyślij link do logowania
            </Button>
          </form>
        )}
      </section>

      <p className={styles["muted"]}>
        Nie masz konta? <Link to="/signup">Zarejestruj się</Link>
      </p>
    </div>
  );
}
