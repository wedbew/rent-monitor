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
  createInterior,
  createMarket,
  createRun,
  createSaved,
  type Scenario,
  type ScenarioName,
  RUN_AUDIT_ID,
  SHOP_HISTORY,
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
/** Settings scenarios whose account has a password: only those show the change-password form (RM-345). */
const PASSWORD_ACCOUNT = ["settings", "settingsOneSession", "settingsSessionsFailing"] as const;

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
  /** Modal popups trap Tab; a select list or a help popover does not (default: modal). */
  readonly modal?: boolean;
  /** Does a click outside close it? Decided per popup and tested. */
  readonly backdrop: "closes" | "stays";
  readonly scenarios?: readonly ScenarioName[];
  /** Reached only in this page state (see PageState: `prepare` leaves the page ready for the trigger). */
  readonly state?: string;
}

const EVERY_SCENARIO = ["empty"] as const;
/** The id of the seeded project of the `interior` scenarios (test/scenarios.ts `createInterior`). */
const INTERIOR_PROJECT = "00000000-0000-4000-8000-000000000901";
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
    id: "credits",
    path: "/app/credits",
    heading: "Raporty i zakupy",
    scenarios: ["shop", "shopHistory", "billingDisabled"],
  },
  {
    id: "success",
    path: `/app/credits/success?purchase=${SHOP_HISTORY[0]?.purchase_id ?? ""}`,
    heading: "Płatność",
    scenarios: ["shopHistory"],
    states: [
      {
        name: "waiting",
        path: `/app/credits/success?purchase=${SHOP_HISTORY[1]?.purchase_id ?? ""}`,
        scenario: "shopHistory",
        prepare: async (page) => {
          await page.getByText("Nie płać ponownie").waitFor();
        },
      },
    ],
  },
  {
    id: "interior.list",
    path: "/app/interior",
    heading: "Architekt wnętrz",
    scenarios: ["interior", "interiorEmpty", "interiorClosed"],
  },
  {
    id: "interior.project",
    path: `/app/interior/${INTERIOR_PROJECT}`,
    heading: "Salon",
    scenarios: ["interior", "interiorNoCatalogue"],
    states: [
      {
        // The catalogue answered: real-looking offers with the way to pick one exact variant.
        name: "search-results",
        scenario: () => createInterior({ rich: true }),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Czego szukasz" }).fill("sofa");
          await page.getByRole("button", { name: "Szukaj produktów" }).click();
          await page.getByRole("list", { name: "Znalezione produkty" }).waitFor();
        },
      },
      {
        // An own item opened for editing.
        name: "editing-item",
        scenario: () => createInterior({ rich: true }),
        prepare: async (page) => {
          await page.getByRole("button", { name: "Edytuj: Stary fotel" }).click();
          await page.getByRole("button", { name: "Zapisz rzecz" }).waitFor();
        },
      },
      {
        // A visualisation is queued and can still be cancelled.
        name: "generation-queued",
        scenario: () => createInterior({ rich: true, hold: true }),
        prepare: async (page) => {
          await page.getByRole("button", { name: "Generuj wizualizację z wersji 1" }).click();
          await page.getByRole("button", { name: "Anuluj wizualizację" }).waitFor();
        },
      },
      {
        // A visualisation ended without a usable answer: the way to a new attempt.
        name: "generation-failed",
        scenario: () => createInterior({ rich: true, failWith: "AMBIGUOUS" }),
        prepare: async (page) => {
          await page.getByRole("button", { name: "Generuj wizualizację z wersji 1" }).click();
          await page.getByRole("button", { name: "Spróbuj ponownie" }).waitFor({ timeout: 15_000 });
        },
      },
    ],
  },
  {
    id: "settings",
    path: "/app/settings",
    heading: "Ustawienia",
    scenarios: ["settings", "settingsOneSession", "settingsSessionsFailing", "settingsNoPassword"],
    states: [
      {
        name: "validation-errors",
        scenario: "settings",
        prepare: async (page) => {
          await page.getByRole("button", { name: "Zmień hasło" }).click();
          await page.getByRole("alert").filter({ hasText: "Popraw pola" }).waitFor();
        },
      },
    ],
  },
  {
    id: "pay",
    path: "/pay?_ptxn=txn_fixture0001",
    layout: "public",
    heading: "Płatność",
    scenarios: SIGNED_OUT,
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
        // The server created the audit for this request key; only the answer was lost.
        scenario: () => createRun({ post: { status: 0, networkError: true }, lostAnswer: true }),
        prepare: async (page) => {
          await submitListing(LISTING)(page);
          await page.getByRole("status").filter({ hasText: "Analiza została przyjęta" }).waitFor();
        },
      },
      {
        name: "ambiguous-not-received",
        scenario: () => createRun({ post: { status: 0, networkError: true } }),
        prepare: async (page) => {
          await submitListing(LISTING)(page);
          await page.getByRole("alert").filter({ hasText: "Analiza nie dotarła do serwera" }).waitFor();
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
    scenarios: ["empty", "collection", "slow", "auditsFailing", "savedLoaded"],
    states: [
      {
        name: "saved-view",
        scenario: () => createSaved(),
        prepare: async (page) => {
          await page.getByRole("button", { name: "Zapisane", exact: true }).click();
          await page.getByRole("list", { name: "Zapisane ogłoszenia" }).waitFor();
        },
      },
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
    heading: /^Ogłoszenie /,
    scenarios: ["loaded"],
    states: [
      {
        name: "saved-with-note",
        scenario: () => createSaved([[0, "Notatka testowa"]]),
        prepare: async (page) => {
          await page.getByRole("textbox", { name: "Twoja notatka" }).waitFor();
        },
      },
      {
        name: "returns",
        scenario: "loaded",
        prepare: async (page) => {
          await page.getByRole("button", { name: "Zwroty, wyjście i wrażliwość na wzrost cen" }).click();
        },
      },
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
  {
    id: "rynek.otodom",
    path: "/app/market/otodom",
    heading: "Rynek",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    states: [
      {
        name: "filtered",
        path: "/app/market/otodom?view=list&cohort=rooms_2",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Aktywny filtr: 2 pokoje").waitFor();
        },
      },
      {
        name: "selected",
        path: "/app/market/otodom?sel=bialystok",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByTestId("map-preview").waitFor();
        },
      },
      {
        name: "compare-empty",
        path: "/app/market/otodom?view=compare",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Wybierz co najmniej dwa miejsca").waitFor();
        },
      },
      {
        name: "compare",
        path: "/app/market/otodom?view=compare&ids=bialystok,bydgoszcz",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByRole("table", { name: "Porównanie miejsc" }).waitFor();
        },
      },
      {
        name: "overview-error",
        scenario: () => createMarket({ overviewFails: true }),
        prepare: async (page) => {
          await page.getByRole("alert").filter({ hasText: "Nie udało się wczytać miejsc" }).waitFor();
        },
      },
    ],
  },
  {
    id: "rynek.place",
    path: "/app/market/otodom/bialystok",
    heading: "Białystok",
    scenarios: ["market"],
    states: [
      {
        name: "no-districts",
        path: "/app/market/otodom/bydgoszcz",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Otodom nie wskazuje dzielnic dla tego miejsca").waitFor();
        },
      },
      {
        name: "unavailable",
        path: "/app/market/otodom/kielce",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Brak danych dla tego miejsca").waitFor();
        },
      },
      {
        name: "not-found",
        path: "/app/market/otodom/nie-ma-takiej",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Nie ma takiego miejsca").waitFor();
        },
      },
      {
        name: "detail-error",
        scenario: () => createMarket({ detailFails: true }),
        prepare: async (page) => {
          await page.getByRole("alert").filter({ hasText: "Nie udało się wczytać miejsca" }).waitFor();
        },
      },
      {
        name: "history-error",
        scenario: () => createMarket({ historyFails: true }),
        prepare: async (page) => {
          await page
            .getByRole("alert")
            .filter({ hasText: "Nie udało się wczytać historii odczytów" })
            .waitFor();
        },
      },
      {
        name: "districts-error",
        scenario: () => createMarket({ districtsFail: true }),
        prepare: async (page) => {
          await page.getByRole("alert").filter({ hasText: "Nie udało się wczytać dzielnic" }).waitFor();
        },
      },
    ],
  },
  {
    id: "rynek.district",
    path: "/app/market/otodom/bialystok/centrum",
    heading: "Centrum",
    scenarios: ["market"],
    states: [
      {
        name: "insufficient",
        path: "/app/market/otodom/bialystok/rubinkowo",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Za mało ofert z ceną, by podać medianę", { exact: true }).first().waitFor();
        },
      },
      {
        name: "unsupported",
        path: "/app/market/otodom/bydgoszcz/centrum",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Otodom nie wskazuje dzielnic dla tego miejsca").first().waitFor();
        },
      },
      {
        name: "missing",
        path: "/app/market/otodom/bialystok/nigdzie",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByText("Nie ma takiej dzielnicy w tym miejscu").waitFor();
        },
      },
    ],
  },
  {
    id: "rynek.gus",
    path: "/app/market/gus/bialystok",
    heading: "Białystok",
    scenarios: ["market", "marketFree"],
    states: [
      {
        name: "overview",
        path: "/app/market/gus",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByRole("table", { name: /Mianownik pozycji/ }).waitFor();
        },
      },
      {
        name: "compare",
        path: "/app/market/gus/bialystok?ids=bialystok,bydgoszcz",
        scenario: () => createMarket(),
        prepare: async (page) => {
          await page.getByRole("table", { name: "Porównanie wskaźników" }).waitFor();
        },
      },
      {
        name: "ranking-error",
        scenario: () => createMarket({ rankingFails: true }),
        prepare: async (page) => {
          await page
            .getByRole("alert")
            .filter({ hasText: "Nie udało się wczytać rankingu" })
            .first()
            .waitFor();
        },
      },
    ],
  },
  { id: "listing", path: "/app/listings/new", heading: "Stwórz ogłoszenie", scenarios: EVERY_SCENARIO },
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

  // Credits and purchases.
  {
    id: "credits.buy",
    page: "credits",
    scenarios: ["shop", "shopHistory"],
    role: "button",
    name: /^Kup pakiet /,
    outcome: "request",
  },
  {
    id: "credits.resume",
    page: "credits",
    scenarios: ["shopHistory"],
    role: "button",
    name: /^Dokończ płatność, zamówienie /,
    outcome: "request",
  },
  {
    id: "credits.invoice",
    page: "credits",
    scenarios: ["shopHistory"],
    role: "button",
    name: /^Pokaż fakturę, zamówienie /,
    outcome: "request",
  },
  { id: "success.analysis", page: "success", role: "link", name: "Sprawdź mieszkanie", outcome: "url" },
  { id: "success.purchases", page: "success", role: "link", name: "Wróć do zakupów", outcome: "url" },
  { id: "pay.credits", page: "pay", role: "link", name: "Wróć do zakupów", outcome: "url" },
  // Settings.
  {
    id: "settings.password.current",
    page: "settings",
    scenarios: PASSWORD_ACCOUNT,
    role: "textbox",
    name: "Obecne hasło",
    outcome: "state",
  },
  {
    id: "settings.password.next",
    page: "settings",
    scenarios: PASSWORD_ACCOUNT,
    role: "textbox",
    name: "Nowe hasło",
    outcome: "state",
  },
  {
    id: "settings.password.submit",
    page: "settings",
    scenarios: PASSWORD_ACCOUNT,
    role: "button",
    name: "Zmień hasło",
    outcome: "request",
  },
  {
    id: "settings.password.recover",
    page: "settings",
    scenarios: ["settingsNoPassword"],
    role: "link",
    name: "Ustaw hasło przez e-mail",
    outcome: "url",
  },
  {
    id: "settings.error.current",
    page: "settings",
    state: "validation-errors",
    role: "link",
    name: "Wpisz obecne hasło.",
    outcome: "focus",
  },
  {
    id: "settings.error.next",
    page: "settings",
    state: "validation-errors",
    role: "link",
    name: "Wpisz hasło.",
    outcome: "focus",
  },
  {
    id: "settings.sessions.retry",
    page: "settings",
    scenarios: ["settingsSessionsFailing"],
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  {
    id: "settings.signout-all",
    page: "settings",
    role: "button",
    name: "Wyloguj ze wszystkich urządzeń",
    outcome: "dialog",
  },
  {
    id: "settings.signout-all.close",
    page: "settings",
    within: "settings.signout-all",
    role: "button",
    name: "Zamknij",
    outcome: "dialog",
  },
  {
    id: "settings.signout-all.cancel",
    page: "settings",
    within: "settings.signout-all",
    role: "button",
    name: "Anuluj",
    outcome: "dialog",
  },
  {
    id: "settings.signout-all.confirm",
    page: "settings",
    within: "settings.signout-all",
    role: "button",
    name: "Wyloguj wszędzie",
    outcome: "url",
  },
  { id: "settings.export", page: "settings", role: "button", name: "Pobierz moje dane", outcome: "request" },
  { id: "settings.erase.open", page: "settings", role: "button", name: "Usuń konto", outcome: "dialog" },
  {
    id: "settings.erase.close",
    page: "settings",
    within: "settings.erase",
    role: "button",
    name: "Zamknij",
    outcome: "dialog",
  },
  {
    id: "settings.erase.email",
    page: "settings",
    within: "settings.erase",
    role: "textbox",
    name: "Adres e-mail konta",
    outcome: "state",
  },
  {
    id: "settings.erase.cancel",
    page: "settings",
    within: "settings.erase",
    role: "button",
    name: "Anuluj",
    outcome: "dialog",
  },
  {
    id: "settings.erase.confirm",
    page: "settings",
    within: "settings.erase",
    role: "button",
    name: "Usuń konto na stałe",
    outcome: "url",
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
  { id: "dashboard.interior", page: "dashboard", role: "link", name: "Otwórz architekta", outcome: "url" },
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

  // Rynek: two tabs (Otodom, GUS), the filters, the map, the comparison, a place, a district, the ranking (RM-439).
  ...(["rynek.otodom", "rynek.place", "rynek.district", "rynek.gus"] as const).flatMap(
    (page): Interaction[] => [
      { id: `${page}.tab.otodom`, page, role: "link", name: /^Otodom/, outcome: "url" },
      { id: `${page}.tab.gus`, page, role: "link", name: /^GUS/, outcome: "url" },
    ],
  ),
  ...(["rynek.otodom", "rynek.place", "rynek.district"] as const).flatMap((page): Interaction[] => [
    {
      id: `${page}.filter.area`,
      page,
      role: "radio",
      name: /^(Poniżej 30 m²|30 do 45 m²|45 do 60 m²|60 do 80 m²|80 m² i więcej)$/,
      outcome: "url",
    },
    {
      id: `${page}.filter.rooms`,
      page,
      role: "radio",
      name: /^(1 pokój|2 pokoje|3 pokoje|4 pokoje i więcej)$/,
      outcome: "url",
    },
  ]),
  {
    id: "rynek.otodom.filter.reset",
    page: "rynek.otodom",
    state: "filtered",
    role: "button",
    name: "Wyczyść filtr",
    outcome: "url",
  },
  {
    id: "rynek.otodom.view.map",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: "Mapa",
    outcome: "url",
  },
  {
    id: "rynek.otodom.view.list",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: "Lista",
    outcome: "url",
  },
  {
    id: "rynek.otodom.metric",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "combobox",
    name: "Co pokazuje kolor",
    outcome: "url",
  },
  {
    id: "rynek.otodom.sort",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "combobox",
    name: "Kolejność na liście",
    outcome: "url",
  },
  {
    id: "rynek.otodom.compare-cta",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: /^Porównaj miejsca/,
    outcome: "url",
  },
  {
    id: "rynek.map.zoom-in",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: "Przybliż mapę",
    outcome: "state",
  },
  {
    id: "rynek.map.zoom-out",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: "Oddal mapę",
    outcome: "state",
  },
  {
    id: "rynek.map.reset",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: "Pokaż całą Polskę",
    outcome: "state",
  },
  {
    id: "rynek.map.cluster",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: /^Skupisko: /,
    outcome: "state",
  },
  {
    id: "rynek.map.marker",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: /: (?:\d|za mało ofert|brak danych)/,
    outcome: "url",
  },
  {
    id: "rynek.otodom.search",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "textbox",
    name: "Szukaj miejsca na liście",
    outcome: "state",
  },
  {
    id: "rynek.otodom.pick",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: /^Wybierz miejsce /,
    outcome: "url",
  },
  {
    id: "rynek.otodom.open",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "link",
    name: /^Otwórz miejsce /,
    outcome: "url",
  },
  {
    id: "rynek.otodom.compare-toggle",
    page: "rynek.otodom",
    scenarios: ["market", "marketFree", "marketUnlimited"],
    role: "button",
    name: /^(Dodaj do porównania|Usuń z porównania) /,
    outcome: "url",
  },
  {
    id: "rynek.otodom.more",
    page: "rynek.otodom",
    scenarios: ["market", "marketUnlimited"],
    role: "button",
    name: "Pokaż więcej miejsc",
    outcome: "state",
  },
  {
    id: "rynek.otodom.upgrade",
    page: "rynek.otodom",
    scenarios: ["marketFree"],
    role: "link",
    name: "Kup pakiet raportów",
    outcome: "url",
  },
  {
    id: "rynek.otodom.retry",
    page: "rynek.otodom",
    state: "overview-error",
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  {
    id: "rynek.preview.open",
    page: "rynek.otodom",
    state: "selected",
    role: "link",
    name: "Otwórz miejsce",
    outcome: "url",
  },
  {
    id: "rynek.preview.close",
    page: "rynek.otodom",
    state: "selected",
    role: "button",
    name: "Zamknij podgląd",
    outcome: "url",
  },
  {
    id: "rynek.preview.compare",
    page: "rynek.otodom",
    state: "selected",
    role: "button",
    name: /^(Dodaj do porównania|Usuń z porównania|Limit porównania osiągnięty)$/,
    outcome: "url",
  },
  {
    id: "rynek.compare.back",
    page: "rynek.otodom",
    state: "compare",
    role: "button",
    name: "Wróć do mapy",
    outcome: "url",
  },
  {
    id: "rynek.compare.clear",
    page: "rynek.otodom",
    state: "compare",
    role: "button",
    name: "Wyczyść porównanie",
    outcome: "url",
  },
  {
    id: "rynek.compare.search",
    page: "rynek.otodom",
    state: "compare",
    role: "textbox",
    name: "Szukaj miejsca do dodania",
    outcome: "state",
  },
  {
    id: "rynek.compare.place",
    page: "rynek.otodom",
    state: "compare",
    role: "link",
    name: /^[A-ZĄĆĘŁŃÓŚŹŻ][\p{L} -]+$/u,
    outcome: "url",
  },
  {
    id: "rynek.compare.back-empty",
    page: "rynek.otodom",
    state: "compare-empty",
    role: "button",
    name: "Wróć do mapy",
    outcome: "url",
  },
  {
    id: "rynek.compare.add-empty",
    page: "rynek.otodom",
    state: "compare-empty",
    role: "button",
    name: /^Dodaj do porównania /,
    outcome: "url",
  },
  {
    id: "rynek.compare.search-empty",
    page: "rynek.otodom",
    state: "compare-empty",
    role: "textbox",
    name: "Szukaj miejsca do dodania",
    outcome: "state",
  },
  // The place page.
  { id: "rynek.place.crumb", page: "rynek.place", role: "link", name: "Otodom", outcome: "url" },
  { id: "rynek.place.back", page: "rynek.place", role: "link", name: "Wszystkie miejsca", outcome: "url" },
  {
    id: "rynek.place.series.cohort",
    page: "rynek.place",
    role: "button",
    name: "Okno 90 dób",
    outcome: "url",
  },
  {
    id: "rynek.place.series.additions",
    page: "rynek.place",
    role: "button",
    name: "Nowe ogłoszenia dnia",
    outcome: "url",
  },
  ...([30, 90, 365] as const).map((days): Interaction => ({
    id: `rynek.place.period.${String(days)}`,
    page: "rynek.place",
    role: "button",
    name: `${String(days)} dni`,
    outcome: "url",
  })),
  {
    id: "rynek.place.group",
    page: "rynek.place",
    role: "button",
    name: /^Pokaż tylko grupę /,
    outcome: "url",
  },
  {
    id: "rynek.place.district-bar",
    page: "rynek.place",
    role: "link",
    name: /^(Centrum|Północ|Południe|Rubinkowo)$/,
    outcome: "url",
  },
  { id: "rynek.place.gus", page: "rynek.place", role: "link", name: "Zobacz profil GUS", outcome: "url" },
  {
    id: "rynek.place.back-nodistricts",
    page: "rynek.place",
    state: "no-districts",
    role: "link",
    name: "Wszystkie miejsca",
    outcome: "url",
  },
  {
    id: "rynek.place.back-unavailable",
    page: "rynek.place",
    state: "unavailable",
    role: "link",
    name: "Wszystkie miejsca",
    outcome: "url",
  },
  {
    id: "rynek.place.back-notfound",
    page: "rynek.place",
    state: "not-found",
    role: "link",
    name: "Wszystkie miejsca",
    outcome: "url",
  },
  {
    id: "rynek.place.retry-detail",
    page: "rynek.place",
    state: "detail-error",
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  {
    id: "rynek.place.retry-history",
    page: "rynek.place",
    state: "history-error",
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  {
    id: "rynek.place.retry-districts",
    page: "rynek.place",
    state: "districts-error",
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  // The district page.
  { id: "rynek.district.crumb", page: "rynek.district", role: "link", name: "Otodom", outcome: "url" },
  {
    id: "rynek.district.crumb-place",
    page: "rynek.district",
    role: "link",
    name: /^(Białystok|Bydgoszcz)$/,
    outcome: "url",
  },
  { id: "rynek.district.back", page: "rynek.district", role: "link", name: /^Wróć do: /, outcome: "url" },
  {
    id: "rynek.district.other",
    page: "rynek.district",
    role: "link",
    name: /^(Północ|Południe|Rubinkowo|Centrum)$/,
    outcome: "url",
  },
  // The GUS tab.
  {
    id: "rynek.gus.picker.search",
    page: "rynek.gus",
    scenarios: ["market", "marketFree"],
    role: "textbox",
    name: "Miejsce",
    outcome: "state",
  },
  {
    id: "rynek.gus.picker.pick",
    page: "rynek.gus",
    scenarios: ["market", "marketFree"],
    role: "button",
    name: /^[A-ZĄĆĘŁŃÓŚŹŻ][\p{L} -]+$/u,
    outcome: "url",
  },
  {
    id: "rynek.gus.leaderboard.pick",
    page: "rynek.gus",
    scenarios: ["market", "marketFree"],
    role: "button",
    name: /^Pokaż wynik /,
    outcome: "url",
  },
  {
    id: "rynek.gus.leaderboard.compare",
    page: "rynek.gus",
    scenarios: ["market", "marketFree"],
    role: "button",
    name: /^(Dodaj do porównania|Usuń z porównania) /,
    outcome: "url",
  },
  {
    id: "rynek.gus.leaderboard.more",
    page: "rynek.gus",
    scenarios: ["market"],
    role: "button",
    name: "Pokaż więcej miejsc",
    outcome: "state",
  },
  {
    id: "rynek.gus.component",
    page: "rynek.gus",
    scenarios: ["market", "marketFree"],
    role: "link",
    name: /^Szczegóły wskaźnika: /,
    outcome: "url",
  },
  {
    id: "rynek.gus.retry",
    page: "rynek.gus",
    state: "ranking-error",
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
  {
    id: "dashboard.market",
    page: "dashboard",
    role: "link",
    name: "Otwórz Rynek",
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
  // The options exist only while a select is open: they are inventoried inside its popup (`POPUPS`), together with
  // the list that holds them.
  {
    id: "analyses.status.listbox",
    page: "analyses",
    role: "listbox",
    name: "Status",
    outcome: "state",
    within: "analyses.status.list",
  },
  {
    id: "analyses.grade.listbox",
    page: "analyses",
    role: "listbox",
    name: "Ocena",
    outcome: "state",
    within: "analyses.grade.list",
  },
  {
    id: "analyses.option.all",
    page: "analyses",
    role: "option",
    name: "Wszystkie",
    outcome: "url",
    within: "analyses.status.list",
  },
  {
    id: "analyses.option.grade-all",
    page: "analyses",
    role: "option",
    name: "Wszystkie",
    outcome: "url",
    within: "analyses.grade.list",
  },
  ...[
    ["ready", "Gotowe", "analyses.status.list"],
    ["active", "W toku", "analyses.status.list"],
    ["rejected", "Odrzucone", "analyses.status.list"],
    ["failed", "Nieudane", "analyses.status.list"],
    ["grade-A", "A", "analyses.grade.list"],
    ["grade-B", "B", "analyses.grade.list"],
    ["grade-C", "C", "analyses.grade.list"],
    ["grade-D", "D", "analyses.grade.list"],
    ["grade-E", "E", "analyses.grade.list"],
    ["grade-N", "Bez oceny", "analyses.grade.list"],
  ].map(([id = "", label = "", within = ""]): Interaction => ({
    id: `analyses.option.${id}`,
    page: "analyses",
    role: "option",
    name: label,
    outcome: "url",
    within,
  })),
  {
    id: "analyses.row",
    page: "analyses",
    scenarios: ["collection", "savedLoaded"],
    role: "link",
    name: /^Ogłoszenie ID(LST|FIX)/,
    outcome: "url",
  },
  {
    id: "analyses.scope.all",
    page: "analyses",
    role: "button",
    name: "Wszystkie analizy",
    outcome: "url",
  },
  { id: "analyses.scope.saved", page: "analyses", role: "button", name: "Zapisane", outcome: "url" },
  {
    id: "analyses.save",
    page: "analyses",
    scenarios: ["collection", "savedLoaded"],
    role: "button",
    name: /^Zapisz ogłoszenie ID/,
    outcome: "request",
  },
  {
    id: "analyses.saved.open",
    page: "analyses",
    state: "saved-view",
    role: "link",
    name: /^Otwórz analizę/,
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
  {
    id: "report.all.rejected",
    page: "report",
    state: "rejected",
    role: "link",
    name: "Moje analizy",
    outcome: "url",
  },
  {
    id: "report.all.failed",
    page: "report",
    state: "failed",
    role: "link",
    name: "Moje analizy",
    outcome: "url",
  },
  {
    id: "report.all.notfound",
    page: "report",
    state: "not-found",
    role: "link",
    name: "Moje analizy",
    outcome: "url",
  },
  {
    id: "report.save",
    page: "report",
    role: "button",
    name: "Zapisz to ogłoszenie",
    outcome: "request",
  },
  {
    id: "report.note",
    page: "report",
    state: "saved-with-note",
    role: "textbox",
    name: "Twoja notatka",
    outcome: "state",
  },
  {
    id: "report.note.save",
    page: "report",
    state: "saved-with-note",
    role: "button",
    name: "Zapisz notatkę",
    outcome: "request",
  },
  ...[
    ["close", "Zamknij", "dialog"],
    ["cancel", "Anuluj", "dialog"],
    ["confirm", "Usuń z zapisanych", "request"],
  ].map(([id = "", label = "", outcome = ""]): Interaction => ({
    id: `report.unsave.${id}`,
    page: "report",
    state: "saved-with-note",
    within: "report.unsave",
    role: "button",
    name: label,
    outcome: outcome as Interaction["outcome"],
  })),
  // Help beside a return measure: a button that opens a popover (`POPUPS`).
  {
    id: "report.help.asking",
    page: "report",
    role: "button",
    name: "Co oznacza: Zwrot przy cenie ofertowej",
    outcome: "dialog",
  },
  ...[
    ["irr", "Roczna stopa zwrotu"],
    ["cagr", "Średni roczny wzrost kapitału"],
    ["moic", "Mnożnik zainwestowanego kapitału"],
  ].map(([id = "", label = ""]): Interaction => ({
    id: `report.help.${id}`,
    page: "report",
    state: "returns",
    role: "button",
    name: `Co oznacza: ${label}`,
    outcome: "dialog",
  })),
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
  // ----------------------------------------------------------------------------------- Architekt wnętrz (RM-451)
  {
    id: "interior.list.name",
    page: "interior.list",
    scenarios: ["interior", "interiorEmpty"],
    role: "textbox",
    name: "Nazwa projektu",
    outcome: "state",
  },
  {
    id: "interior.list.room",
    page: "interior.list",
    scenarios: ["interior", "interiorEmpty"],
    role: "combobox",
    name: "Rodzaj pokoju",
    outcome: "text",
  },
  {
    id: "interior.list.create",
    page: "interior.list",
    scenarios: ["interior", "interiorEmpty"],
    role: "button",
    name: "Utwórz projekt",
    outcome: "url",
  },
  {
    id: "interior.list.open",
    page: "interior.list",
    scenarios: ["interior"],
    role: "link",
    name: /^Otwórz projekt /,
    outcome: "url",
  },
  {
    id: "interior.list.delete",
    page: "interior.list",
    scenarios: ["interior"],
    role: "button",
    name: /^Usuń projekt /,
    outcome: "dialog",
  },
  ...[
    ["close", "Zamknij", "dialog"],
    ["cancel", "Anuluj", "dialog"],
    ["confirm", "Usuń projekt", "request"],
  ].map(([id = "", label = "", outcome = ""]): Interaction => ({
    id: `interior.delete.${id}`,
    page: "interior.list",
    scenarios: ["interior"],
    within: "interior.delete",
    role: "button",
    name: label,
    outcome: outcome as Interaction["outcome"],
  })),
  {
    id: "interior.project.back",
    page: "interior.project",
    role: "link",
    name: "Wszystkie projekty",
    outcome: "url",
  },
  {
    id: "interior.project.photo",
    page: "interior.project",
    role: "button",
    name: "Wybierz zdjęcie pokoju",
    outcome: "request",
  },
  {
    id: "interior.brief.name",
    page: "interior.project",
    role: "textbox",
    name: "Nazwa projektu",
    outcome: "state",
  },
  {
    id: "interior.brief.room",
    page: "interior.project",
    role: "combobox",
    name: "Rodzaj pokoju",
    outcome: "text",
  },
  { id: "interior.brief.style", page: "interior.project", role: "textbox", name: "Styl", outcome: "state" },
  {
    id: "interior.brief.budget",
    page: "interior.project",
    role: "textbox",
    name: "Budżet na wyposażenie (zł)",
    outcome: "state",
  },
  {
    id: "interior.brief.keep",
    page: "interior.project",
    role: "textbox",
    name: "Rzeczy, które zostają",
    outcome: "state",
  },
  {
    id: "interior.brief.notes",
    page: "interior.project",
    role: "textbox",
    name: "Dodatkowe życzenia",
    outcome: "state",
  },
  {
    id: "interior.brief.save",
    page: "interior.project",
    role: "button",
    name: "Zapisz założenia",
    outcome: "request",
  },
  {
    id: "interior.item.name",
    page: "interior.project",
    role: "textbox",
    name: "Nazwa rzeczy",
    outcome: "state",
  },
  {
    id: "interior.item.quantity",
    page: "interior.project",
    role: "textbox",
    name: "Liczba sztuk",
    outcome: "state",
  },
  {
    id: "interior.item.price",
    page: "interior.project",
    role: "textbox",
    name: "Cena za sztukę (zł, opcjonalnie)",
    outcome: "state",
  },
  {
    id: "interior.item.url",
    page: "interior.project",
    role: "textbox",
    name: "Link (opcjonalnie)",
    outcome: "state",
  },
  {
    id: "interior.item.add",
    page: "interior.project",
    role: "button",
    name: "Dodaj rzecz",
    outcome: "request",
  },
  {
    id: "interior.item.photo",
    page: "interior.project",
    role: "button",
    name: /^Dodaj zdjęcie: /,
    outcome: "request",
  },
  { id: "interior.item.edit", page: "interior.project", role: "button", name: /^Edytuj: /, outcome: "text" },
  {
    id: "interior.item.remove",
    page: "interior.project",
    role: "button",
    name: /^Usuń: /,
    outcome: "request",
  },
  {
    id: "interior.item.save",
    page: "interior.project",
    state: "editing-item",
    role: "button",
    name: "Zapisz rzecz",
    outcome: "request",
  },
  {
    id: "interior.item.cancel",
    page: "interior.project",
    state: "editing-item",
    role: "button",
    name: "Anuluj edycję",
    outcome: "text",
  },
  {
    id: "interior.catalogue.query",
    page: "interior.project",
    scenarios: ["interior"],
    role: "textbox",
    name: "Czego szukasz",
    outcome: "state",
  },
  {
    id: "interior.catalogue.category",
    page: "interior.project",
    scenarios: ["interior"],
    role: "combobox",
    name: "Kategoria",
    outcome: "text",
  },
  {
    id: "interior.catalogue.maxprice",
    page: "interior.project",
    scenarios: ["interior"],
    role: "textbox",
    name: "Cena najwyżej (zł)",
    outcome: "state",
  },
  {
    id: "interior.catalogue.search",
    page: "interior.project",
    scenarios: ["interior"],
    role: "button",
    name: "Szukaj produktów",
    outcome: "request",
  },
  {
    id: "interior.catalogue.pick",
    page: "interior.project",
    state: "search-results",
    role: "button",
    name: /^Wybierz: /,
    outcome: "request",
  },
  {
    id: "interior.offer.link",
    page: "interior.project",
    role: "link",
    name: /^Otwórz stronę produktu: /,
    outcome: "state",
  },
  {
    id: "interior.board.decrease",
    page: "interior.project",
    role: "button",
    name: /^Zmniejsz liczbę sztuk: /,
    outcome: "request",
  },
  {
    id: "interior.board.increase",
    page: "interior.project",
    role: "button",
    name: /^Zwiększ liczbę sztuk: /,
    outcome: "request",
  },
  {
    id: "interior.board.refresh",
    page: "interior.project",
    role: "button",
    name: /^Sprawdź ponownie: /,
    outcome: "request",
  },
  {
    id: "interior.board.remove",
    page: "interior.project",
    role: "button",
    name: /^Usuń z tablicy: /,
    outcome: "request",
  },
  {
    id: "interior.revision.save",
    page: "interior.project",
    role: "button",
    name: "Zapisz wersję",
    outcome: "request",
  },
  {
    id: "interior.generation.start",
    page: "interior.project",
    role: "button",
    name: /^Generuj wizualizację z wersji /,
    outcome: "request",
  },
  {
    id: "interior.generation.cancel",
    page: "interior.project",
    state: "generation-queued",
    role: "button",
    name: "Anuluj wizualizację",
    outcome: "request",
  },
  {
    id: "interior.generation.retry",
    page: "interior.project",
    state: "generation-failed",
    role: "button",
    name: "Spróbuj ponownie",
    outcome: "request",
  },
];

export const POPUPS: readonly Popup[] = [
  {
    id: "analyses.status.list",
    page: "analyses",
    trigger: "analyses.status",
    role: "listbox",
    name: "Status",
    backdrop: "closes",
    modal: false,
    scenarios: ["collection"],
  },
  {
    id: "analyses.grade.list",
    page: "analyses",
    trigger: "analyses.grade",
    role: "listbox",
    name: "Ocena",
    backdrop: "closes",
    modal: false,
    scenarios: ["collection"],
  },
  {
    id: "report.help.asking",
    page: "report",
    trigger: "report.help.asking",
    role: "dialog",
    name: /^IRR, czyli wewnętrzna stopa zwrotu$/,
    backdrop: "closes",
    modal: false,
  },
  ...[
    ["irr", /^IRR, czyli wewnętrzna stopa zwrotu$/],
    ["cagr", /^CAGR, czyli złożona roczna stopa wzrostu$/],
    ["moic", /^MOIC, czyli mnożnik zainwestowanego kapitału$/],
  ].map(([id = "", name = ""]): Popup => ({
    id: `report.help.${id}`,
    page: "report",
    state: "returns",
    trigger: `report.help.${id}`,
    role: "dialog",
    name,
    backdrop: "closes",
    modal: false,
  })),
  {
    id: "report.unsave",
    page: "report",
    state: "saved-with-note",
    trigger: "report.save",
    role: "dialog",
    name: "Usunąć z zapisanych?",
    backdrop: "closes",
  },
  {
    id: "settings.signout-all",
    page: "settings",
    trigger: "settings.signout-all",
    role: "dialog",
    name: "Wylogować ze wszystkich urządzeń?",
    backdrop: "closes",
    scenarios: ["settings"],
  },
  {
    id: "settings.erase",
    page: "settings",
    trigger: "settings.erase.open",
    role: "dialog",
    name: "Usunąć konto na stałe?",
    backdrop: "closes",
    scenarios: ["settings"],
  },
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
  {
    id: "interior.delete",
    page: "interior.list",
    scenarios: ["interior"],
    trigger: "interior.list.delete",
    role: "dialog",
    name: "Usunąć projekt?",
    backdrop: "closes",
  },
];
