import { type MouseEvent, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { IconButton } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { AccountBlock } from "./AccountBlock";
import { LEGAL, PRIMARY } from "./navigation";
import { NavList } from "./NavList";
import { useSession } from "./session";
import styles from "./MobileMenu.module.css";
import { t } from "../i18n";

const isPlainLeftClick = (event: MouseEvent) =>
  event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

/**
 * Navigation for narrow screens: a sheet from the same registry as the rail. It is a modal dialog (focus trapped,
 * Escape and backdrop close it). Following a link closes the sheet FIRST, lets it hand focus back, and only then
 * navigates, so the shell's route focus (the new page's heading) is the last thing that moves focus; navigating
 * while the sheet closes would race with the dialog restoring focus to the trigger. Modified clicks (new tab) are
 * left to the browser.
 */
export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const session = useSession();
  const pending = useRef<string | null>(null);

  // Any route change not started by the sheet (back button, a link elsewhere) also closes it. State that follows a
  // prop is adjusted while rendering, not in an effect (react.dev: "You might not need an effect").
  const [shownAt, setShownAt] = useState(pathname);
  if (shownAt !== pathname) {
    setShownAt(pathname);
    setOpen(false);
  }

  const follow = (to: string, event: MouseEvent) => {
    if (!isPlainLeftClick(event)) return;
    event.preventDefault();
    pending.current = to;
    setOpen(false);
  };

  return (
    <>
      <IconButton
        type="button"
        icon="menu"
        aria-haspopup="dialog"
        aria-expanded={open}
        label={t.shell.openMenu}
        title={t.shell.openMenu}
        onClick={() => setOpen(true)}
      />
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={t.shell.navigationTitle}
        variant="drawer"
        closeLabel={t.shell.closeNavigation}
        onClosed={() => {
          const to = pending.current;
          pending.current = null;
          if (to !== null) void navigate(to);
        }}
      >
        <div className={styles["sections"]}>
          <NavList label={t.shell.mobileNavigation} destinations={PRIMARY} size="sheet" onFollow={follow} />
          <NavList label={t.shell.documents} destinations={LEGAL} size="sheet" onFollow={follow} />
          {session.status === "signedIn" ? <AccountBlock /> : null}
        </div>
      </Dialog>
    </>
  );
}
