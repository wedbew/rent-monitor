import { type ChangeEvent, type InputHTMLAttributes, type Ref, useId } from "react";

import { Icon } from "./Icon";
import styles from "./Field.module.css";
import { t } from "../i18n";

export interface TextFieldProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "className" | "onChange" | "value" | "aria-label"
> {
  /** Always visible: a placeholder is not a label. */
  readonly label: string;
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly hint?: string;
  /** The message for this field; its presence marks the field invalid and is announced with it. */
  readonly error?: string | null | undefined;
  readonly inputRef?: Ref<HTMLInputElement>;
  /** Stable id (an error summary links to it); generated when omitted. */
  readonly fieldId?: string;
}

/**
 * A labelled text input with an optional hint and error, wired with `aria-describedby`, `aria-invalid` and a
 * visible, textual error (an icon and the word "Błąd", not colour alone). The value is controlled by the caller and
 * is never cleared by a failed submit.
 */
export function TextField({
  label,
  value,
  onValueChange,
  hint,
  error,
  inputRef,
  fieldId,
  ...rest
}: TextFieldProps) {
  const generated = useId();
  const id = fieldId ?? generated;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={styles["field"]}>
      <label className={styles["label"]} htmlFor={id}>
        {label}
      </label>
      {hint ? (
        <p className={styles["hint"]} id={hintId}>
          {hint}
        </p>
      ) : null}
      <input
        {...rest}
        ref={inputRef ?? null}
        id={id}
        className={styles["input"]}
        value={value}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onValueChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
      {error ? (
        <p className={styles["error"]} id={errorId}>
          <Icon name="alert" size={16} />
          <span>
            <span className="sr-only">{t.ui.errorPrefix}</span>
            {error}
          </span>
        </p>
      ) : null}
    </div>
  );
}
