/**
 * Recording what a test really did. `exercise(id, run)` is the only way an interaction counts as covered: `run`
 * performs the action and returns outcome tokens produced by the `outcome` helpers, each of which makes a real
 * Playwright assertion first. The id is recorded only when a token of the kind the registry promises came back,
 * so a click without an assertion does not count (see e2e/interactions.ts).
 */
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, type Locator, type Page } from "@playwright/test";

import { INTERACTIONS, type OutcomeKind } from "./interactions";
import type { MockApi, RecordedRequest } from "./mock";

export const COVERAGE_DIR = process.env["E2E_COVERAGE_DIR"] ?? "playwright-coverage";

export interface Outcome {
  readonly kind: OutcomeKind;
}

function record(id: string, kind: OutcomeKind): void {
  mkdirSync(COVERAGE_DIR, { recursive: true });
  appendFileSync(join(COVERAGE_DIR, `${process.pid}.ndjson`), `${JSON.stringify({ id, kind })}\n`);
}

/** Run a registered interaction and count it as covered only if it produced an assertion of its outcome kind. */
export async function exercise(id: string, run: () => Promise<Outcome | readonly Outcome[]>): Promise<void> {
  const entry = INTERACTIONS.find((i) => i.id === id);
  if (entry === undefined) throw new Error(`exercise("${id}"): not registered in e2e/interactions.ts`);
  const result = await run();
  const outcomes: readonly Outcome[] = Array.isArray(result)
    ? (result as readonly Outcome[])
    : [result as Outcome];
  if (!outcomes.some((o) => o.kind === entry.outcome)) {
    throw new Error(
      `exercise("${id}"): the test asserted ${outcomes.map((o) => o.kind).join(", ") || "nothing"}, the registry promises ${entry.outcome}`,
    );
  }
  record(id, entry.outcome);
}

/** For popups: recorded by expectDialogContract once the whole contract held. */
export function recordPopup(id: string): void {
  record(`popup:${id}`, "dialog");
}

export const outcome = {
  /** The page ended up on this URL. */
  async url(page: Page, expected: string | RegExp): Promise<Outcome> {
    await expect(page).toHaveURL(expected);
    return { kind: "url" };
  },
  /** The app sent this API request (method, path and, when given, a JSON body subset). */
  async request(
    api: MockApi,
    expected: { method: string; path: string | RegExp; body?: unknown },
  ): Promise<Outcome> {
    await expect
      .poll(() => api.requests.some((r) => requestMatches(r, expected)), {
        message: `request ${expected.method} ${String(expected.path)}`,
      })
      .toBe(true);
    return { kind: "request" };
  },
  /** A dialog or menu is open or closed. */
  async dialog(locator: Locator, state: "open" | "closed"): Promise<Outcome> {
    if (state === "open") await expect(locator).toBeVisible();
    else await expect(locator).toBeHidden();
    return { kind: "dialog" };
  },
  /** Keyboard focus is on this element. */
  async focus(locator: Locator): Promise<Outcome> {
    await expect(locator).toBeFocused();
    return { kind: "focus" };
  },
  /** Visible text appeared or changed. */
  async text(locator: Locator, text: string | RegExp): Promise<Outcome> {
    await expect(locator).toContainText(text);
    return { kind: "text" };
  },
  /** An ARIA/DOM state changed (pressed, expanded, selected, checked, current page...). */
  async state(locator: Locator, attribute: string, value: string | RegExp): Promise<Outcome> {
    await expect(locator).toHaveAttribute(attribute, value);
    return { kind: "state" };
  },
};

function requestMatches(
  request: RecordedRequest,
  expected: { method: string; path: string | RegExp; body?: unknown },
): boolean {
  if (request.method !== expected.method) return false;
  const pathOk =
    typeof expected.path === "string" ? request.path === expected.path : expected.path.test(request.path);
  return pathOk && (expected.body === undefined || subset(expected.body, request.body));
}

function subset(expected: unknown, actual: unknown): boolean {
  if (typeof expected !== "object" || expected === null) return expected === actual;
  if (typeof actual !== "object" || actual === null) return false;
  return Object.entries(expected).every(([key, value]) =>
    subset(value, (actual as Record<string, unknown>)[key]),
  );
}
