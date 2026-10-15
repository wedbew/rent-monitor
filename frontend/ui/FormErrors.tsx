import { useEffect, useRef } from "react";

import styles from "./FormErrors.module.css";

export interface FieldError {
  /** The id of the field (TextField `fieldId`), so the message can link to it. */
  readonly fieldId: string;
  readonly message: string;
}

interface FormErrorSummaryProps {
  readonly errors: readonly FieldError[];
  /** Increments on every failed submit, so the summary takes focus again even if the list is unchanged. */
  readonly submitCount: number;
}

/**
 * After an invalid submit, focus moves here: a heading that says how many things need fixing and links to each
 * field. Screen-reader users hear it (role="alert"); everyone can jump to the first problem.
 */
export function FormErrorSummary({ errors, submitCount }: FormErrorSummaryProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (errors.length > 0) ref.current?.focus();
    // Only a new failed submit moves focus; typing in a field (which edits `errors`) must not steal it.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- submitCount is the trigger by design
  }, [submitCount]);
  if (errors.length === 0) return null;
  return (
    <div ref={ref} className={styles["summary"]} role="alert" tabIndex={-1}>
      <h2>{errors.length === 1 ? "Popraw 1 pole" : `Popraw pola: ${errors.length}`}</h2>
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
