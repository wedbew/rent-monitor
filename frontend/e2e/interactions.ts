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
import {
  createAuthFlow,
  createCollection,
  createRun,
  type Scenario,
  type ScenarioName,
  RUN_AUDIT_ID,
  SUCCEEDED_AUDITS,
} from "../test/scenarios";
import { fx, type Fixture } from "../test/fixtures";
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
  /** Reached only in this page state (see PageState: `prepare` leaves the page ready for the trigger). */
  readonly state?: string;
}

const EVERY_SCENARIO = ["empty"] as const;
const LISTING = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd";

/** A fixture's answer as a scenario reply (for the failing variants of a run). */
function replyOf(operation: string, name: string) {
  const fixture: Fixture = fx(operation, name);
  return {
    status: fixture.status,
    body: fixture.body,
    contentType: fixture.content_type,
    headers: fixture.headers,
  };
}

/** The list row of an analysis created a moment ago (what the list says after a POST whose answer was lost). */
function justCreated() {
  return {
    audit_id: RUN_AUDIT_ID,
    otodom_id: "ID4abcd",
    status: "queued" as const,
    error_code: null,
    created_at: new Date().toISOString(),
    finished_at: null,
    grade: null,
    asking_price_pln: null,
    max_bid_pln: null,
  };
}

/** Type a listing into the new-analysis form and send it. */
function submitListing(value: string) {
  return async (page: Page): Promise<void> => {
    await page.getByRole("textbox", { name: "Adres ogłoszenia lub numer" }).fill(value);
    await page.getByRole("button", { name: "Rozpocznij analizę" }).click();
  };
}
const SIGNED_OUT = ["firstVisit"] as const;
const SAMPLE_TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz012345";

export const PAGES: readonly AppPage[] = [
  {
    id: "dashboard",
    path: "/app",
    heading: "Pulpit",
    scenarios: [
      "empty",
      "loaded",
      "mixed",
      "breakerOpen",
      "insufficientCredits",
      "auditsFailing",
      "unverified",
    ],
    states: [
      {
        // Audit F03: the sign-out request never reached the server, so the session may still be alive.
        name: "signout-unconfirmed",
        scenario: () => {
          const flow = createAuthFlow({ "POST /api/auth/signout": { status: 0, networkError: true } });
          flow.state.signedIn = true;
          return flow;
        },
        prepare: async (page) => {
          if ((page.viewportSize()?.width ?? 1280) <= 760)
            await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
          await page.getByRole("button", { name: "Wyloguj się" }).click();
          await page.getByText("Nie udało się potwierdzić wylogowania").waitFor();
        },
      },
    ],
  },
  {
    id: "new-analysis",
    path: "/app/analyses/new",
    heading: "Nowa analiza",
    scenarios: ["empty", "insufficientCredits"],
    states: [
      {
        name: "otodom-limited",
        scenario: "breakerOpen",
        prepare: async (page) => {
          await page.getByRole("status").filter({ hasText: "Otodom ogranicza zapytania" }).waitFor();
        },
      },
      {
        name: "validation-error",
        scenario: "empty",
        prepare: async (page) => {
          await page.getByRole("button", { name: "Rozpocznij analizę" }).click();
          await page.getByRole("alert").filter({ hasText: "Popraw 1 pole" }).waitFor();
        },
      },
      {
        name: "invalid-listing",
        scenario: () => createRun({ post: replyOf("POST /api/audits", "invalid_listing_ref") }),
        prepare: submitListing("https://example.test/nie-otodom"),
      },
      {
        name: "in-progress",
        scenario: () => createRun({ post: replyOf("POST /api/audits", "already_in_progress") }),
        prepare: async (page) => {
          await submitListing(LISTING)(page);
          await page.getByRole("status").filter({ hasText: "Ta analiza już trwa" }).waitFor();
        },
      },
      {
        name: "ambiguous-arrived",
        scenario: () =>
          createRun({ post: { status: 0, networkError: true }, listAfterPost: [justCreated()] }),
        prepare: async (page) => {
          await submitListing(LISTING)(page);
          await page.getByRole("status").filter({ hasText: "Analiza została przyjęta" }).waitFor();
        },
      },
      {
        name: "ambiguous-unknown",
        scenario: () => createRun({ post: { status: 0, networkError: true }, listFails: true }),
        prepare: async (page) => {
          await submitListing(LISTING)(page);
          await page.getByRole("alert").filter({ hasText: "Nie wiemy, czy analiza ruszyła" }).waitFor();
        },
      },
      {
        name: "no-credits",
        scenario: "insufficientCredits",
        // The paywall opens from the submit button: `prepare` only fills the field in.
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Adres ogłoszenia lub numer" }).fill(LISTING);
        },
      },
    ],
  },
  {
    id: "analyses",
    path: "/app/analyses",
    heading: "Moje analizy",
    scenarios: ["empty", "collection", "slow", "auditsFailing"],
    states: [
      {
        name: "table",
        scenario: () => createCollection(),
        prepare: async (page) => {
          await page.getByRole("button", { name: "Tabela" }).click();
          await page.getByRole("table").waitFor();
        },
      },
      {
        name: "filtered-empty",
        scenario: () => createCollection(),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Numer ogłoszenia (początek)" }).fill("ZZZ");
          await page.getByRole("button", { name: "Szukaj" }).click();
          await page.getByText("Żadna analiza nie pasuje do filtrów").waitFor();
        },
      },
      {
        name: "load-more-error",
        scenario: () => createCollection({ failPage: 1 }),
        prepare: async (page) => {
          await page.getByRole("button", { name: "Załaduj więcej" }).click();
          await page
            .getByRole("alert")
            .filter({ hasText: "Nie udało się wczytać kolejnych analiz" })
            .waitFor();
        },
      },
      {
        name: "end-of-list",
        scenario: () => createCollection({ count: 30 }),
        prepare: async (page) => {
          await page.getByRole("button", { name: "Załaduj więcej" }).click();
          await page.getByText("To wszystkie analizy (30).").waitFor();
        },
      },
    ],
  },
  {
    id: "report",
    path: `/app/analyses/${SUCCEEDED_AUDITS[0]?.audit_id ?? ""}`,
    heading: "Raport",
    scenarios: ["loaded"],
    states: [
      {
        name: "rejected",
        path: "/app/analyses/00000000-0000-4000-8000-000000000036",
        scenario: "rejectedRent",
        prepare: async (page) => {
          await page.getByRole("status").filter({ hasText: "To ogłoszenie wynajmu" }).waitFor();
        },
      },
      {
        name: "failed",
        path: "/app/analyses/00000000-0000-4000-8000-000000000032",
        scenario: "failedUpstream",
        prepare: async (page) => {
          await page.getByRole("status").filter({ hasText: "Otodom zablokował pobranie" }).waitFor();
        },
      },
      {
        name: "running",
        path: `/app/analyses/${RUN_AUDIT_ID}`,
        scenario: () => createRun({ interrupt: true }),
        prepare: async (page) => {
          await page.getByRole("progressbar", { name: "Postęp analizy" }).waitFor();
        },
      },
      {
        name: "degraded",
        path: "/app/analyses/00000000-0000-4000-8000-000000000037",
        scenario: "degraded",
        prepare: async (page) => {
          await page.getByRole("heading", { level: 2, name: "Podsumowanie" }).waitFor();
        },
      },
      {
        name: "unsupported-version",
        scenario: "unsupportedReport",
        prepare: async (page) => {
          await page.getByRole("status").filter({ hasText: "Nieobsługiwana wersja raportu" }).waitFor();
        },
      },
      {
        name: "invalid-result",
        scenario: "invalidReport",
        prepare: async (page) => {
          await page.getByRole("status").filter({ hasText: "Nie można wyświetlić raportu" }).waitFor();
        },
      },
      {
        name: "rich",
        scenario: "richReport",
        prepare: async (page) => {
          await page.getByRole("heading", { level: 2, name: "Podsumowanie" }).waitFor();
        },
      },
      {
        name: "not-found",
        path: "/app/analyses/00000000-0000-4000-8000-000000000999",
        scenario: "unknownAudit",
        prepare: async (page) => {
          await page.getByRole("alert").filter({ hasText: "Nie znaleziono analizy" }).waitFor();
        },
      },
      {
        name: "unavailable",
        path: "/app/analyses/00000000-0000-4000-8000-000000000999",
        scenario: "auditUnavailable",
        prepare: async (page) => {
          await page
            .getByRole("alert")
            .filter({ hasText: "Spróbuj ponownie" })
            .or(page.getByRole("alert"))
            .first()
            .waitFor();
        },
      },
    ],
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
    id: "shell.signout.retry",
    page: "dashboard",
    state: "signout-unconfirmed",
    role: "button",
    name: "Spróbuj wylogować ponownie",
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

  // Dashboard.
  {
    id: "dashboard.analysis",
    page: "dashboard",
    scenarios: ["empty", "loaded", "mixed", "insufficientCredits", "auditsFailing", "unverified"],
    role: "link",
    name: "Rozpocznij analizę",
    outcome: "url",
  },
  { id: "dashboard.all", page: "dashboard", role: "link", name: "Moje analizy", outcome: "url" },
  {
    id: "dashboard.first",
    page: "dashboard",
    scenarios: ["empty", "breakerOpen", "insufficientCredits", "unverified"],
    role: "link",
    name: "Sprawdź pierwsze mieszkanie",
    outcome: "url",
  },
  {
    id: "dashboard.row",
    page: "dashboard",
    scenarios: ["loaded", "mixed"],
    role: "link",
    name: /^Ogłoszenie /,
    outcome: "url",
  },
  {
    id: "dashboard.retry",
    page: "dashboard",
    scenarios: ["auditsFailing"],
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  {
    id: "dashboard.buy",
    page: "dashboard",
    scenarios: ["insufficientCredits"],
    role: "link",
    name: "Kup raporty",
    outcome: "url",
  },

  // Moje analizy.
  {
    id: "analyses.search",
    page: "analyses",
    role: "textbox",
    name: "Numer ogłoszenia (początek)",
    outcome: "state",
  },
  { id: "analyses.search.submit", page: "analyses", role: "button", name: "Szukaj", outcome: "url" },
  { id: "analyses.status", page: "analyses", role: "combobox", name: "Status", outcome: "url" },
  { id: "analyses.grade", page: "analyses", role: "combobox", name: "Ocena", outcome: "url" },
  { id: "analyses.view.cards", page: "analyses", role: "button", name: "Karty", outcome: "state" },
  { id: "analyses.view.table", page: "analyses", role: "button", name: "Tabela", outcome: "url" },
  { id: "analyses.option.all", page: "analyses", role: "option", name: "Wszystkie", outcome: "url" },
  ...[
    ["ready", "Gotowe"],
    ["active", "W toku"],
    ["rejected", "Odrzucone"],
    ["failed", "Nieudane"],
    ["grade-A", "A"],
    ["grade-B", "B"],
    ["grade-C", "C"],
    ["grade-D", "D"],
    ["grade-E", "E"],
    ["grade-N", "Bez oceny"],
  ].map(([id = "", label = ""]): Interaction => ({
    id: `analyses.option.${id}`,
    page: "analyses",
    role: "option",
    name: label,
    outcome: "url",
  })),
  {
    id: "analyses.row",
    page: "analyses",
    scenarios: ["collection"],
    role: "link",
    name: /^Ogłoszenie IDLST/,
    outcome: "url",
  },
  {
    id: "analyses.more",
    page: "analyses",
    scenarios: ["collection"],
    role: "button",
    name: "Załaduj więcej",
    outcome: "request",
  },
  {
    id: "analyses.first",
    page: "analyses",
    scenarios: ["empty", "slow"],
    role: "link",
    name: "Sprawdź pierwsze mieszkanie",
    outcome: "url",
  },
  {
    id: "analyses.retry",
    page: "analyses",
    scenarios: ["auditsFailing"],
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  {
    id: "analyses.clear",
    page: "analyses",
    state: "filtered-empty",
    role: "button",
    name: "Wyczyść filtry",
    outcome: "url",
  },

  // New analysis.
  {
    id: "new.field",
    page: "new-analysis",
    role: "textbox",
    name: "Adres ogłoszenia lub numer",
    outcome: "state",
  },
  {
    id: "new.submit",
    page: "new-analysis",
    role: "button",
    name: "Rozpocznij analizę",
    outcome: "request",
  },
  {
    id: "new.error.field",
    page: "new-analysis",
    state: "validation-error",
    role: "link",
    name: "Wklej adres ogłoszenia lub jego numer.",
    outcome: "focus",
  },
  {
    id: "new.error.listing",
    page: "new-analysis",
    state: "invalid-listing",
    role: "link",
    name: "Wklej adres ogłoszenia sprzedaży z Otodom albo jego numer.",
    outcome: "focus",
  },
  {
    id: "new.existing",
    page: "new-analysis",
    state: "in-progress",
    role: "link",
    name: "Otwórz analizę",
    outcome: "url",
  },
  {
    id: "new.arrived",
    page: "new-analysis",
    state: "ambiguous-arrived",
    role: "link",
    name: "Zobacz postęp",
    outcome: "url",
  },
  {
    id: "new.check",
    page: "new-analysis",
    state: "ambiguous-unknown",
    role: "link",
    name: "Sprawdź w Moich analizach",
    outcome: "url",
  },
  {
    id: "new.paywall.close",
    page: "new-analysis",
    state: "no-credits",
    within: "paywall",
    role: "button",
    name: "Zamknij okno",
    outcome: "dialog",
  },
  {
    id: "new.paywall.buy",
    page: "new-analysis",
    state: "no-credits",
    within: "paywall",
    role: "link",
    name: "Kup raporty",
    outcome: "url",
  },

  // One analysis (progress and result).
  { id: "report.all", page: "report", role: "link", name: "Moje analizy", outcome: "url" },
  ...[
    ["podsumowanie", "Podsumowanie"],
    ["czynsz", "Czynsz"],
    ["koszty", "Koszty i stan"],
    ["cena", "Cena zakupu"],
    ["sprawdz", "Co sprawdzić"],
    ["zrodla", "Źródła"],
  ].map(([id = "", label = ""]): Interaction => ({
    id: `report.nav.${id}`,
    page: "report",
    role: "link",
    name: label,
    outcome: "focus",
  })),
  ...[
    ["rent-how", "Jak policzyliśmy czynsz"],
    ["purchase", "Koszty zakupu: szczegóły"],
    ["owner-costs", "Koszty właściciela w roku 1"],
    ["capex", "Remont: szacunek i założenia"],
    ["sensitivity", "Zwroty, wyjście i wrażliwość na wzrost cen"],
    ["years", "Przepływy pieniężne rok po roku"],
    ["listing", "Dane z ogłoszenia"],
    ["vision", "Ocena zdjęć"],
  ].map(([id = "", label = ""]): Interaction => ({
    id: `report.more.${id}`,
    page: "report",
    role: "button",
    name: label,
    outcome: "state",
  })),
  {
    id: "report.external",
    page: "report",
    state: "rich",
    role: "link",
    name: "Zobacz ogłoszenie na Otodom",
    outcome: "state",
  },
  {
    id: "report.more.evidence",
    page: "report",
    state: "rich",
    role: "button",
    name: /^Fragmenty ogłoszenia użyte w ocenie/,
    outcome: "state",
  },
  {
    id: "report.new.rejected",
    page: "report",
    state: "rejected",
    role: "link",
    name: "Nowa analiza",
    outcome: "url",
  },
  {
    id: "report.new.failed",
    page: "report",
    state: "failed",
    role: "link",
    name: "Nowa analiza",
    outcome: "url",
  },
  {
    id: "report.retry",
    page: "report",
    state: "unavailable",
    role: "button",
    name: "Spróbuj ponownie",
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
    id: "paywall",
    page: "new-analysis",
    state: "no-credits",
    trigger: "new.submit",
    role: "dialog",
    name: "Nie masz już raportów",
    backdrop: "closes",
  },
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
