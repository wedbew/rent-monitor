import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import type { UseMutationResult } from "@tanstack/react-query";

import { PageHeading } from "../../shell/PageHeading";
import { LinkButton } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import { readFailure } from "./forms";
import { ProblemNotice } from "./ProblemNotice";
import { clearCapturedToken, readCapturedToken } from "./token";
import { useMagicLinkVerify, useRegisterVerify } from "./useAuthMutations";
import styles from "./auth.module.css";

interface TokenPageProps {
  readonly title: string;
  readonly verifying: string;
  readonly mutation: UseMutationResult<unknown, Error, string>;
  /** What to offer when the link does not work. */
  readonly retry: { readonly to: string; readonly label: string };
  /** A code that has its own explanation (an account that already exists). */
  readonly special?: {
    readonly code: string;
    readonly title: string;
    readonly body: string;
    readonly to: string;
    readonly label: string;
  };
}

/**
 * A page opened from a mailed link: it reads the one-time token captured at boot (never from storage), spends it
 * exactly once (a token is single-use, so React's double effect must not call twice), and says what happened. On
 * success the mutation hook signs the person in and navigates away.
 */
function TokenPage({ title, verifying, mutation, retry, special }: TokenPageProps) {
  const [token] = useState(readCapturedToken);
  const started = useRef(false);
  const { mutate } = mutation;

  useEffect(() => {
    if (token === null || started.current) return;
    started.current = true;
    mutate(token);
  }, [token, mutate]);

  useEffect(() => clearCapturedToken, []);

  const failure = mutation.isError ? readFailure(mutation.error) : null;
  const isSpecial = special !== undefined && failure?.code === special.code;

  return (
    <div className={styles["stack"]}>
      <PageHeading title={title} />
      {token === null ? (
        <InlineNotice tone="danger" title="Ten link jest niepełny" live="alert">
          Otwórz link z wiadomości jeszcze raz w całości albo poproś o nowy.
        </InlineNotice>
      ) : mutation.isError ? (
        isSpecial ? (
          <InlineNotice tone="info" title={special.title} live="alert">
            {special.body}
          </InlineNotice>
        ) : failure?.general ? (
          <ProblemNotice problem={failure.general} />
        ) : null
      ) : (
        <p role="status" aria-live="polite">
          {verifying}
        </p>
      )}
      {token === null || mutation.isError ? (
        <div className={styles["links"]}>
          {isSpecial ? (
            <LinkButton to={special.to} variant="primary" icon="arrow">
              {special.label}
            </LinkButton>
          ) : null}
          <LinkButton to={retry.to} {...(isSpecial ? {} : { variant: "primary" as const })} icon="arrow">
            {retry.label}
          </LinkButton>
        </div>
      ) : null}
      <p className={styles["muted"]}>
        <Link to="/login">Wróć do logowania</Link>
      </p>
    </div>
  );
}

/** `/login/email#t=...`: the link from "send me a sign-in link". */
export function EmailLinkPage() {
  const mutation = useMagicLinkVerify();
  return (
    <TokenPage
      title="Logowanie linkiem"
      verifying="Sprawdzam link i loguję Cię…"
      mutation={mutation}
      retry={{ to: "/login", label: "Poproś o nowy link" }}
    />
  );
}

/** `/signup/verify#t=...`: the link that creates the account. */
export function VerifySignupPage() {
  const mutation = useRegisterVerify();
  return (
    <TokenPage
      title="Potwierdzenie adresu e-mail"
      verifying="Potwierdzam adres i zakładam konto…"
      mutation={mutation}
      retry={{ to: "/signup", label: "Zarejestruj się ponownie" }}
      special={{
        code: "ACCOUNT_EXISTS",
        title: "Masz już konto z tym adresem",
        body: "Zaloguj się hasłem albo ustaw nowe, jeśli go nie pamiętasz.",
        to: "/login",
        label: "Zaloguj się",
      }}
    />
  );
}
