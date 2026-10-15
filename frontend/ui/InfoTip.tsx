import { Popover } from "@base-ui/react/popover";
import { type ReactNode, useRef } from "react";

import { Icon } from "./Icon";
import styles from "./InfoTip.module.css";

interface InfoTipProps {
  /** The accessible name of the trigger: what the help is about ("Co oznacza: roczna stopa zwrotu"). */
  readonly label: string;
  /** The popup's heading. */
  readonly title: string;
  readonly children: ReactNode;
}

/**
 * Help next to a label. A real button that opens a popover: it works with the keyboard (Enter or Space opens,
 * Escape closes and returns focus), with a tap, and with a click; a hover-only tooltip would not reach touch or
 * keyboard users. The popup is portalled, so no scrolling parent clips it.
 */
export function InfoTip({ label, title, children }: InfoTipProps) {
  // Focus goes back to the button however the popover was closed (Escape, a press outside, a touch): left to the
  // default, a touch closes it with focus lost, and a keyboard user is dropped at the top of the page.
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <Popover.Root>
      <Popover.Trigger ref={trigger} className={styles["trigger"]} aria-label={label}>
        <Icon name="help" size={16} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner className={styles["positioner"]} sideOffset={8} collisionPadding={12}>
          {/* A long explanation scrolls inside the popup (`max-height`), so the popup itself must be reachable by keyboard. */}
          <Popover.Popup className={styles["popup"]} finalFocus={trigger} tabIndex={0}>
            <Popover.Title className={styles["title"]}>{title}</Popover.Title>
            <div className={styles["body"]}>{children}</div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
