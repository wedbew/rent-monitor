import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";

import styles from "./Button.module.css";
import { Icon, type IconName } from "./Icon";

type Variant = "primary" | "secondary" | "danger";

interface CommonProps {
  readonly variant?: Variant;
  readonly icon?: IconName;
  readonly fill?: boolean;
  readonly small?: boolean;
}

function classes(
  variant: Variant | undefined,
  fill: boolean | undefined,
  small: boolean | undefined,
  busy = false,
): string {
  return [
    styles["control"],
    variant === "primary" ? styles["primary"] : "",
    variant === "danger" ? styles["danger"] : "",
    fill ? styles["fill"] : "",
    small ? styles["small"] : "",
    busy ? styles["busy"] : "",
  ]
    .filter(Boolean)
    .join(" ");
}

export interface ButtonProps
  extends CommonProps, Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "className"> {
  /** Always explicit: a button inside a form must say whether it submits. */
  readonly type: "button" | "submit" | "reset";
  /** Shows progress and ignores clicks (no accidental double submit); the width does not change. */
  readonly busy?: boolean;
  readonly children: ReactNode;
}

export function Button({
  variant,
  icon,
  fill,
  small,
  busy = false,
  children,
  disabled,
  onClick,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      className={classes(variant, fill, small, busy)}
      disabled={disabled}
      aria-busy={busy || undefined}
      onClick={busy ? undefined : onClick}
    >
      <span>{children}</span>
      {busy ? (
        <span className={styles["spinner"]} aria-hidden="true" />
      ) : icon ? (
        <span className={styles["icon"]}>
          <Icon name={icon} />
        </span>
      ) : null}
    </button>
  );
}

export interface IconButtonProps extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "type" | "className" | "children" | "aria-label"
> {
  readonly type: "button" | "submit" | "reset";
  /** The accessible name: an icon alone is never a name. */
  readonly label: string;
  readonly icon: IconName;
}

export function IconButton({ label, icon, ...rest }: IconButtonProps) {
  return (
    <button {...rest} aria-label={label} className={[styles["control"], styles["iconOnly"]].join(" ")}>
      <span className={styles["icon"]}>
        <Icon name={icon} size={20} />
      </span>
    </button>
  );
}

export interface LinkButtonProps extends CommonProps, Omit<LinkProps, "className"> {
  readonly children: ReactNode;
}

/** A real link (destination, modified clicks, history) that looks like a button: never a button that navigates. */
export function LinkButton({ variant, icon, fill, small, children, ...rest }: LinkButtonProps) {
  return (
    <Link {...rest} className={classes(variant, fill, small)}>
      <span>{children}</span>
      {icon ? (
        <span className={styles["icon"]}>
          <Icon name={icon} />
        </span>
      ) : null}
    </Link>
  );
}
