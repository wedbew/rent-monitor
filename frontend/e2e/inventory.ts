import type { Locator, Page } from "@playwright/test";

import { findViolations, type Scope, type Violation } from "./gate";
import { INTERACTIONS, type Interaction } from "./interactions";

/** Violations of the interaction gate for what the browser shows right now (the page or one popup). */
export async function inventory(
  page: Page,
  scope: Scope,
  registry: readonly Interaction[] = INTERACTIONS,
  root?: Locator,
): Promise<Violation[]> {
  const snapshot = await (root ?? page.locator("body")).ariaSnapshot();
  return findViolations(snapshot, registry, scope);
}
