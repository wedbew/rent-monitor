import { useEffect, useState } from "react";
import { Link } from "react-router";

import { formatCount } from "../../api/format";
import { PageHeading } from "../../shell/PageHeading";
import { Button, LinkButton } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError, useFormAttempt } from "../../ui/FormErrors";
import { InlineNotice } from "../../ui/Status";
import { emailError, newPasswordError, PASSWORD_MIN, readFailure } from "./forms";
import { ProblemNotice } from "./ProblemNotice";
import { clearCapturedToken, readCapturedToken } from "./token";
import { usePasswordForgot, usePasswordReset } from "./useAuthMutations";
import styles from "./auth.module.css";
import { t } from "../../i18n";

const FORGOT_EMAIL_ID = "forgot-email";

/** `/password/forgot`: always answers the same, whether or not the address has an account. */
export function ForgotPasswordPage() {
  const forgot = usePasswordForgot();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [attempt, markInvalid] = useFormAttempt();

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const problem = emailError(email);
    setError(problem);
    if (problem !== null) {
      markInvalid();
      return;
    }
    forgot.mutate(email.trim(), { onError: markInvalid });
  };
  const failure = forgot.isError ? readFailure(forgot.error) : null;
  const message = error ?? failure?.fields["email"] ?? null;
  const shown: FieldError[] = message ? [{ fieldId: FORGOT_EMAIL_ID, message }] : [];

  return (
    <div className={styles["stack"]}>
      <PageHeading title={t.auth.forgot.title} lead={t.auth.forgot.lead} />
      {forgot.isSuccess ? (
        <InlineNotice tone="success" title={t.auth.checkInbox} live="status">
          {t.auth.forgot.sentBody}
        </InlineNotice>
      ) : (
        <form className={styles["form"]} onSubmit={submit} noValidate aria-label={t.auth.forgot.form}>
          <FormErrorSummary errors={shown} attempt={attempt} />
          {failure?.general ? <ProblemNotice key={attempt} problem={failure.general} /> : null}
          <TextField
            fieldId={FORGOT_EMAIL_ID}
            label={t.auth.email}
            type="email"
            name="email"
            autoComplete="email"
            inputMode="email"
            value={email}
            onValueChange={setEmail}
            error={message}
          />
          <Button type="submit" variant="primary" fill busy={forgot.isPending} icon="arrow">
            {t.auth.forgot.submit}
          </Button>
        </form>
      )}
      <p className={styles["muted"]}>
        <Link to="/login">{t.auth.backToLogin}</Link>
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
  const [attempt, markInvalid] = useFormAttempt();

  useEffect(() => clearCapturedToken, []);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (token === null) return;
    const problem = newPasswordError(password);
    const found = problem ? [{ fieldId: PASSWORD_ID, message: problem }] : [];
    setErrors(found);
    if (found.length > 0) {
      markInvalid();
      return;
    }
    reset.mutate({ token, password }, { onError: markInvalid });
  };

  const failure = reset.isError ? readFailure(reset.error) : null;
  const serverError = failure?.fields["password"];
  const shown =
    errors.length > 0 ? errors : serverError ? [{ fieldId: PASSWORD_ID, message: serverError }] : [];
  const invalidLink = token === null || failure?.code === "AUTH_TOKEN_INVALID";

  if (reset.isSuccess) {
    return (
      <div className={styles["stack"]}>
        <PageHeading title={t.auth.reset.doneTitle} />
        <InlineNotice tone="success" title={t.auth.reset.doneNotice} live="status">
          {t.auth.reset.doneBody}
        </InlineNotice>
        <LinkButton to="/login" variant="primary" icon="arrow">
          {t.auth.signIn}
        </LinkButton>
      </div>
    );
  }

  return (
    <div className={styles["stack"]}>
      <PageHeading title={t.auth.reset.title} />
      {invalidLink ? (
        <>
          <InlineNotice tone="danger" title={t.auth.reset.invalidTitle} live="alert">
            {t.auth.reset.invalidBody}
          </InlineNotice>
          <LinkButton to="/password/forgot" variant="primary" icon="arrow">
            {t.auth.reset.requestNew}
          </LinkButton>
        </>
      ) : (
        <form className={styles["form"]} onSubmit={submit} noValidate aria-label={t.auth.reset.form}>
          <FormErrorSummary errors={shown} attempt={attempt} />
          {failure?.general ? <ProblemNotice key={attempt} problem={failure.general} /> : null}
          <TextField
            fieldId={PASSWORD_ID}
            label={t.auth.reset.newPassword}
            type="password"
            name="new-password"
            autoComplete="new-password"
            hint={t.auth.passwordHint({ min: formatCount(PASSWORD_MIN) })}
            value={password}
            onValueChange={setPassword}
            error={shown[0]?.message}
          />
          <Button type="submit" variant="primary" fill busy={reset.isPending} icon="arrow">
            {t.auth.reset.submit}
          </Button>
        </form>
      )}
      <p className={styles["muted"]}>
        <Link to="/login">{t.auth.backToLogin}</Link>
      </p>
    </div>
  );
}
