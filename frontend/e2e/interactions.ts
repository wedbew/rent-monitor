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
import { LEGAL, PRIMARY } from "../shell/navigation";
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

/** The two layouts the app has; the project's viewport decides which one a test sees (<= 760 px is mobile). */
export type Viewport = "desktop" | "mobile";

/** `"*"` registers an element of the shell that is on every page (navigation, theme): exercised once, inventoried everywhere. */
export type PageRef = string;
export const EVERY_PAGE = "*";

export interface Interaction {
  readonly id: string;
  readonly page: PageRef;
  readonly role: InteractiveRole;
  /** Accessible name; a RegExp when the name carries data (an audit's address). */
  readonly name: string | RegExp;
  readonly outcome: OutcomeKind;
  /** Only present in these scenarios (default: all of the page's). */
  readonly scenarios?: readonly ScenarioName[];
  /** Only in this layout (the desktop rail is not in the DOM on mobile); default both. */
  readonly viewport?: Viewport;
  /** Inside this popup (see `POPUPS`); omitted for elements on the page itself. */
  readonly within?: string;
}

export interface Popup {
  readonly id: string;
  readonly page: PageRef;
  readonly viewport?: Viewport;
  /** The registered interaction that opens it. */
  readonly trigger: string;
  readonly role: "dialog" | "alertdialog" | "menu" | "listbox" | "tooltip";
  readonly name: string | RegExp;
  /** Does a click outside close it? Decided per popup and tested. */
  readonly backdrop: "closes" | "stays";
  readonly scenarios?: readonly ScenarioName[];
}

const EVERY_SCENARIO = ["empty"] as const;

export const PAGES: readonly AppPage[] = [
  { id: "dashboard", path: "/app", heading: "Pulpit", scenarios: EVERY_SCENARIO },
  { id: "new-analysis", path: "/app/analyses/new", heading: "Nowa analiza", scenarios: EVERY_SCENARIO },
  { id: "analyses", path: "/app/analyses", heading: "Moje analizy", scenarios: EVERY_SCENARIO },
  {
    id: "report",
    path: "/app/analyses/00000000-0000-4000-8000-000000000001",
    heading: "Raport",
    scenarios: EVERY_SCENARIO,
  },
  { id: "market", path: "/app/market", heading: "Rynek", scenarios: EVERY_SCENARIO },
  { id: "interior", path: "/app/interior", heading: "Architekt wnętrz", scenarios: EVERY_SCENARIO },
  { id: "listing", path: "/app/listings/new", heading: "Stwórz ogłoszenie", scenarios: EVERY_SCENARIO },
  { id: "settings", path: "/app/settings", heading: "Ustawienia", scenarios: EVERY_SCENARIO },
  { id: "terms", path: "/terms", heading: "Regulamin", scenarios: EVERY_SCENARIO },
  { id: "privacy", path: "/privacy", heading: "Polityka prywatności", scenarios: EVERY_SCENARIO },
  {
    id: "not-found",
    path: "/nie-ma-takiej-strony",
    heading: "Nie znaleziono strony",
    scenarios: EVERY_SCENARIO,
  },
];

// The shell is on every page (EVERY_PAGE): registered once, inventoried everywhere. The destination lists come from
// the navigation registry so a new destination is registered here automatically and then needs its test.
const THEME_NAME = /^Tryb (ciemny|jasny)$/;

export const INTERACTIONS: readonly Interaction[] = [
  { id: "shell.skip", page: EVERY_PAGE, role: "link", name: "Przejdź do treści", outcome: "focus" },
  {
    id: "shell.brand",
    page: EVERY_PAGE,
    role: "link",
    name: "renti.tech, przejdź do pulpitu",
    outcome: "url",
  },
  { id: "shell.theme", page: EVERY_PAGE, role: "button", name: THEME_NAME, outcome: "state" },
  ...PRIMARY.map((d): Interaction => ({
    id: `shell.nav.${d.id}`,
    page: EVERY_PAGE,
    viewport: "desktop",
    role: "link",
    name: d.label,
    outcome: "url",
  })),
  ...LEGAL.map((d): Interaction => ({
    id: `shell.nav.${d.id}`,
    page: EVERY_PAGE,
    viewport: "desktop",
    role: "link",
    name: d.label,
    outcome: "url",
  })),
  {
    id: "shell.menu",
    page: EVERY_PAGE,
    viewport: "mobile",
    role: "button",
    name: "Otwórz menu nawigacji",
    outcome: "dialog",
  },
  {
    id: "shell.menu.close",
    page: EVERY_PAGE,
    viewport: "mobile",
    within: "mobile-menu",
    role: "button",
    name: "Zamknij nawigację",
    outcome: "dialog",
  },
  ...[...PRIMARY, ...LEGAL].map((d): Interaction => ({
    id: `shell.menu.nav.${d.id}`,
    page: EVERY_PAGE,
    viewport: "mobile",
    within: "mobile-menu",
    role: "link",
    name: d.label,
    outcome: "url",
  })),
  { id: "not-found.home", page: "not-found", role: "link", name: "Wróć do pulpitu", outcome: "url" },
];

export const POPUPS: readonly Popup[] = [
  {
    id: "mobile-menu",
    page: EVERY_PAGE,
    viewport: "mobile",
    trigger: "shell.menu",
    role: "dialog",
    name: "Nawigacja",
    backdrop: "closes",
  },
];
