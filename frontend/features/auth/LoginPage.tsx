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
import { t } from "../../i18n";
import { Rich } from "../../i18n/Rich";

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
      <PageHeading title={t.auth.login.title} lead={t.auth.login.lead} />

      {googleFailure?.general ? (
        <ProblemNotice
          problem={googleFailure.general}
          tone={needsLink ? "info" : "danger"}
          actions={
            needsLink ? (
              <Button type="button" onClick={() => linkField.current?.focus()}>
                {t.auth.login.useEmailLink}
              </Button>
            ) : undefined
          }
        />
      ) : null}
      <GoogleButton text="signin_with" onCredential={(credential) => google.mutate(credential)} />

      <form
        className={styles["form"]}
        onSubmit={submitPassword}
        noValidate
        aria-label={t.auth.login.passwordForm}
      >
        <FormErrorSummary errors={shown} attempt={attempt} />
        {loginFailure?.general ? <ProblemNotice key={attempt} problem={loginFailure.general} /> : null}
        <TextField
          fieldId={IDS.email}
          label={t.auth.email}
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
          label={t.auth.password}
          type="password"
          name="password"
          autoComplete="current-password"
          value={password}
          onValueChange={setPassword}
          error={fieldMessage(IDS.password)}
        />
        <Button type="submit" variant="primary" fill busy={login.isPending} icon="arrow">
          {t.auth.signIn}
        </Button>
        <p className={styles["links"]}>
          <Link to="/password/forgot">{t.auth.login.forgot}</Link>
        </p>
      </form>

      <section className={styles["section"]} aria-labelledby="link-heading">
        <h2 id="link-heading">{t.auth.login.linkHeading}</h2>
        {link.isSuccess ? (
          <InlineNotice tone="success" title={t.auth.checkInbox} live="status">
            {t.auth.login.linkSentBody}
          </InlineNotice>
        ) : (
          <form
            className={styles["form"]}
            onSubmit={submitLink}
            noValidate
            aria-label={t.auth.login.linkForm}
          >
            <FormErrorSummary errors={linkShown} attempt={linkAttempt} />
            {linkFailure?.general ? <ProblemNotice key={linkAttempt} problem={linkFailure.general} /> : null}
            <TextField
              fieldId={IDS.linkEmail}
              inputRef={linkField}
              label={t.auth.login.linkEmail}
              type="email"
              name="link-email"
              autoComplete="email"
              inputMode="email"
              hint={t.auth.login.linkHint}
              value={linkEmail}
              onValueChange={setLinkEmail}
              error={linkMessage}
            />
            <Button type="submit" fill busy={link.isPending}>
              {t.auth.login.sendLink}
            </Button>
          </form>
        )}
      </section>

      <p className={styles["muted"]}>
        <Rich parts={t.auth.login.noAccount({ link: <Link to="/signup">{t.auth.login.signUpLink}</Link> })} />
      </p>
    </div>
  );
}
