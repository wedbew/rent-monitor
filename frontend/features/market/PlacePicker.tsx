import { useState } from "react";

import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { matchesName } from "./explore";
import styles from "./gus.module.css";

interface Props {
  readonly places: readonly { readonly id: string; readonly name: string }[];
  readonly label: string;
  readonly hint?: string;
  readonly selectedId: string | null;
  readonly onPick: (id: string) => void;
}

/** A search over the places (the catalogue is too long for a select): the best matches as buttons. */
export function PlacePicker({ places, label, hint, selectedId, onPick }: Props) {
  const [search, setSearch] = useState("");
  const results = places.filter((p) => matchesName(p.name, search)).slice(0, 8);
  return (
    <div className={styles["picker"]}>
      <TextField
        label={label}
        {...(hint === undefined ? {} : { hint })}
        value={search}
        onValueChange={setSearch}
        autoComplete="off"
        spellCheck={false}
        maxLength={60}
      />
      {results.length === 0 ? (
        <p className={styles["muted"]}>{t.rynek.compare.pickerEmpty}</p>
      ) : (
        <ul className={styles["chips"]}>
          {results.map((p) => (
            <li key={p.id}>
              <Button type="button" small aria-pressed={p.id === selectedId} onClick={() => onPick(p.id)}>
                {p.name}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
