import { useEffect, useState } from "react";
import { useBlocker } from "react-router";

import { formatCount } from "../../api/format";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { InlineNotice } from "../../ui/Status";
import { TextArea } from "../../ui/TextArea";
import { type SavedItem, NOTE_MAX, noteLength } from "./items";
import { MutationNotice } from "./MutationNotice";
import { useSaveListing } from "./useSaved";
import styles from "./saved.module.css";
import { t } from "../../i18n";

/**
 * The private note of a saved listing. The draft is the person's until they save it; leaving the page with an unsaved
 * draft asks first (in-app navigation and closing the tab). A note that changed on the server replaces a clean
 * draft and never one being edited. An empty note is stored as no note.
 */
export function NoteEditor({ item }: { readonly item: SavedItem }) {
  const save = useSaveListing();
  const stored = item.note ?? "";
  const [draft, setDraft] = useState(stored);
  // The stored note changed (our own save, or another tab): a clean draft follows it, a draft being edited stays.
  const [seen, setSeen] = useState(stored);
  if (stored !== seen) {
    setSeen(stored);
    if (draft === seen) setDraft(stored);
  }
  const [tooLong, setTooLong] = useState(false);
  const dirty = draft !== stored;
  const used = noteLength(draft);

  const blocker = useBlocker(dirty);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (save.isPending) return;
    if (used > NOTE_MAX) {
      setTooLong(true);
      return;
    }
    setTooLong(false);
    save.mutate({ otodomId: item.otodomId, note: draft === "" ? null : draft });
  };

  return (
    <form className={styles["note"]} onSubmit={submit} noValidate aria-label={t.saved.note.label}>
      <TextArea
        label={t.saved.note.label}
        hint={t.saved.note.hint}
        meta={t.saved.note.counter({ used: formatCount(used), max: formatCount(NOTE_MAX) })}
        value={draft}
        onValueChange={(value) => {
          setDraft(value);
          setTooLong(false);
          if (save.isSuccess || save.isError) save.reset();
        }}
        error={tooLong || used > NOTE_MAX ? t.saved.note.tooLong({ max: formatCount(NOTE_MAX) }) : null}
      />
      {dirty ? <p className={styles["dirty"]}>{t.saved.note.unsaved}</p> : null}
      {save.isError ? <MutationNotice error={save.error} /> : null}
      {save.isSuccess && !dirty ? (
        <InlineNotice tone="success" title={t.saved.note.saved} live="status" />
      ) : null}
      <div>
        <Button type="submit" variant="primary" busy={save.isPending}>
          {t.saved.note.save}
        </Button>
      </div>
      <Dialog
        open={blocker.state === "blocked"}
        onOpenChange={(open) => {
          if (!open && blocker.state === "blocked") blocker.reset();
        }}
        title={t.saved.note.leaveTitle}
        description={t.saved.note.leaveBody}
      >
        <div className={styles["dialogActions"]}>
          <Button
            type="button"
            variant="primary"
            onClick={() => blocker.state === "blocked" && blocker.reset()}
          >
            {t.saved.note.stay}
          </Button>
          <Button
            type="button"
            variant="danger"
            onClick={() => blocker.state === "blocked" && blocker.proceed()}
          >
            {t.saved.note.leave}
          </Button>
        </div>
      </Dialog>
    </form>
  );
}
