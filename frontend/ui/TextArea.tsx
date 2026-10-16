import { type ChangeEvent, type Ref, type TextareaHTMLAttributes, useId } from "react";

import { Icon } from "./Icon";
import styles from "./Field.module.css";
import { t } from "../i18n";

export interface TextAreaProps extends Omit<
  TextareaHTMLAttributes<HTMLTextAreaElement>,
  "id" | "className" | "onChange" | "value" | "aria-label"
> {
  /** Always visible: a placeholder is not a label. */
  readonly label: string;
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly hint?: string;
  /** Shown under the field and tied to it (a character counter); announced politely, not on every key. */
  readonly meta?: string;
  /** The message for this field; its presence marks the field invalid and is announced with it. */
  readonly error?: string | null | undefined;
  readonly inputRef?: Ref<HTMLTextAreaElement>;
  readonly fieldId?: string;
}

/**
 * A labelled multi-line field with the same label, hint, error and `aria-describedby` wiring as `TextField`. The
 * value is controlled by the caller and never cleared here.
 */
export function TextArea({
  label,
  value,
  onValueChange,
  hint,
  meta,
  error,
  inputRef,
  fieldId,
  rows = 4,
  ...rest
}: TextAreaProps) {
  const generated = useId();
  const id = fieldId ?? generated;
  const hintId = `${id}-hint`;
  const metaId = `${id}-meta`;
  const errorId = `${id}-error`;
  const describedBy =
    [hint ? hintId : null, meta ? metaId : null, error ? errorId : null].filter(Boolean).join(" ") ||
    undefined;
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
      <textarea
        {...rest}
        ref={inputRef ?? null}
        id={id}
        rows={rows}
        className={styles["input"]}
        value={value}
        onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onValueChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
      {meta ? (
        <p className={styles["hint"]} id={metaId}>
          {meta}
        </p>
      ) : null}
      {error ? (
        <p className={styles["error"]} id={errorId}>
          <Icon name="error" size={16} />
          <span>
            <span className="sr-only">{t.ui.errorPrefix}</span>
            {error}
          </span>
        </p>
      ) : null}
    </div>
  );
}
