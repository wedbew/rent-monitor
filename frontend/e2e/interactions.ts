/**
 * The interaction registry: the list of every page, every clickable or typeable element on it and every popup,
 * kept by hand next to the code that renders them (docs/FRONTEND-PLAN.md section 4).
 *
 * "Every page, popup and clickable element has an e2e test" is enforced by the machine, not by review:
 *  1. `inventory.spec.ts` visits each page in each listed scenario, opens each popup, lists every visible element
 *     with an interactive ARIA role and FAILS on one that is unnamed or not registered here (and on a registered
 *     one that is no longer there).
 *  2. A test marks an element exercised with `exercise(id, ...)` (e2e/coverage.ts), which records the id only when
 *     the test also asserted the outcome the registry promises; `coverage-reporter.ts` FAILS the run when a
 *     registered id was never exercised.
 *
 * A slice that adds a screen adds its `PAGES` entry, its `INTERACTIONS`/`POPUPS`, and the tests, in the same PR.
 */
import type { ScenarioName } from "../test/scenarios";

/** What a test must assert after using the element. */
export type OutcomeKind = "url" | "request" | "dialog" | "focus" | "text" | "state";

export type InteractiveRole =
  | "button"
  | "link"
  | "textbox"
  | "searchbox"
  | "checkbox"
  | "radio"
  | "combobox"
  | "listbox"
  | "option"
  | "menuitem"
  | "menuitemcheckbox"
  | "menuitemradio"
  | "tab"
  | "switch"
  | "slider"
  | "spinbutton"
  | "treeitem";

export interface AppPage {
  /** `dashboard`, `analyses.list`... stable; used in interaction ids. */
  readonly id: string;
  /** Path to visit (a concrete one for parameterised routes). */
  readonly path: string;
  /** The page's `h1`, shown once it is ready (the inventory waits for it). */
  readonly heading: string | RegExp;
  /** Every API state this page must be inventoried in. */
  readonly scenarios: readonly ScenarioName[];
}

export interface Interaction {
  readonly id: string;
  readonly page: string;
  readonly role: InteractiveRole;
  /** Accessible name; a RegExp when the name carries data (an audit's address). */
  readonly name: string | RegExp;
  readonly outcome: OutcomeKind;
  /** Only present in these scenarios (default: all of the page's). */
  readonly scenarios?: readonly ScenarioName[];
  /** Inside this popup (see `POPUPS`); omitted for elements on the page itself. */
  readonly within?: string;
}

export interface Popup {
  readonly id: string;
  readonly page: string;
  /** The registered interaction that opens it. */
  readonly trigger: string;
  readonly role: "dialog" | "alertdialog" | "menu" | "listbox" | "tooltip";
  readonly name: string | RegExp;
  /** Does a click outside close it? Decided per popup and tested. */
  readonly backdrop: "closes" | "stays";
  readonly scenarios?: readonly ScenarioName[];
}

export const PAGES: readonly AppPage[] = [
  { id: "placeholder", path: "/", heading: "renti", scenarios: ["firstVisit"] },
];

export const INTERACTIONS: readonly Interaction[] = [];

export const POPUPS: readonly Popup[] = [];
