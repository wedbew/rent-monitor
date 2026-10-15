import { useState } from "react";
import { Link } from "react-router";

import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError, useFormAttempt } from "../../ui/FormErrors";
import { InlineNotice } from "../../ui/Status";
import { formatCount } from "../../api/format";
import { PageHeading } from "../../shell/PageHeading";
import { emailError, newPasswordError, PASSWORD_MIN, readFailure } from "./forms";
import { GoogleButton } from "./GoogleButton";
import { ProblemNotice } from "./ProblemNotice";
import { useGoogleSignIn, useRegister, useRegisterResend } from "./useAuthMutations";
import styles from "./auth.module.css";
import { t } from "../../i18n";
import { Rich } from "../../i18n/Rich";

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
        <PageHeading title={t.auth.checkInbox} />
        <InlineNotice tone="success" title={t.auth.signup.sentTitle} live="status">
          {t.auth.signup.sentBody({ email: sentTo })}
        </InlineNotice>
        {resend.isSuccess ? (
          <InlineNotice tone="info" title={t.auth.signup.resentTitle} live="status">
            {t.auth.signup.resentBody}
          </InlineNotice>
        ) : null}
        {resendFailure?.general ? <ProblemNotice problem={resendFailure.general} /> : null}
        <div className={styles["links"]}>
          <Button type="button" busy={resend.isPending} onClick={() => resend.mutate(sentTo)}>
            {t.auth.signup.resend}
          </Button>
          <Button type="button" onClick={() => setSentTo(null)}>
            {t.auth.signup.changeAddress}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles["stack"]}>
      <PageHeading title={t.auth.signup.title} lead={t.auth.signup.lead} />
      {googleFailure?.general ? <ProblemNotice problem={googleFailure.general} tone="info" /> : null}
      <GoogleButton text="signup_with" onCredential={(credential) => google.mutate(credential)} />
      <form className={styles["form"]} onSubmit={submit} noValidate aria-label={t.auth.signup.form}>
        <FormErrorSummary errors={shown} attempt={attempt} />
        {failure?.general ? <ProblemNotice key={attempt} problem={failure.general} /> : null}
        <TextField
          fieldId={IDS.email}
          label={t.auth.email}
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
          label={t.auth.password}
          type="password"
          name="new-password"
          autoComplete="new-password"
          hint={t.auth.passwordHint({ min: formatCount(PASSWORD_MIN) })}
          value={password}
          onValueChange={setPassword}
          error={messageFor(IDS.password)}
        />
        <Button type="submit" variant="primary" fill busy={register.isPending} icon="arrow">
          {t.auth.signup.submit}
        </Button>
        <p className={styles["muted"]}>
          <Rich
            parts={t.auth.signup.consent({
              terms: <Link to="/terms">{t.auth.signup.termsLink}</Link>,
              privacy: <Link to="/privacy">{t.auth.signup.privacyLink}</Link>,
            })}
          />
        </p>
      </form>
      <p className={styles["muted"]}>
        <Rich parts={t.auth.signup.haveAccount({ link: <Link to="/login">{t.auth.signIn}</Link> })} />
      </p>
    </div>
  );
}
