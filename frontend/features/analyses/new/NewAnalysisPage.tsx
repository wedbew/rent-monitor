import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";

import { formatReports } from "../../../api/format";
import { ApiError } from "../../../api/errors";
import { describeProblem } from "../../../api/problems";
import { PageHeading } from "../../../shell/PageHeading";
import { useMe } from "../../../shell/session";
import { Button, LinkButton } from "../../../ui/Button";
import { Dialog } from "../../../ui/Dialog";
import { TextField } from "../../../ui/Field";
import { FormErrorSummary } from "../../../ui/FormErrors";
import { InlineNotice } from "../../../ui/Status";
import { ProblemNotice } from "../../auth/ProblemNotice";
import { readFailure, retryIn } from "../../auth/forms";
import { reconcileAfterAmbiguousFailure, type Reconciled, useCreateAudit } from "./useCreateAudit";
import styles from "./NewAnalysisPage.module.css";

export const MAX_LISTING_REF = 300; // rm_contracts.audits.MAX_LISTING_REF

/** Only what can be said without asking the server; whether it is an Otodom sale listing is the server's call. */
export function listingRefError(value: string): string | null {
  const ref = value.trim();
  if (ref === "") return "Wklej adres ogłoszenia lub jego numer.";
  if ([...ref].length > MAX_LISTING_REF) return `Adres może mieć najwyżej ${MAX_LISTING_REF} znaków.`;
  return null;
}

const FIELD_ID = "listing-ref";

/**
 * The start of the journey: one URL (or Otodom id), one click, one request. The page never decides money or
 * eligibility: 402, 409, 422 and 429 are the API's answers, shown in words, and the report balance is the server's.
 */
// LEGAL[url-analysis]: accepts a user-supplied Otodom listing URL or id and sends it to the API unchanged (RM-273)
export function NewAnalysisPage() {
  const me = useMe();
  const client = useQueryClient();
  const create = useCreateAudit();
  const [value, setValue] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [submitCount, setSubmitCount] = useState(0);
  const [paywall, setPaywall] = useState(false);
  const [reconciled, setReconciled] = useState<Reconciled | null>(null);
  const busy = create.isPending;

  const breaker = me.upstream.otodom_breaker_open;
  const failure = create.error;
  const code = failure instanceof ApiError ? failure.code : null;
  const fieldError =
    clientError ??
    (code === "INVALID_LISTING_REF" || code === "VALIDATION_ERROR"
      ? (readFailure(failure).fields["listing_ref"] ?? describeProblem("INVALID_LISTING_REF").detail)
      : null);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const problem = listingRefError(value);
    setSubmitCount((n) => n + 1);
    setClientError(problem);
    setReconciled(null);
    if (problem !== null) return;
    const startedAt = Date.now();
    create.mutate(value.trim(), {
      onError: (error) => {
        if (error instanceof ApiError && error.code === "QUOTA_EXHAUSTED") setPaywall(true);
        void reconcileAfterAmbiguousFailure(error, value, startedAt).then(setReconciled);
        void client.invalidateQueries({ queryKey: ["audits"] });
      },
    });
  }

  const summary = fieldError ? [{ fieldId: FIELD_ID, message: fieldError }] : [];

  return (
    <div className={styles["page"]}>
      <PageHeading
        title="Nowa analiza"
        eyebrow="Od ogłoszenia do decyzji"
        lead="Wklej adres ogłoszenia sprzedaży z Otodom. Zobaczysz, ile mieszkanie może zarabiać i do jakiej ceny warto negocjować."
      />

      <div className={styles["modes"]} aria-label="Sposób wprowadzenia">
        <span className={styles["mode"]} aria-current="true">
          Adres z Otodom
        </span>
        <span className={styles["modeSoon"]}>Dane ręcznie · wkrótce</span>
      </div>

      {breaker ? (
        <InlineNotice tone="warning" title="Otodom ogranicza zapytania" live="status">
          Nowe analizy są chwilowo wstrzymane. Spróbuj {retryIn(me.upstream.retry_after_s)}. Raport nie
          zostanie pobrany z konta.
        </InlineNotice>
      ) : (
        <form className={styles["form"]} onSubmit={submit} noValidate>
          <FormErrorSummary errors={summary} submitCount={submitCount} />
          <TextField
            fieldId={FIELD_ID}
            label="Adres ogłoszenia lub numer"
            hint="Na przykład https://www.otodom.pl/pl/oferta/mieszkanie-3-pokoje-ID4abcd. Obsługujemy tylko ogłoszenia sprzedaży."
            value={value}
            onValueChange={(next) => {
              setValue(next);
              setClientError(null);
            }}
            error={fieldError}
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            autoCapitalize="off"
            maxLength={MAX_LISTING_REF * 4}
          />
          {failure !== null && fieldError === null && code !== "QUOTA_EXHAUSTED" ? (
            <FailureNotice error={failure} reconciled={reconciled} />
          ) : null}
          <div className={styles["actions"]}>
            <Button type="submit" variant="primary" icon="arrow" busy={busy}>
              Rozpocznij analizę
            </Button>
            <p className={styles["cost"]}>
              Analiza zużywa 1 raport, ale tylko gdy się uda. Na koncie: {formatReports(me.credit_balance)}.
            </p>
          </div>
        </form>
      )}

      <Dialog
        open={paywall}
        onOpenChange={setPaywall}
        title="Nie masz już raportów"
        description="Kup pakiet raportów, aby przeanalizować to ogłoszenie. Nic nie zostało pobrane."
        closeLabel="Zamknij okno"
      >
        <div className={styles["paywall"]}>
          <LinkButton to="/app/credits" variant="primary" icon="arrow">
            Kup raporty
          </LinkButton>
        </div>
      </Dialog>
    </div>
  );
}

function FailureNotice({
  error,
  reconciled,
}: {
  readonly error: unknown;
  readonly reconciled: Reconciled | null;
}) {
  if (reconciled !== null && "found" in reconciled) {
    return (
      <InlineNotice
        tone="success"
        title="Analiza tego ogłoszenia już istnieje"
        live="status"
        actions={
          <LinkButton to={`/app/analyses/${reconciled.found.auditId}`} variant="primary" icon="arrow">
            Zobacz postęp
          </LinkButton>
        }
      >
        Połączenie przerwało się, ale ta analiza została przyjęta. Nie wysyłaj jej drugi raz.
      </InlineNotice>
    );
  }
  if (reconciled !== null) {
    return (
      <InlineNotice
        tone="warning"
        title="Nie wiemy, czy analiza ruszyła"
        live="alert"
        actions={
          <Link to="/app/analyses" className={styles["link"]}>
            Sprawdź w Moich analizach
          </Link>
        }
      >
        Połączenie przerwało się i nie możemy tego rozstrzygnąć. Zanim spróbujesz ponownie, sprawdź listę
        analiz, żeby nie zapłacić dwa razy.
      </InlineNotice>
    );
  }
  if (error instanceof ApiError && error.code === "AUDIT_IN_PROGRESS") {
    const existing = (error.problem as unknown as Record<string, unknown> | null)?.["audit_id"];
    return (
      <InlineNotice
        tone="info"
        title="Ta analiza już trwa"
        live="status"
        actions={
          typeof existing === "string" ? (
            <LinkButton to={`/app/analyses/${existing}`} variant="primary" icon="arrow">
              Otwórz analizę
            </LinkButton>
          ) : undefined
        }
      >
        Dla tego ogłoszenia analiza jest już w toku. Drugi raport nie zostanie pobrany.
      </InlineNotice>
    );
  }
  const read = readFailure(error);
  return read.general === null ? null : <ProblemNotice problem={read.general} />;
}
