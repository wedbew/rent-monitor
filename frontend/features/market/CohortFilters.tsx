import { useId, useState } from "react";

import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { cohortLabel, familyOf, ROOMS_KEYS, SIZE_KEYS } from "./cohorts";
import type { CohortKey } from "./filters";
import styles from "./filters.module.css";

interface Props {
  readonly value: CohortKey;
  readonly onChange: (next: CohortKey) => void;
  /** The answer for the new group is on its way. */
  readonly busy?: boolean;
}

function Group({
  name,
  legend,
  keys,
  value,
  onPick,
}: {
  readonly name: string;
  readonly legend: string;
  readonly keys: readonly CohortKey[];
  readonly value: CohortKey;
  readonly onPick: (key: CohortKey) => void;
}) {
  return (
    <fieldset className={styles["group"]}>
      <legend className={styles["legend"]}>{legend}</legend>
      <div className={styles["chips"]}>
        {keys.map((key) => (
          <label key={key} className={styles["chip"]}>
            <input
              type="radio"
              name={name}
              value={key}
              checked={value === key}
              onChange={() => onPick(key)}
              className={styles["radio"]}
            />
            <span>{cohortLabel(key)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/**
 * The apartment filter of Rynek: "Powierzchnia mieszkania" and "Liczba pokoi", each a labelled group of radio
 * chips (a visible label and an accessible name on every control). One group at a time, because the source
 * publishes statistics per area group and per rooms group but not for their combination; choosing from one family
 * replaces the other and the page says so in words. The reset clears the choice and nothing else (the map view, the
 * selected place and the comparison stay).
 */
export function CohortFilters({ value, onChange, busy = false }: Props) {
  const headingId = useId();
  const [replaced, setReplaced] = useState<string | null>(null);

  const pick = (next: CohortKey) => {
    const was = value;
    const crossed = familyOf(was) !== null && familyOf(next) !== null && familyOf(was) !== familyOf(next);
    setReplaced(
      crossed ? t.rynek.filters.exclusiveNote({ was: cohortLabel(was), now: cohortLabel(next) }) : null,
    );
    onChange(next);
  };

  return (
    <section className={styles["panel"]} aria-labelledby={headingId} data-testid="cohort-filters">
      <div className={styles["head"]}>
        <h2 id={headingId} className={styles["heading"]}>
          {t.rynek.filters.heading}
        </h2>
        <p className={styles["lead"]}>{t.rynek.filters.lead}</p>
      </div>
      <div className={styles["groups"]}>
        <Group
          name="cohort-area"
          legend={t.rynek.filters.area}
          keys={SIZE_KEYS}
          value={value}
          onPick={pick}
        />
        <Group
          name="cohort-rooms"
          legend={t.rynek.filters.rooms}
          keys={ROOMS_KEYS}
          value={value}
          onPick={pick}
        />
      </div>
      <details className={styles["rules"]}>
        <summary>{t.rynek.filters.rulesToggle}</summary>
        <p className={styles["rule"]}>{t.rynek.filters.boundary}</p>
        <p className={styles["rule"]}>{t.rynek.filters.exclusive}</p>
      </details>
      <div className={styles["summary"]}>
        <p className={styles["active"]} role="status" aria-busy={busy}>
          {busy
            ? t.rynek.filters.loading
            : value === "all"
              ? t.rynek.filters.none
              : t.rynek.filters.active({ filter: cohortLabel(value) })}
        </p>
        {value === "all" ? null : (
          <Button
            type="button"
            small
            onClick={() => {
              setReplaced(null);
              onChange("all");
            }}
          >
            {t.rynek.filters.reset}
          </Button>
        )}
      </div>
      <p className={styles["replaced"]} role="status">
        {replaced}
      </p>
    </section>
  );
}
