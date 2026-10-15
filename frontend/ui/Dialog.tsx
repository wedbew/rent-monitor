import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import type { ReactNode, RefObject } from "react";

import { IconButton } from "./Button";
import styles from "./Dialog.module.css";

export interface DialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  /** The accessible name of the dialog and its visible heading. */
  readonly title: string;
  readonly description?: string;
  /** `drawer` slides from the left edge (mobile navigation); `modal` is centred. */
  readonly variant?: "drawer" | "modal";
  readonly closeLabel?: string;
  /** Called once the close animation has finished. */
  readonly onClosed?: () => void;
  /**
   * Where focus goes on close when the dialog was not opened by a focused trigger (opened by the app, or by a
   * click in Safari, where a clicked button does not take focus). Default: the element focused before opening.
   */
  readonly finalFocus?: RefObject<HTMLElement | null>;
  readonly children: ReactNode;
}

/**
 * Modal dialog on Base UI: focus moves in, is trapped, Escape and a click on the backdrop close it, and focus
 * returns to the trigger (or `finalFocus`). The title names it; the page behind is inert while it is open.
 */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  variant = "modal",
  closeLabel = "Zamknij",
  onClosed,
  finalFocus,
  children,
}: DialogProps) {
  return (
    <BaseDialog.Root
      open={open}
      onOpenChange={onOpenChange}
      {...(onClosed ? { onOpenChangeComplete: (isOpen: boolean) => !isOpen && onClosed() } : {})}
    >
      <BaseDialog.Portal>
        <BaseDialog.Backdrop className={styles["backdrop"]} />
        <BaseDialog.Popup
          className={`${styles["popup"]} ${styles[variant]}`}
          {...(finalFocus ? { finalFocus } : {})}
        >
          <div className={styles["head"]}>
            <BaseDialog.Title className={styles["title"]}>{title}</BaseDialog.Title>
            <BaseDialog.Close render={<IconButton type="button" label={closeLabel} icon="close" />} />
          </div>
          {description ? (
            <BaseDialog.Description className={styles["description"]}>{description}</BaseDialog.Description>
          ) : null}
          {children}
        </BaseDialog.Popup>
      </BaseDialog.Portal>
    </BaseDialog.Root>
  );
}
