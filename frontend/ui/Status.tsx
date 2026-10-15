import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";
import styles from "./Status.module.css";

export type Tone = "info" | "success" | "warning" | "danger";

const ICONS: Record<Tone, IconName> = { info: "info", success: "check", warning: "alert", danger: "alert" };

interface InlineNoticeProps {
  readonly tone: Tone;
  readonly title: string;
  readonly children?: ReactNode;
  /** Buttons or links; the notice does not decide what they do. */
  readonly actions?: ReactNode;
  /** `alert` interrupts (errors the user must see now); `status` is polite. Default: polite. */
  readonly live?: "status" | "alert" | "off";
}

/** Meaning is carried by the title, the icon and the words, never by colour alone. */
export function InlineNotice({ tone, title, children, actions, live = "off" }: InlineNoticeProps) {
  const role = live === "off" ? undefined : live;
  return (
    <div className={`${styles["notice"]} ${styles[tone]}`} role={role}>
      <span className={styles["icon"]}>
        <Icon name={ICONS[tone]} size={20} />
      </span>
      <div>
        <strong className={styles["title"]}>{title}</strong>
        {children ? <span className={styles["body"]}>{children}</span> : null}
        {actions ? <div className={styles["actions"]}>{actions}</div> : null}
      </div>
    </div>
  );
}
