import { useState } from "react";

import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { MutationNotice } from "./MutationNotice";
import { useSavedState, useSaveListing, useUnsaveListing } from "./useSaved";
import styles from "./saved.module.css";
import { t } from "../../i18n";

interface SaveToggleProps {
  readonly otodomId: string;
  /** The label on a list row names the listing; on the report page the heading already does. */
  readonly label?: string;
  readonly small?: boolean;
}

/**
 * Save or unsave one listing. A pressed toggle: its name stays, `aria-pressed` carries the state. Not optimistic: the
 * button is busy until the server answers and the state shown is the server's. Unsaving a listing that has a note
 * asks first, because the API removes the note with it. Nothing is shown until the saved state of this listing is
 * known: the list is loaded, and a listing missing from a full (possibly incomplete) list stays unknown. Saving sends
 * no note, so it can never replace one.
 */
export function SaveToggle({
  otodomId,
  label = t.saved.toggle({ id: otodomId }),
  small = false,
}: SaveToggleProps) {
  const state = useSavedState();
  const save = useSaveListing();
  const unsave = useUnsaveListing();
  const [confirming, setConfirming] = useState(false);
  if (state.status !== "ready") return null;
  const item = state.byId.get(otodomId);
  if (item === undefined && state.truncated) return null;
  const saved = item !== undefined;
  const busy = save.isPending || unsave.isPending;
  const failed = save.isError ? save.error : unsave.isError ? unsave.error : null;

  const run = () => {
    if (busy) return;
    save.reset();
    unsave.reset();
    if (!saved) save.mutate({ otodomId });
    else if (item.note !== null && item.note !== "") setConfirming(true);
    else unsave.mutate(otodomId);
  };

  return (
    <div className={styles["toggle"]}>
      <Button
        type="button"
        small={small}
        icon={saved ? "bookmarked" : "bookmark"}
        aria-pressed={saved}
        aria-label={label}
        busy={busy}
        onClick={run}
      >
        {saved ? t.saved.saved : t.saved.save}
      </Button>
      {failed !== null ? <MutationNotice error={failed} /> : null}
      <Dialog
        open={confirming}
        onOpenChange={(open) => {
          if (!unsave.isPending) setConfirming(open);
        }}
        title={t.saved.unsave.title}
        description={t.saved.unsave.body}
      >
        <div className={styles["dialogActions"]}>
          <Button type="button" onClick={() => setConfirming(false)}>
            {t.saved.unsave.cancel}
          </Button>
          <Button
            type="button"
            variant="danger"
            busy={unsave.isPending}
            onClick={() => {
              if (unsave.isPending) return;
              unsave.mutate(otodomId, { onSuccess: () => setConfirming(false) });
            }}
          >
            {t.saved.unsave.confirm}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
