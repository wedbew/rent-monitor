import { InlineNotice } from "../../ui/Status";
import { NoteEditor } from "./NoteEditor";
import { SaveToggle } from "./SaveToggle";
import { useSavedState } from "./useSaved";
import styles from "./saved.module.css";
import { t } from "../../i18n";

/** On a finished report: save the listing and, once saved, keep a private note with it. */
// GDPR[personal-data]: the note is free text written by the person, shown and sent to its owner only (RM-276)
export function SavedPanel({ otodomId }: { readonly otodomId: string }) {
  const state = useSavedState();
  const item = state.status === "ready" ? state.byId.get(otodomId) : undefined;
  return (
    <section className={styles["panel"]} aria-label={t.saved.panel}>
      {state.status === "error" ? (
        <InlineNotice tone="warning" title={t.saved.list.failed} live="status" />
      ) : (
        <SaveToggle otodomId={otodomId} label={t.saved.toggleReport} />
      )}
      {item !== undefined ? <NoteEditor item={item} /> : null}
    </section>
  );
}
