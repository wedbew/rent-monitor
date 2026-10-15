import { type ChangeEvent, type SelectHTMLAttributes, useId } from "react";

import styles from "./Field.module.css";

export interface SelectOption {
  readonly value: string;
  readonly label: string;
}

interface SelectProps extends Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  "id" | "className" | "onChange" | "value" | "aria-label"
> {
  readonly label: string;
  readonly value: string;
  readonly options: readonly SelectOption[];
  readonly onValueChange: (value: string) => void;
}

/** A native select with a visible label: the platform's own keyboard, touch and screen-reader behaviour. */
export function Select({ label, value, options, onValueChange, ...rest }: SelectProps) {
  const id = useId();
  return (
    <div className={styles["field"]}>
      <label className={styles["label"]} htmlFor={id}>
        {label}
      </label>
      <select
        {...rest}
        id={id}
        className={styles["input"]}
        value={value}
        onChange={(event: ChangeEvent<HTMLSelectElement>) => onValueChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
