import { type FormEvent, useState } from "react";

import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError, useFormAttempt } from "../../ui/FormErrors";
import { Select } from "../../ui/Select";
import { TextArea } from "../../ui/TextArea";
import { InlineNotice } from "../../ui/Status";
import { FailureNotice, parseMoneyInput } from "./common";
import { type Brief, type ProjectOut, useUpdateProject } from "./hooks";
import { roomOptions, type Room } from "./InteriorPage";
import styles from "./interior.module.css";
import { t } from "../../i18n";

const MAX_KEEP = 10;
const MAX_NOTES = 2000;
const IDS = { name: "brief-name", budget: "brief-budget", keep: "brief-keep", notes: "brief-notes" } as const;

/** The unit the budget field is typed in: a decimal in złoty; the server stores it exactly. */
function budgetText(value: string | null | undefined): string {
  return value === null || value === undefined ? "" : value.replace(".", ",").replace(/,00$/, "");
}

/** What can be said without asking the server; the server still decides (a 422 is shown on the form as well). */
export function briefErrors(input: {
  name: string;
  budget: string;
  keep: string[];
  notes: string;
}): Record<string, string> {
  const errors: Record<string, string> = {};
  if (input.name.trim() === "") errors[IDS.name] = t.interior.brief.nameMissing;
  if (input.budget.trim() !== "" && parseMoneyInput(input.budget) === null)
    errors[IDS.budget] = t.interior.brief.budgetInvalid;
  if (input.keep.length > MAX_KEEP) errors[IDS.keep] = t.interior.brief.keepTooMany;
  if ([...input.notes].length > MAX_NOTES) errors[IDS.notes] = t.interior.brief.notesTooLong;
  return errors;
}

/**
 * The brief and the project's name. Saving keeps the 30-day lifetime (the server never extends it). The budget is a
 * comparison limit the person chose, not a cost of the room, and is sent as an exact decimal string.
 */
export function BriefPanel({ project }: { readonly project: ProjectOut }) {
  const update = useUpdateProject();
  const [name, setName] = useState(project.name);
  const [room, setRoom] = useState<Room>(project.brief.room_type);
  const [style, setStyle] = useState(project.brief.style ?? "");
  const [budget, setBudget] = useState(budgetText(project.brief.budget_pln));
  const [keep, setKeep] = useState((project.brief.keep ?? []).join("\n"));
  const [notes, setNotes] = useState(project.brief.notes ?? "");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [attempt, markInvalid] = useFormAttempt();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (update.isPending) return;
    const keepLines = keep
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line !== "");
    const found = briefErrors({ name, budget, keep: keepLines, notes });
    setErrors(found);
    setSaved(false);
    if (Object.keys(found).length > 0) {
      markInvalid();
      return;
    }
    const brief: Brief = {
      room_type: room,
      keep: keepLines,
      ...(style.trim() === "" ? {} : { style: style.trim() }),
      ...(budget.trim() === "" ? {} : { budget_pln: parseMoneyInput(budget) ?? "0" }),
      ...(notes.trim() === "" ? {} : { notes: notes.trim() }),
    };
    update.mutate(
      { projectId: project.project_id, name: name.trim(), brief },
      { onSuccess: () => setSaved(true), onError: () => markInvalid() },
    );
  }

  const summary: FieldError[] = Object.entries(errors).map(([fieldId, message]) => ({ fieldId, message }));
  return (
    <section className={styles["panel"]} aria-labelledby="interior-brief">
      <h2 className={styles["h2"]} id="interior-brief">
        {t.interior.brief.title}
      </h2>
      <p className={styles["muted"]}>{t.interior.brief.lead}</p>
      <form className={styles["form"]} onSubmit={submit} noValidate>
        <FormErrorSummary errors={summary} attempt={attempt} />
        <TextField
          fieldId={IDS.name}
          label={t.interior.brief.name}
          value={name}
          onValueChange={setName}
          error={errors[IDS.name]}
          maxLength={120}
          autoComplete="off"
        />
        <Select
          label={t.interior.brief.room}
          value={room}
          options={roomOptions}
          onValueChange={(next) => setRoom(next as Room)}
        />
        <TextField
          label={t.interior.brief.style}
          hint={t.interior.brief.styleHint}
          value={style}
          onValueChange={setStyle}
          maxLength={80}
          autoComplete="off"
        />
        <TextField
          fieldId={IDS.budget}
          label={t.interior.brief.budget}
          hint={t.interior.brief.budgetHint}
          value={budget}
          onValueChange={setBudget}
          error={errors[IDS.budget]}
          inputMode="decimal"
          autoComplete="off"
        />
        <TextArea
          fieldId={IDS.keep}
          label={t.interior.brief.keep}
          hint={t.interior.brief.keepHint}
          value={keep}
          onValueChange={setKeep}
          error={errors[IDS.keep]}
          rows={3}
        />
        <TextArea
          fieldId={IDS.notes}
          label={t.interior.brief.notes}
          hint={t.interior.brief.notesHint}
          value={notes}
          onValueChange={setNotes}
          error={errors[IDS.notes]}
          rows={4}
        />
        {update.isError ? <FailureNotice error={update.error} /> : null}
        {saved && !update.isPending ? (
          <InlineNotice tone="success" title={t.interior.brief.saved} live="status" />
        ) : null}
        <div className={styles["actions"]}>
          <Button type="submit" variant="primary" busy={update.isPending}>
            {t.interior.brief.save}
          </Button>
        </div>
      </form>
    </section>
  );
}
