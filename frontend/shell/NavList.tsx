import type { MouseEvent } from "react";
import { Link, useLocation } from "react-router";

import { Icon } from "../ui/Icon";
import styles from "./NavList.module.css";
import type { Destination } from "./navigation";

interface NavListProps {
  readonly label: string;
  readonly destinations: readonly Destination[];
  /** Lets the container decide when a click navigates (the mobile sheet closes first); see MobileMenu. */
  readonly onFollow?: (to: string, event: MouseEvent) => void;
  readonly size?: "rail" | "sheet";
}

/** One list of real links. `aria-current="page"` comes from the destination's own rule, not from a click. */
export function NavList({ label, destinations, onFollow, size = "rail" }: NavListProps) {
  const { pathname } = useLocation();
  return (
    <nav aria-label={label}>
      <ul className={`${styles["list"]} ${size === "sheet" ? styles["sheet"] : ""}`}>
        {destinations.map((destination) => {
          const active = destination.isActive(pathname);
          return (
            <li key={destination.id}>
              <Link
                to={destination.to}
                className={`${styles["item"]} ${active ? styles["active"] : ""}`}
                aria-current={active ? "page" : undefined}
                {...(onFollow ? { onClick: (event: MouseEvent) => onFollow(destination.to, event) } : {})}
              >
                <span className={styles["icon"]}>
                  <Icon name={destination.icon} />
                </span>
                <span>{destination.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
