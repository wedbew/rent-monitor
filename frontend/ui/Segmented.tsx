import { Icon, type IconName } from "./Icon";
import styles from "./Segmented.module.css";

export interface SegmentOption<T extends string> {
  readonly value: T;
  readonly label: string;
  readonly icon?: IconName;
}

interface SegmentedProps<T extends string> {
  /** The accessible name of the group ("Widok"). */
  readonly label: string;
  readonly value: T;
  readonly options: readonly SegmentOption<T>[];
  readonly onValueChange: (value: T) => void;
}

/**
 * A compact switch between a few views of the same data. Each segment is a real button that says whether it is
 * pressed (`aria-pressed`), so the current choice is read, not only seen; the pressed one also looks different by
 * more than colour (filled ground, bolder text).
 */
export function Segmented<T extends string>({ label, value, options, onValueChange }: SegmentedProps<T>) {
  return (
    <div className={styles["group"]} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={styles["segment"]}
          aria-pressed={option.value === value}
          onClick={() => {
            if (option.value !== value) onValueChange(option.value);
          }}
        >
          {option.icon ? <Icon name={option.icon} size={16} /> : null}
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );
}
