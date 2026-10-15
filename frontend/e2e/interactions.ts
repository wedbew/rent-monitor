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
import type { Page } from "@playwright/test";

import { LEGAL, PRIMARY } from "../shell/navigation";
import { createAuthFlow, type Scenario, type ScenarioName } from "../test/scenarios";
import { nextGoogleCredential } from "./gis";

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

/**
 * A state of a page that shows different interactive elements (an error summary, a "link sent" confirmation, an
 * unconfirmed-account banner). The inventory visits it too: `prepare` drives the page there with the real UI.
 * Elements that exist only there are registered with `state`; elements that are also in the base state stay as they are.
 */
export interface PageState {
  readonly name: string;
  /** Another path (a link with a token) when the state needs one; default the page's. */
  readonly path?: string;
  /** The API scenario for this state: a registry name, or a factory for a stateful scenario (a fresh one per test). */
  readonly scenario: ScenarioName | (() => Scenario);
  readonly prepare: (page: Page) => Promise<void>;
}

export interface AppPage {
  /** `dashboard`, `analyses.list`... stable; used in interaction ids. */
  readonly id: string;
  /** Path to visit (a concrete one for parameterised routes). */
  readonly path: string;
  /** `public` pages use the signed-out frame (features/auth/PublicLayout); default `app`. */
  readonly layout?: "app" | "public";
  /** The page's `h1`, shown once it is ready (the inventory waits for it). */
  readonly heading: string | RegExp;
  /** Every API state this page must be inventoried in. */
  readonly scenarios: readonly ScenarioName[];
  /** Further states of the page, reached through the UI (see PageState). */
  readonly states?: readonly PageState[];
}

/** The two layouts the app has; the project's viewport decides which one a test sees (<= 760 px is mobile). */
export type Viewport = "desktop" | "mobile";

/** `"*"` registers an element of the shell that is on every page (navigation, theme): exercised once, inventoried everywhere. */
export type PageRef = string;
export const EVERY_PAGE = "*";
/** The same for every page of the signed-out frame (brand, theme, documents). */
export const EVERY_PUBLIC_PAGE = "public:*";

export interface Interaction {
  readonly id: string;
  readonly page: PageRef;
  readonly role: InteractiveRole;
  /** Accessible name; a RegExp when the name carries data (an audit's address). */
  readonly name: string | RegExp;
  readonly outcome: OutcomeKind;
  /** Only present in these scenarios (default: all of the page's). */
  readonly scenarios?: readonly ScenarioName[];
  /** Only in this page state (see PageState); default the base state. */
  readonly state?: string;
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
const SIGNED_OUT = ["firstVisit"] as const;
const SAMPLE_TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz012345";

export const PAGES: readonly AppPage[] = [
  { id: "dashboard", path: "/app", heading: "Pulpit", scenarios: ["empty", "unverified"] },
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
  // The signed-out frame: sign-in, sign-up, the three pages the API's e-mails link to, password recovery.
  {
    id: "login",
    path: "/login",
    layout: "public",
    heading: "Zaloguj się",
    scenarios: SIGNED_OUT,
    states: [
      {
        name: "validation-errors",
        scenario: "firstVisit",
        prepare: async (page) => {
          await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
          await page.getByRole("alert").filter({ hasText: "Popraw pola" }).waitFor();
        },
      },
      {
        name: "wrong-password",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Adres e-mail", exact: true }).fill("anna@example.test");
          await page.getByRole("textbox", { name: "Hasło" }).fill("wrong-password-1");
          await page.getByRole("button", { name: "Zaloguj się", exact: true }).click();
          await page.getByRole("alert").filter({ hasText: "Nieprawidłowy e-mail lub hasło" }).waitFor();
        },
      },
      {
        name: "google-needs-link",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await nextGoogleCredential(page, "fake-confirm-credential-0123456789");
          await page.getByRole("button", { name: "Zaloguj się przez Google" }).click();
          await page.getByRole("button", { name: "Użyj linku e-mail" }).waitFor();
        },
      },
      {
        name: "link-sent",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Adres e-mail do linku" }).fill("anna@example.test");
          await page.getByRole("button", { name: "Wyślij link do logowania" }).click();
          await page.getByText("Sprawdź skrzynkę").waitFor();
        },
      },
    ],
  },
  {
    id: "signup",
    path: "/signup",
    layout: "public",
    heading: "Załóż konto",
    scenarios: SIGNED_OUT,
    states: [
      {
        name: "validation-errors",
        scenario: "firstVisit",
        prepare: async (page) => {
          await page.getByRole("button", { name: "Załóż konto" }).click();
          await page.getByRole("alert").filter({ hasText: "Popraw pola" }).waitFor();
        },
      },
      {
        name: "weak-password",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Adres e-mail" }).fill("anna@example.test");
          await page.getByRole("textbox", { name: "Hasło" }).fill("password1234");
          await page.getByRole("button", { name: "Załóż konto" }).click();
          await page.getByRole("alert").filter({ hasText: "Popraw 1 pole" }).waitFor();
        },
      },
      {
        name: "link-sent",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Adres e-mail" }).fill("anna@example.test");
          await page.getByRole("textbox", { name: "Hasło" }).fill("correct-horse-battery-staple-91");
          await page.getByRole("button", { name: "Załóż konto" }).click();
          await page.getByRole("heading", { level: 1, name: "Sprawdź skrzynkę" }).waitFor();
        },
      },
    ],
  },
  {
    id: "forgot",
    path: "/password/forgot",
    layout: "public",
    heading: "Nie pamiętam hasła",
    scenarios: SIGNED_OUT,
  },
  {
    id: "reset",
    path: `/password/reset#t=${SAMPLE_TOKEN}`,
    layout: "public",
    heading: "Ustaw nowe hasło",
    scenarios: SIGNED_OUT,
    states: [
      {
        name: "weak-password",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Nowe hasło" }).fill("password1234");
          await page.getByRole("button", { name: "Zapisz hasło" }).click();
          await page.getByRole("alert").filter({ hasText: "Popraw 1 pole" }).waitFor();
        },
      },
      {
        name: "done",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Nowe hasło" }).fill("a-brand-new-passphrase-77");
          await page.getByRole("button", { name: "Zapisz hasło" }).click();
          await page.getByRole("heading", { level: 1, name: "Hasło zostało zmienione" }).waitFor();
        },
      },
    ],
  },
  {
    id: "reset-invalid",
    path: "/password/reset",
    layout: "public",
    heading: "Ustaw nowe hasło",
    scenarios: SIGNED_OUT,
  },
  {
    id: "login-email",
    path: "/login/email",
    layout: "public",
    heading: "Logowanie linkiem",
    scenarios: SIGNED_OUT,
  },
  {
    id: "signup-verify",
    path: "/signup/verify",
    layout: "public",
    heading: "Potwierdzenie adresu e-mail",
    scenarios: SIGNED_OUT,
    states: [
      {
        name: "account-exists",
        path: "/signup/verify#t=exists12345678901234567890",
        scenario: () => createAuthFlow(),
        prepare: async (page) => {
          await page.getByText("Masz już konto z tym adresem").waitFor();
        },
      },
    ],
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
  {
    id: "shell.signout",
    page: EVERY_PAGE,
    viewport: "desktop",
    role: "button",
    name: "Wyloguj się",
    outcome: "url",
  },
  {
    id: "shell.menu.signout",
    page: EVERY_PAGE,
    viewport: "mobile",
    within: "mobile-menu",
    role: "button",
    name: "Wyloguj się",
    outcome: "url",
  },
  {
    id: "shell.verify.resend",
    page: EVERY_PAGE,
    scenarios: ["unverified"],
    role: "button",
    name: "Wyślij link ponownie",
    outcome: "request",
  },

  // The signed-out frame (every public page).
  { id: "public.skip", page: EVERY_PUBLIC_PAGE, role: "link", name: "Przejdź do treści", outcome: "focus" },
  {
    id: "public.brand",
    page: EVERY_PUBLIC_PAGE,
    role: "link",
    name: "renti.tech, przejdź do pulpitu",
    outcome: "url",
  },
  { id: "public.theme", page: EVERY_PUBLIC_PAGE, role: "button", name: THEME_NAME, outcome: "state" },
  { id: "public.terms", page: EVERY_PUBLIC_PAGE, role: "link", name: "Regulamin", outcome: "url" },
  {
    id: "public.privacy",
    page: EVERY_PUBLIC_PAGE,
    role: "link",
    name: "Polityka prywatności",
    outcome: "url",
  },

  // Sign in.
  { id: "login.google", page: "login", role: "button", name: "Zaloguj się przez Google", outcome: "request" },
  { id: "login.email", page: "login", role: "textbox", name: "Adres e-mail", outcome: "state" },
  { id: "login.password", page: "login", role: "textbox", name: "Hasło", outcome: "state" },
  { id: "login.submit", page: "login", role: "button", name: "Zaloguj się", outcome: "request" },
  { id: "login.forgot", page: "login", role: "link", name: "Nie pamiętam hasła", outcome: "url" },
  { id: "login.link-email", page: "login", role: "textbox", name: "Adres e-mail do linku", outcome: "state" },
  {
    id: "login.link-submit",
    page: "login",
    role: "button",
    name: "Wyślij link do logowania",
    outcome: "request",
  },
  { id: "login.signup", page: "login", role: "link", name: "Zarejestruj się", outcome: "url" },

  // Sign up.
  {
    id: "signup.google",
    page: "signup",
    role: "button",
    name: "Zarejestruj się przez Google",
    outcome: "request",
  },
  { id: "signup.email", page: "signup", role: "textbox", name: "Adres e-mail", outcome: "state" },
  { id: "signup.password", page: "signup", role: "textbox", name: "Hasło", outcome: "state" },
  { id: "signup.submit", page: "signup", role: "button", name: "Załóż konto", outcome: "request" },
  { id: "signup.terms", page: "signup", role: "link", name: "Regulamin", outcome: "url" },
  { id: "signup.privacy", page: "signup", role: "link", name: /^Polityk[aą] prywatności$/, outcome: "url" },
  { id: "signup.login", page: "signup", role: "link", name: "Zaloguj się", outcome: "url" },

  // Password recovery.
  { id: "forgot.email", page: "forgot", role: "textbox", name: "Adres e-mail", outcome: "state" },
  { id: "forgot.submit", page: "forgot", role: "button", name: "Wyślij link", outcome: "request" },
  { id: "forgot.back", page: "forgot", role: "link", name: "Wróć do logowania", outcome: "url" },
  { id: "reset.password", page: "reset", role: "textbox", name: "Nowe hasło", outcome: "state" },
  { id: "reset.submit", page: "reset", role: "button", name: "Zapisz hasło", outcome: "request" },
  { id: "reset.back", page: "reset", role: "link", name: "Wróć do logowania", outcome: "url" },
  {
    id: "reset-invalid.new-link",
    page: "reset-invalid",
    role: "link",
    name: "Poproś o nowy link",
    outcome: "url",
  },
  {
    id: "reset-invalid.back",
    page: "reset-invalid",
    role: "link",
    name: "Wróć do logowania",
    outcome: "url",
  },

  // The links the API mails, opened without a token (a truncated link).
  {
    id: "login-email.new-link",
    page: "login-email",
    role: "link",
    name: "Poproś o nowy link",
    outcome: "url",
  },
  { id: "login-email.back", page: "login-email", role: "link", name: "Wróć do logowania", outcome: "url" },
  {
    id: "signup-verify.again",
    page: "signup-verify",
    role: "link",
    name: "Zarejestruj się ponownie",
    outcome: "url",
  },
  {
    id: "signup-verify.back",
    page: "signup-verify",
    role: "link",
    name: "Wróć do logowania",
    outcome: "url",
  },

  // Elements that exist only in a state of a page.
  {
    id: "login.error.email",
    page: "login",
    state: "validation-errors",
    role: "link",
    name: "Wpisz adres e-mail.",
    outcome: "focus",
  },
  {
    id: "login.error.password",
    page: "login",
    state: "validation-errors",
    role: "link",
    name: "Wpisz hasło.",
    outcome: "focus",
  },
  {
    id: "login.use-link",
    page: "login",
    state: "google-needs-link",
    role: "button",
    name: "Użyj linku e-mail",
    outcome: "focus",
  },
  {
    id: "signup.error.email",
    page: "signup",
    state: "validation-errors",
    role: "link",
    name: "Wpisz adres e-mail.",
    outcome: "focus",
  },
  {
    id: "signup.error.password",
    page: "signup",
    state: "validation-errors",
    role: "link",
    name: "Wpisz hasło.",
    outcome: "focus",
  },
  {
    id: "signup.error.weak",
    page: "signup",
    state: "weak-password",
    role: "link",
    name: /popularne/,
    outcome: "focus",
  },
  {
    id: "signup.resend",
    page: "signup",
    state: "link-sent",
    role: "button",
    name: "Wyślij link ponownie",
    outcome: "request",
  },
  {
    id: "signup.change-address",
    page: "signup",
    state: "link-sent",
    role: "button",
    name: "Zmień adres",
    outcome: "text",
  },
  {
    id: "reset.error.weak",
    page: "reset",
    state: "weak-password",
    role: "link",
    name: /popularne/,
    outcome: "focus",
  },
  { id: "reset.done.login", page: "reset", state: "done", role: "link", name: "Zaloguj się", outcome: "url" },
  {
    id: "signup-verify.exists.login",
    page: "signup-verify",
    state: "account-exists",
    role: "link",
    name: "Zaloguj się",
    outcome: "url",
  },
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
