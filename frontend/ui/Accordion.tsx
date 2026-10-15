import { Accordion as BaseAccordion } from "@base-ui/react/accordion";
import type { ReactNode } from "react";

import { Icon } from "./Icon";
import styles from "./Accordion.module.css";

export interface DisclosureItem {
  readonly value: string;
  /** The button's accessible name: it says what is inside (and may carry a count). */
  readonly title: string;
  readonly children: ReactNode;
}

interface DisclosureGroupProps {
  readonly items: readonly DisclosureItem[];
  /** Several may be open at once, and opening one never closes another (the reader keeps their place). */
  readonly defaultOpen?: readonly string[];
}

/**
 * Details that belong to a section: closed by default, each one a real button with `aria-expanded` and a panel it
 * controls (Base UI). Opening is local and reversible; nothing moves on its own.
 */
export function DisclosureGroup({ items, defaultOpen = [] }: DisclosureGroupProps) {
  return (
    <BaseAccordion.Root className={styles["root"]} multiple defaultValue={[...defaultOpen]}>
      {items.map((item) => (
        <BaseAccordion.Item key={item.value} value={item.value} className={styles["item"]}>
          <BaseAccordion.Header className={styles["header"]}>
            <BaseAccordion.Trigger className={styles["trigger"]}>
              <span>{item.title}</span>
              <span className={styles["chevron"]} aria-hidden="true">
                <Icon name="arrow" />
              </span>
            </BaseAccordion.Trigger>
          </BaseAccordion.Header>
          <BaseAccordion.Panel className={styles["panel"]}>{item.children}</BaseAccordion.Panel>
        </BaseAccordion.Item>
      ))}
    </BaseAccordion.Root>
  );
}
