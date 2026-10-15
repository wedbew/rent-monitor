import { Select as BaseSelect } from "@base-ui/react/select";
import { useId } from "react";

import { Icon } from "./Icon";
import fieldStyles from "./Field.module.css";
import styles from "./Select.module.css";
import { t } from "../i18n";

export interface SelectOption {
  readonly value: string;
  readonly label: string;
}

interface SelectProps {
  /** Always visible: the trigger shows the current choice, not what the field is. */
  readonly label: string;
  readonly value: string;
  readonly options: readonly SelectOption[];
  readonly onValueChange: (value: string) => void;
  readonly hint?: string;
  /** The message for this field; its presence marks the field invalid (an error summary can link to `fieldId`). */
  readonly error?: string | null | undefined;
  readonly disabled?: boolean;
  /** Stable id of the trigger (an error summary links to it); generated when omitted. */
  readonly fieldId?: string;
  readonly name?: string;
}

/**
 * A select whose trigger and list are styled by the app (Base UI): the trigger is a labelled combobox button, the
 * list is a listbox in a portal (never clipped by a scrolling parent) with keyboard arrows, typeahead, Escape and
 * focus returned to the trigger. A native select cannot be styled open, and its look differs per browser.
 */
export function Select({
  label,
  value,
  options,
  onValueChange,
  hint,
  error,
  disabled,
  fieldId,
  name,
}: SelectProps) {
  const generated = useId();
  const id = fieldId ?? generated;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={fieldStyles["field"]}>
      <BaseSelect.Root
        items={options as SelectOption[]}
        value={value}
        onValueChange={(next) => {
          if (typeof next === "string") onValueChange(next);
        }}
        disabled={disabled ?? false}
        {...(name !== undefined ? { name } : {})}
      >
        <BaseSelect.Label className={fieldStyles["label"]}>{label}</BaseSelect.Label>
        {hint ? (
          <p className={fieldStyles["hint"]} id={hintId}>
            {hint}
          </p>
        ) : null}
        <BaseSelect.Trigger
          id={id}
          className={styles["trigger"]}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        >
          <BaseSelect.Value className={styles["value"]} />
          <BaseSelect.Icon className={styles["arrow"]}>
            <Icon name="chevronDown" size={18} />
          </BaseSelect.Icon>
        </BaseSelect.Trigger>
        <BaseSelect.Portal>
          <BaseSelect.Positioner className={styles["positioner"]} sideOffset={6} alignItemWithTrigger={false}>
            <BaseSelect.Popup className={styles["popup"]}>
              <BaseSelect.List className={styles["list"]} aria-label={label}>
                {options.map((option) => (
                  <BaseSelect.Item key={option.value} value={option.value} className={styles["item"]}>
                    <BaseSelect.ItemIndicator className={styles["indicator"]}>
                      <Icon name="check" size={16} />
                    </BaseSelect.ItemIndicator>
                    <BaseSelect.ItemText className={styles["itemText"]}>{option.label}</BaseSelect.ItemText>
                  </BaseSelect.Item>
                ))}
              </BaseSelect.List>
            </BaseSelect.Popup>
          </BaseSelect.Positioner>
        </BaseSelect.Portal>
      </BaseSelect.Root>
      {error ? (
        <p className={fieldStyles["error"]} id={errorId}>
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
