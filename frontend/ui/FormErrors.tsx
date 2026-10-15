import { useCallback, useEffect, useRef, useState } from "react";

import styles from "./FormErrors.module.css";

/** ui/ knows nothing of api/: the count is still laid out by Intl, in the app's locale. */
const COUNT = new Intl.NumberFormat("pl-PL", { useGrouping: "always" });

export interface FieldError {
  /** The id of the field (TextField `fieldId`), so the message can link to it. */
  readonly fieldId: string;
  readonly message: string;
}

/**
 * The one error contract for every form (audit F12). `attempt` changes each time a submit ENDS invalid: at once
 * for a client check, and when the server's answer arrives for a server one (call `markInvalid` in the mutation's
 * `onError`), never when the request merely starts. The summary takes focus on that change only, so typing never
 * steals focus; a general problem notice keyed by `attempt` is re-announced even when its text repeats.
 */
export function useFormAttempt(): readonly [attempt: number, markInvalid: () => void] {
  const [attempt, setAttempt] = useState(0);
  const markInvalid = useCallback(() => setAttempt((n) => n + 1), []);
  return [attempt, markInvalid];
}

interface FormErrorSummaryProps {
  /** Client and server field errors together: one list, one place to hear and fix them. */
  readonly errors: readonly FieldError[];
  /** From `useFormAttempt`: the summary takes focus again on every invalid result, even if the list is unchanged. */
  readonly attempt: number;
}

/**
 * After an invalid submit, focus moves here: a heading that says how many things need fixing and links to each
 * field. Screen-reader users hear it (role="alert"); everyone can jump to the first problem.
 */
export function FormErrorSummary({ errors, attempt }: FormErrorSummaryProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (attempt > 0 && errors.length > 0) ref.current?.focus();
    // Only a new invalid result moves focus; typing in a field (which edits `errors`) must not steal it.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- attempt is the trigger by design
  }, [attempt]);
  if (errors.length === 0) return null;
  return (
    <div ref={ref} className={styles["summary"]} role="alert" tabIndex={-1}>
      <h2>{errors.length === 1 ? "Popraw 1 pole" : `Popraw pola: ${COUNT.format(errors.length)}`}</h2>
      <ul>
        {errors.map((error) => (
          <li key={error.fieldId}>
            <a
              href={`#${error.fieldId}`}
              onClick={(event) => {
                event.preventDefault();
                document.getElementById(error.fieldId)?.focus();
              }}
            >
              {error.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
