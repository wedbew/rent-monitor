/**
 * The scenario registry: named, typed states of the API that screens are built and tested against (#268).
 * A scenario is plain data (routes and replies), so the same registry feeds Vitest (through MSW, test/handlers.ts),
 * the component catalog and the Playwright mocked lane. A request no route matches is a test failure, never an
 * empty success.
 *
 * Replies come from sanitised fixtures. The loaded states are built from the five distinct `succeeded` audits of the
 * capture so a list row, its detail and its progress stream tell one consistent story.
 */
import type { components } from "../api/schema.generated";
import { bodyOf, eventStreamText, fx, type Fixture, type HttpMethod } from "./fixtures";

type AuditOut = components["schemas"]["AuditOut"];
type AuditPage = components["schemas"]["AuditPage"];
type AuditSummary = components["schemas"]["AuditSummary"];
type MeDetail = components["schemas"]["MeDetailOut"];

export interface MockRequest {
  readonly method: HttpMethod;
  readonly url: URL;
  readonly params: Readonly<Record<string, string>>;
  readonly body: unknown;
  /** Request headers, lower-case names (an `Idempotency-Key`, for example). */
  readonly headers: Readonly<Record<string, string>>;
}

export interface Reply {
  readonly status: number;
  readonly body?: unknown;
  readonly text?: string;
  readonly contentType?: string;
  readonly headers?: Readonly<Record<string, string>>;
  /** The request fails before any answer, like a dropped connection. */
  readonly networkError?: true;
  /** Answer after this many milliseconds (a loading state worth looking at). */
  readonly delayMs?: number;
}

export interface Route {
  /** `"GET /api/audits/{audit_id}"`: the OpenAPI operation key. */
  readonly operation: string;
  readonly reply: Reply | ((request: MockRequest) => Reply);
}

export interface Scenario {
  readonly name: string;
  readonly description: string;
  readonly routes: readonly Route[];
}

export function replyFrom(fixture: Fixture): Reply {
  if (fixture.events !== undefined) {
    return {
      status: fixture.status,
      text: eventStreamText(fixture.events),
      contentType: "text/event-stream",
      headers: fixture.headers,
    };
  }
  return {
    status: fixture.status,
    body: fixture.body,
    contentType: fixture.content_type,
    headers: fixture.headers,
  };
}

const fromFixture = (operation: string, scenario: string): Route => ({
  operation,
  reply: replyFrom(fx(operation, scenario)),
});

// ------------------------------------------------------------------------------------------------ audits
export const SUCCEEDED_SCENARIOS = ["warszawa", "krakow", "lodz", "gdansk", "torun"].map(
  (c) => `succeeded_${c}`,
);

/** Spread creation times so ordering is visible: audit 0 is the newest. */
function stamped(audit: AuditOut, index: number): AuditOut {
  const base = Date.parse("2026-10-01T10:00:00Z") - index * 3_600_000;
  const at = (offsetS: number) => new Date(base + offsetS * 1000).toISOString().replace(".000Z", "Z");
  return { ...audit, created_at: at(0), started_at: at(2), finished_at: at(38) };
}

export function summaryOf(audit: AuditOut): AuditSummary {
  return {
    audit_id: audit.audit_id,
    otodom_id: audit.otodom_id,
    status: audit.status,
    error_code: audit.error_code,
    created_at: audit.created_at,
    finished_at: audit.finished_at,
    grade: audit.grade,
    asking_price_pln: audit.asking_price_pln,
    max_bid_pln: audit.max_bid_pln,
  };
}

/** Five distinct finished audits, newest first, each with its progress stream. */
export const SUCCEEDED_AUDITS: readonly AuditOut[] = SUCCEEDED_SCENARIOS.map((name, i) =>
  stamped(bodyOf<AuditOut>(fx("GET /api/audits/{audit_id}", name)), i),
);

function page(audits: readonly AuditOut[]): AuditPage {
  return { items: audits.map(summaryOf), next_cursor: null };
}

function auditRoutes(audits: readonly AuditOut[]): Route[] {
  return [
    {
      operation: "GET /api/audits",
      reply: (request) => {
        const limit = Number(request.url.searchParams.get("limit") ?? "50");
        return { status: 200, body: { ...page(audits), items: page(audits).items.slice(0, limit) } };
      },
    },
    {
      operation: "GET /api/audits/{audit_id}",
      reply: (request) => {
        const found = audits.find((a) => a.audit_id === request.params["audit_id"]);
        return found === undefined
          ? replyFrom(fx("GET /api/audits/{audit_id}", "unknown_audit"))
          : { status: 200, body: found };
      },
    },
    fromFixture("GET /api/audits/{audit_id}/events", "success_transcript"),
  ];
}

// -------------------------------------------------------------------------------------------------- base
const me = (scenario: string): Route => fromFixture("GET /api/me", scenario);

function withMe(patch: (body: MeDetail) => MeDetail, scenario = "with_credits_and_flags"): Route {
  const body = patch(bodyOf<MeDetail>(fx("GET /api/me", scenario)));
  return { operation: "GET /api/me", reply: { status: 200, body } };
}

const PACKS = fromFixture("GET /api/billing/packs", "three_packs");
const SAVED_EMPTY = fromFixture("GET /api/saved", "empty");
export const EMPTY_PAGE: Route = {
  operation: "GET /api/audits",
  reply: { status: 200, body: { items: [], next_cursor: null } satisfies AuditPage },
};

/** Routes any signed-in screen needs. A scenario replaces a route by repeating its operation. */
const PURCHASES_EMPTY = fromFixture("GET /api/billing/purchases", "empty");
/** Until a scenario says otherwise nothing is published, so /app/market renders its empty state. */
const MARKET_EMPTY: Route = {
  operation: "GET /api/market/locations",
  reply: { status: 200, body: { items: [], next_cursor: null } },
};
const OVERVIEW_EMPTY: Route = {
  operation: "GET /api/market/overview",
  reply: {
    status: 200,
    body: {
      items: [],
      total_places: 0,
      visible_places: 0,
      access: "full",
      free_limit: 20,
      free_rule_pl: "Darmowe konto widzi 20 miejsc z największą liczbą opublikowanych ofert z ceną.",
    },
  },
};
const SIGNED_IN: readonly Route[] = [
  me("with_credits_and_flags"),
  PACKS,
  PURCHASES_EMPTY,
  SAVED_EMPTY,
  EMPTY_PAGE,
  MARKET_EMPTY,
  OVERVIEW_EMPTY,
];

function scenario(
  name: string,
  description: string,
  routes: readonly Route[],
  base: readonly Route[] = SIGNED_IN,
): Scenario {
  const replaced = new Set(routes.map((r) => r.operation));
  return { name, description, routes: [...routes, ...base.filter((r) => !replaced.has(r.operation))] };
}

const MIXED_SCENARIOS = [
  "queued_not_yet_run",
  "succeeded_degraded",
  "rejected_rent_is_not_a_deal",
  "failed_upstream_blocked",
  "failed_input_listing_gone",
  "succeeded_krakow",
] as const;

/** Six analyses in six different states, newest first: what a real, busy account looks like. */
export const MIXED_AUDITS: readonly AuditOut[] = MIXED_SCENARIOS.map((name, i) =>
  stamped(bodyOf<AuditOut>(fx("GET /api/audits/{audit_id}", name)), i),
);

const NOT_READY = {
  type: "urn:rentmonitor:problem:NOT_READY",
  title: "Service not ready",
  status: 503,
  code: "NOT_READY",
  instance: "/api/audits",
  detail: null,
  errors: null,
  request_id: "req_fixture",
};

/** The first finished audit with its stored result changed: for the report states a capture cannot show. */
function withResult(
  patch: (result: Record<string, unknown>) => Record<string, unknown>,
): readonly AuditOut[] {
  const [first] = SUCCEEDED_AUDITS;
  if (first === undefined) throw new Error("no succeeded audit fixture");
  return [{ ...first, result: patch(structuredClone(first.result as Record<string, unknown>)) }];
}

// ------------------------------------------------------------------------------------------------ market
type LocationSummary = components["schemas"]["LocationSummaryOut"];
type LocationDetail = components["schemas"]["LocationDetailOut"];
type AskingRent = components["schemas"]["AskingRentOut"];

export interface MarketOptions {
  /** How many places the catalogue has (default 38: two pages of 30). */
  readonly count?: number;
  /** The catalogue has places but nothing is published yet: the list is empty. */
  readonly empty?: boolean;
  /** Requests for list pages after the first fail with a 503 until `state.failing` is set false. */
  readonly failPage?: number;
  /** The first page of the list cannot be read. */
  readonly listFails?: boolean;
  /** The place cannot be read. */
  readonly detailFails?: boolean;
  /** The history cannot be read (or answers 429 with a Retry-After). */
  readonly historyFails?: boolean | "rate-limited";
  /** The history answers after this many milliseconds. */
  readonly historyDelayMs?: number;
  /** The history has no published day at all. */
  readonly historyEmpty?: boolean;
  /** A free account: the overview shows only the first `FREE_VISIBLE` places and the rest answer 403. */
  readonly free?: boolean;
  /** The overview cannot be read. */
  readonly overviewFails?: boolean;
  /** The context of a place cannot be read. */
  readonly contextFails?: boolean;
  /** The districts of a place cannot be read. */
  readonly districtsFail?: boolean;
  /** The experimental index cannot be read. */
  readonly rankingFails?: boolean;
  /** No place has any district at the source. */
  readonly noDistricts?: boolean;
  /** The account holds the no-limit entitlement (zero balance, full market). */
  readonly unlimited?: boolean;
}

type OverviewOut = components["schemas"]["OverviewOut"];
type OverviewPlaceOut = components["schemas"]["OverviewPlaceOut"];
type LocationContextOut = components["schemas"]["LocationContextOut"];

/** Real TERYT codes of gminas in the committed geometry, so the map has areas to draw. */
const MARKET_TERYT = [
  "0201011",
  "0209062",
  "0220042",
  "0402062",
  "0411032",
  "0419033",
  "0604062",
  "0610033",
  "0618032",
  "0804043",
  "1001032",
  "1009013",
  "1015062",
  "1201092",
  "1208022",
  "1214023",
  "1402033",
  "1410023",
  "1416072",
  "1423032",
  "1429082",
  "1465011",
  "1610023",
  "1807083",
  "1815033",
  "2002063",
  "2010011",
  "2203011",
  "2212022",
  "2402072",
  "2408052",
  "2417042",
  "2604092",
  "2612053",
  "2808053",
  "2819012",
  "3008072",
  "3017052",
  "3024063",
  "3203052",
];
export const FREE_VISIBLE = 20;

export interface Market extends Scenario {
  readonly state: { requests: string[]; failing: boolean };
  readonly places: readonly LocationSummary[];
}

const CITY_NAMES = [
  "Białystok", "Bydgoszcz", "Bytom", "Chorzów", "Częstochowa", "Elbląg", "Gdańsk", "Gdynia", "Gliwice",
  "Gorzów Wielkopolski", "Grudziądz", "Kalisz", "Katowice", "Kielce", "Koszalin", "Kraków", "Legnica", "Lublin",
  "Łódź", "Olsztyn", "Opole", "Płock", "Poznań", "Radom", "Rybnik", "Rzeszów", "Sopot", "Sosnowiec", "Szczecin",
  "Tarnów", "Toruń", "Tychy", "Wałbrzych", "Warszawa", "Włocławek", "Wrocław", "Zabrze", "Zielona Góra",
]; // prettier-ignore

const MARKET_DAY = "2026-10-19";
const MARKET_REFRESH = "2026-10-19T04:00:00Z";
const MARKET_CAVEATS = ["asking_not_achieved_rent", "not_active_stock", "not_deed_price"];
const COHORT_FACTOR: Record<string, number> = {
  all: 1,
  rooms_1: 0.9,
  rooms_2: 1.1,
  rooms_3: 1.3,
  rooms_4plus: 1.6,
  size_lt30: 0.8,
  size_30_45: 1,
  size_45_60: 1.25,
  size_60_80: 1.4,
  size_80plus: 1.8,
};

const slug = (name: string) =>
  name
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/ł/g, "l")
    .replace(/[^a-z0-9]+/g, "-");

function marketPlace(name: string, i: number): LocationSummary {
  const status = i % 9 === 4 ? "unavailable" : i % 6 === 2 ? "stale" : i % 5 === 3 ? "delayed" : "fresh";
  const base = {
    location_id: slug(name),
    name,
    data_status: status,
    last_successful_refresh_at: status === "unavailable" ? null : MARKET_REFRESH,
  } as const;
  if (status === "unavailable")
    return {
      ...base,
      latest_summary_date: null,
      median_rent_pln: null,
      median_ppm2: null,
      priced_count: null,
      sufficient: null,
      withheld_reason: null,
    };
  const sufficient = i % 7 !== 5;
  return {
    ...base,
    latest_summary_date: MARKET_DAY,
    median_rent_pln: sufficient ? `${1800 + ((i * 37) % 2200)}.00` : null,
    median_ppm2: sufficient ? `${40 + ((i * 13) % 30)}.50` : null,
    priced_count: sufficient ? 12 + ((i * 17) % 300) : 3 + (i % 7),
    sufficient,
    withheld_reason: sufficient ? null : "insufficient_sample",
  };
}

function marketPlaces(count: number): LocationSummary[] {
  const names = Array.from(
    { length: count },
    (_, i) => CITY_NAMES[i] ?? `Miejscowość ${String(i).padStart(3, "0")}`,
  );
  return names.sort((a, b) => a.localeCompare(b, "pl")).map(marketPlace);
}

function marketReading(
  place: LocationSummary,
  cohort: string,
  series: "cohort" | "additions",
  offset: number,
): AskingRent {
  const sufficient = place.sufficient === true;
  const factor = COHORT_FACTOR[cohort] ?? 1;
  const drift = (offset % 9) * 10;
  const rent = Number(place.median_rent_pln ?? "2000") * factor + drift;
  const ppm2 = Number(place.median_ppm2 ?? "40.50") * (factor > 1 ? 1.05 : 1) + (offset % 9) / 10;
  const day = new Date(Date.parse(`${MARKET_DAY}T00:00:00Z`) - offset * 86_400_000)
    .toISOString()
    .slice(0, 10);
  const priced = Math.max(
    3,
    Math.round((place.priced_count ?? 10) / (cohort === "all" ? 1 : 3) / (series === "additions" ? 6 : 1)),
  );
  const enough = sufficient && priced >= 10;
  return {
    price_basis: "asking",
    measure: "original_asking_rent",
    source: "otodom",
    archive_days: 90,
    caveats: MARKET_CAVEATS,
    summary_date: day,
    series,
    cohort_key: cohort,
    as_of: `${day}T05:30:00Z`,
    observed_count: priced + 2,
    priced_count: priced,
    first_observed_count: series === "additions" ? (priced % 5) + 1 : null,
    median_rent_pln: enough ? rent.toFixed(2) : null,
    median_ppm2: enough ? ppm2.toFixed(2) : null,
    p25_ppm2: enough ? (ppm2 - 3).toFixed(2) : null,
    p75_ppm2: enough ? (ppm2 + 3).toFixed(2) : null,
    sufficient: enough,
    withheld_reason: enough ? null : "insufficient_sample",
    backfilled: offset % 10 === 3,
  };
}

/**
 * The catalogue and its published asking-rent readings, with the server's semantics: a case-insensitive name
 * search, `limit`, an opaque cursor that ends with `null`, a detail that lists the cohorts published for the place
 * and a history of `days` daily readings with gap days left out (never zero). Places differ in freshness and
 * sample size so every state of the page can be reached from one scenario.
 */
export function createMarket(options: MarketOptions = {}): Market {
  const places = options.empty === true ? [] : marketPlaces(options.count ?? 38);
  const state = { requests: [] as string[], failing: options.failPage !== undefined };
  const problem = (status: number, extra: Record<string, string> = {}): Reply => ({
    status,
    body: NOT_READY,
    contentType: "application/problem+json",
    headers: extra,
  });
  const list: Route = {
    operation: "GET /api/market/locations",
    reply: (request) => {
      const q = request.url.searchParams;
      state.requests.push(request.url.search);
      const cursor = q.get("cursor");
      if (options.listFails === true || (cursor !== null && state.failing)) return problem(503);
      const needle = (q.get("q") ?? "").toLowerCase();
      const matching = places.filter((p) => p.name.toLowerCase().includes(needle));
      const limit = Math.min(Number(q.get("limit") ?? "50"), 100);
      const start = cursor === null ? 0 : Number(atob(cursor).replace("cursor:", ""));
      if (!Number.isInteger(start) || start < 0)
        return replyFrom(fx("GET /api/market/locations", "bad_cursor"));
      const items = matching.slice(start, start + limit);
      return {
        status: 200,
        body: {
          items,
          next_cursor: start + limit < matching.length ? btoa(`cursor:${start + limit}`) : null,
        },
      };
    },
  };
  const detail: Route = {
    operation: "GET /api/market/locations/{location_id}",
    reply: (request) => {
      state.requests.push(request.url.pathname);
      if (options.detailFails === true) return problem(503);
      const place = places.find((p) => p.location_id === request.params["location_id"]);
      if (place === undefined)
        return replyFrom(fx("GET /api/market/locations/{location_id}", "unknown_place"));
      if (options.free === true && !places.slice(0, FREE_VISIBLE).includes(place))
        return replyFrom(fx("GET /api/market/locations/{location_id}", "outside_free_list"));
      const usable = place.data_status !== "unavailable";
      return {
        status: 200,
        body: {
          location_id: place.location_id,
          name: place.name,
          data_status: place.data_status,
          last_successful_refresh_at: place.last_successful_refresh_at,
          covered_until: usable ? "2026-10-17T21:00:00Z" : null,
          unresolved_gap_since: place.data_status === "stale" ? "2026-10-14T03:00:00Z" : null,
          usable_for_ranking: place.data_status === "fresh" && place.sufficient === true,
          cohort: usable ? Object.keys(COHORT_FACTOR).map((k) => marketReading(place, k, "cohort", 0)) : [],
        } satisfies LocationDetail,
      };
    },
  };
  const history: Route = {
    operation: "GET /api/market/locations/{location_id}/history",
    reply: (request) => {
      state.requests.push(`${request.url.pathname}${request.url.search}`);
      if (options.historyFails === true) return problem(503);
      if (options.historyFails === "rate-limited")
        return {
          status: 429,
          body: { ...NOT_READY, status: 429, code: "RATE_LIMITED", title: "Too many requests" },
          contentType: "application/problem+json",
          headers: { "retry-after": "7" },
        };
      const place = places.find((p) => p.location_id === request.params["location_id"]);
      if (place === undefined)
        return replyFrom(fx("GET /api/market/locations/{location_id}/history", "unknown_place"));
      const q = request.url.searchParams;
      const days = Number(q.get("days") ?? "90");
      const series = q.get("series") === "additions" ? "additions" : "cohort";
      const cohort = q.get("cohort") ?? "all";
      const points =
        options.historyEmpty === true
          ? []
          : Array.from({ length: days }, (_, offset) => days - 1 - offset)
              .filter((offset) => offset % 11 !== 5) // days without a published reading are absent
              .map((offset) => marketReading(place, cohort, series, offset));
      return {
        status: 200,
        body: {
          location_id: place.location_id,
          series,
          cohort_key: cohort,
          start: points[0]?.summary_date ?? MARKET_DAY,
          end: MARKET_DAY,
          points,
        },
        ...(options.historyDelayMs === undefined ? {} : { delayMs: options.historyDelayMs }),
      };
    },
  };
  const visible = options.free === true ? places.slice(0, FREE_VISIBLE) : places;
  const closed = (id: string) => !visible.some((p) => p.location_id === id);
  const mappingOf = (i: number) => (i % 11 === 10 ? "unmatched" : i % 7 === 6 ? "ambiguous" : "mapped");
  const scaled = (p: LocationSummary, cohort: string): LocationSummary => {
    if (cohort === "all" || p.data_status === "unavailable") return p;
    const factor = COHORT_FACTOR[cohort] ?? 1;
    const priced = Math.max(2, Math.round((p.priced_count ?? 0) / 3));
    const enough = p.sufficient === true && priced >= 10;
    return {
      ...p,
      priced_count: priced,
      sufficient: enough,
      withheld_reason: enough ? null : "insufficient_sample",
      median_rent_pln: enough ? (Number(p.median_rent_pln ?? "2000") * factor).toFixed(2) : null,
      median_ppm2: enough ? (Number(p.median_ppm2 ?? "40") * factor).toFixed(2) : null,
    };
  };
  const overview: Route = {
    operation: "GET /api/market/overview",
    reply: (request) => {
      if (options.overviewFails === true) return problem(503);
      const cohort = request.url.searchParams.get("cohort") ?? "all";
      state.requests.push(`/api/market/overview${request.url.search}`);
      if (!(cohort in COHORT_FACTOR)) return replyFrom(fx("GET /api/market/overview", "bad_cohort"));
      const items: OverviewPlaceOut[] = visible.map((p) => {
        const i = places.indexOf(p);
        const mapping = mappingOf(i);
        return {
          ...scaled(p, cohort),
          mapping,
          relation: mapping === "mapped" ? (i % 5 === 4 ? "within_gmina" : "gmina") : null,
          gmina_teryt: mapping === "mapped" ? (MARKET_TERYT[i % MARKET_TERYT.length] ?? null) : null,
          powiat_name: mapping === "unmatched" ? null : "Powiat testowy",
          wojewodztwo_name: mapping === "unmatched" ? null : "Województwo testowe",
        };
      });
      return {
        status: 200,
        body: {
          items,
          total_places: places.length,
          visible_places: items.length,
          access: options.free === true ? "free" : "full",
          free_limit: FREE_VISIBLE,
          free_rule_pl: "Darmowe konto widzi 20 miejsc z największą liczbą opublikowanych ofert z ceną.",
          cohort_key: cohort,
        } satisfies OverviewOut,
      };
    },
  };
  const DISTRICT_NAMES = ["Centrum", "Północ", "Południe", "Rubinkowo"];
  const districts: Route = {
    operation: "GET /api/market/locations/{location_id}/districts",
    reply: (request) => {
      state.requests.push(`${request.url.pathname}${request.url.search}`);
      if (options.districtsFail === true) return problem(503);
      const id = String(request.params["location_id"]);
      const place = places.find((p) => p.location_id === id);
      if (place === undefined)
        return replyFrom(fx("GET /api/market/locations/{location_id}/districts", "unknown_place"));
      if (closed(id))
        return replyFrom(fx("GET /api/market/locations/{location_id}/districts", "outside_free_list"));
      const cohort = request.url.searchParams.get("cohort") ?? "all";
      const i = places.indexOf(place);
      const supported = options.noDistricts !== true && place.data_status !== "unavailable" && i % 3 === 0;
      const factor = COHORT_FACTOR[cohort] ?? 1;
      const rows = supported
        ? DISTRICT_NAMES.map((name, k) => {
            const priced =
              k === 3
                ? 4
                : Math.max(0, Math.round((place.priced_count ?? 30) / (k + 2) / (cohort === "all" ? 1 : 3)));
            const enough = priced >= 10;
            const ppm2 = (Number(place.median_ppm2 ?? "40") * factor * (1 + k / 20)).toFixed(2);
            return {
              district_id: `cala-polska/${id}/${slug(name)}`,
              name,
              observed_count: priced + 1,
              priced_count: priced,
              median_rent_pln: enough ? (Number(ppm2) * 48).toFixed(2) : null,
              median_ppm2: enough ? ppm2 : null,
              p25_ppm2: enough ? (Number(ppm2) - 3).toFixed(2) : null,
              p75_ppm2: enough ? (Number(ppm2) + 3).toFixed(2) : null,
              sufficient: enough,
              withheld_reason: enough ? null : ("insufficient_sample" as const),
            };
          })
        : [];
      return {
        status: 200,
        body: {
          price_basis: "asking",
          source: "otodom",
          location_id: id,
          name: place.name,
          data_status: place.data_status,
          coverage: supported ? "supported" : "none",
          cohort_key: cohort,
          as_of: `${MARKET_DAY}T05:30:00Z`,
          offers_in_cohort: supported ? rows.reduce((n, r) => n + r.priced_count, 0) + 3 : 0,
          offers_with_district: supported ? rows.reduce((n, r) => n + r.priced_count, 0) : 0,
          districts: rows,
          caveats: MARKET_CAVEATS,
        } satisfies components["schemas"]["LocationDistrictsOut"],
      };
    },
  };
  const COMPONENTS = [
    ["net_migration_per_1000", "net_migration", "demography", "Demografia", "Saldo migracji na pobyt stały na 1000 mieszkańców", "osób na 1000 mieszkańców", 20, "higher"],
    ["natural_increase_per_1000", "natural_increase", "demography", "Demografia", "Przyrost naturalny na 1000 mieszkańców", "osób na 1000 mieszkańców", 10, "higher"],
    ["unemployment_share", "unemployment_share_working_age", "labour", "Rynek pracy i dochody", "Udział zarejestrowanych bezrobotnych w ludności w wieku produkcyjnym", "%", 15, "lower"],
    ["earnings", "average_monthly_gross_earnings", "labour", "Rynek pracy i dochody", "Przeciętne miesięczne wynagrodzenie brutto", "zł", 15, "higher"],
    ["business_density", "regon_entities_per_10k", "business", "Przedsiębiorczość", "Podmioty gospodarcze (REGON) na 10 tys. mieszkańców", "podmiotów na 10 tys. mieszkańców", 20, "higher"],
    ["own_revenue", "own_revenue_per_resident", "fiscal", "Dochody własne gminy", "Dochody własne gminy na mieszkańca", "zł na mieszkańca", 20, "higher"],
  ] as const; // prettier-ignore
  const indexOf = (i: number): components["schemas"]["IndexOut"] => {
    const state = i % 7 === 3 ? "not_scored" : i % 11 === 6 ? "scored_not_ranked" : "ok";
    const scoreValue = 82 - (i % 37) * 1.7;
    const have = state !== "not_scored";
    const comps = COMPONENTS.map(([key, metric, pillar, pillarPl, name, unit, weight, dir], k) => {
      const missing = state === "not_scored" && k === 4;
      const score = Math.max(4, 90 - ((i * 7 + k * 13) % 80));
      return {
        key,
        metric_key: metric,
        pillar,
        pillar_pl: pillarPl,
        name_pl: name,
        explain_pl: "Opis wskaźnika w tym teście.",
        unit_pl: unit,
        weight,
        value: missing ? null : (12 + k * 3.25 + i / 10).toFixed(2),
        year: missing ? null : 2024 + (k % 2),
        basis: missing ? null : k === 3 ? ("proxy" as const) : ("direct" as const),
        measured: missing
          ? null
          : {
              territory_id: `t${k}`,
              name: k === 3 ? "Powiat testowy" : "Gmina testowa",
              level: k === 3 ? ("powiat" as const) : ("gmina" as const),
              teryt: "",
            },
        national_rank: missing ? null : 100 + i + k * 9,
        national_of: missing ? null : 2479,
        score: missing ? null : score.toFixed(2),
        points: missing || !have ? null : ((weight / 100) * score).toFixed(2),
        favourable_pl: dir === "lower" ? "Niższa wartość = korzystniej" : "Wyższa wartość = korzystniej",
      };
    });
    return {
      state,
      reasons:
        state === "not_scored"
          ? ["brak danych w obszarze „Przedsiębiorczość”"]
          : state === "scored_not_ranked"
            ? ["kohorta mniejsza niż 50 gmin: brak pozycji"]
            : [],
      method_version: 1,
      title_pl: "Eksperymentalny indeks warunków lokalnych",
      caveat_pl:
        "To eksperymentalne podsumowanie oficjalnych wskaźników GUS: porównuje gminę z innymi gminami w Polsce. Nie jest wyceną nieruchomości, prognozą czynszów ani cen i nie wchodzi do żadnego wyniku finansowego.",
      higher_is_better: true,
      score: state === "not_scored" ? null : scoreValue.toFixed(2),
      weight_coverage: state === "not_scored" ? "0.80" : "1.00",
      positions:
        state === "ok"
          ? [
              {
                name_pl: "gminy w Polsce z kompletnym indeksem",
                scope: "national" as const,
                rank: 120 + i,
                of: 2479,
                percentile: "95.20",
                unit_name: null,
              },
              {
                name_pl: "gminy z kompletnym indeksem w tym samym województwie",
                scope: "voivodeship" as const,
                rank: 3 + (i % 5),
                of: 160,
                percentile: null,
                unit_name: "Województwo testowe",
              },
            ]
          : [],
      components: comps,
      missing: state === "not_scored" ? ["Podmioty gospodarcze (REGON) na 10 tys. mieszkańców"] : [],
      gmina: {
        territory_id: `g${i}`,
        name: `Gmina ${places[i]?.name ?? ""}`,
        level: "gmina" as const,
        teryt: MARKET_TERYT[i % MARKET_TERYT.length] ?? "",
      },
      oldest_year: 2024,
      newest_year: 2025,
      min_weight_coverage: "0.80",
      min_cohort: 50,
    };
  };
  const ranking: Route = {
    operation: "GET /api/market/locations/{location_id}/ranking",
    reply: (request) => {
      state.requests.push(request.url.pathname);
      if (options.rankingFails === true) return problem(503);
      const id = String(request.params["location_id"]);
      const place = places.find((p) => p.location_id === id);
      if (place === undefined)
        return replyFrom(fx("GET /api/market/locations/{location_id}/ranking", "unknown_place"));
      if (closed(id))
        return replyFrom(fx("GET /api/market/locations/{location_id}/ranking", "outside_free_list"));
      const i = places.indexOf(place);
      const mapping = mappingOf(i);
      const index =
        mapping === "mapped"
          ? indexOf(i)
          : {
              ...indexOf(i),
              state: "unavailable" as const,
              reasons: ["Tego miejsca nie udało się jednoznacznie przypisać do gminy GUS."],
              score: null,
              positions: [],
              components: [],
              missing: [],
              gmina: null,
              weight_coverage: null,
              oldest_year: null,
              newest_year: null,
            };
      return {
        status: 200,
        body: {
          location_id: id,
          name: place.name,
          mapping: {
            status: mapping,
            relation: mapping === "mapped" ? (i % 5 === 4 ? "within_gmina" : "gmina") : null,
            method: "name_in_powiat",
            candidates: [],
          },
          index,
          source: {
            name: "GUS BDL",
            url: "https://example.test/fixture/1",
            attribution_pl: "Źródło: GUS, Bank Danych Lokalnych (BDL); obliczenia własne.",
            note_pl: "Dane roczne.",
          },
        } satisfies components["schemas"]["LocationIndexOut"],
      };
    },
  };
  const rankingOverview: Route = {
    operation: "GET /api/market/ranking",
    reply: () => {
      if (options.rankingFails === true) return problem(503);
      const items = visible
        .map((p) => {
          const i = places.indexOf(p);
          const mapped = mappingOf(i) === "mapped";
          const idx = indexOf(i);
          return {
            location_id: p.location_id,
            name: p.name,
            gmina_name: mapped ? `Gmina ${p.name}` : null,
            state: mapped ? idx.state : ("unavailable" as const),
            score: mapped ? idx.score : null,
            rank: mapped && idx.state === "ok" ? 120 + i : null,
            of: mapped && idx.state === "ok" ? 2479 : null,
            relation: mapped ? (i % 5 === 4 ? ("within_gmina" as const) : ("gmina" as const)) : null,
          };
        })
        .sort(
          (a, b) =>
            (a.rank === null ? 1 : 0) - (b.rank === null ? 1 : 0) ||
            (a.rank ?? 0) - (b.rank ?? 0) ||
            a.name.localeCompare(b.name, "pl"),
        );
      return {
        status: 200,
        body: {
          method_version: 1,
          title_pl: "Eksperymentalny indeks warunków lokalnych",
          caveat_pl: "To eksperymentalne podsumowanie oficjalnych wskaźników GUS.",
          cohort_name_pl: "gminy w Polsce z kompletnym indeksem",
          scored_gminas: 2400,
          total_places: places.length,
          visible_places: items.length,
          access: options.free === true ? "free" : "full",
          items,
          source: {
            name: "GUS BDL",
            url: "https://example.test/fixture/1",
            attribution_pl: "Źródło: GUS, Bank Danych Lokalnych (BDL); obliczenia własne.",
            note_pl: "Dane roczne.",
          },
        } satisfies components["schemas"]["RankingOverviewOut"],
      };
    },
  };
  const context: Route = {
    operation: "GET /api/market/locations/{location_id}/context",
    reply: (request) => {
      state.requests.push(request.url.pathname);
      if (options.contextFails === true) return problem(503);
      const id = String(request.params["location_id"]);
      const place = places.find((p) => p.location_id === id);
      if (place === undefined)
        return replyFrom(fx("GET /api/market/locations/{location_id}/context", "unknown_place"));
      if (closed(id))
        return replyFrom(fx("GET /api/market/locations/{location_id}/context", "outside_free_list"));
      const i = places.indexOf(place);
      const mapping = mappingOf(i);
      const territory = (name: string, level: "gmina" | "powiat" | "wojewodztwo" | "country") => ({
        territory_id: `${level}-${i}`,
        name,
        level,
        teryt: "",
      });
      const series = Array.from({ length: 10 }, (_, k) => ({
        year: 2016 + k,
        value: String(20_000 + i * 100 + k * 150),
        status: "measured",
      }));
      const metric = (
        key: string,
        name: string,
        state: "direct" | "proxy",
        unit: string,
        family: string,
      ) => ({
        key,
        name_pl: name,
        family,
        family_pl:
          family === "population" ? "Ludność i wiek" : "Transakcje na rynku lokali (akty notarialne)",
        unit,
        note_pl: "",
        direction: "neutral" as const,
        state,
        reason: null,
        measured: territory(
          state === "direct" ? place.name : "Powiat testowy",
          state === "direct" ? "gmina" : "powiat",
        ),
        year: 2025,
        value: series.at(-1)?.value ?? null,
        value_status: "measured",
        series,
        trend: {
          state: "ok" as const,
          movement: "up" as const,
          favorable: null,
          from_year: 2016,
          to_year: 2025,
          absolute_change: "1350",
          percent_change: "6.7",
          comparable_steps: 9,
          reasons: [],
        },
        parents: [
          { territory: territory("Powiat testowy", "powiat"), value: "180000", relation: "below" as const },
        ],
        national: {
          scope: "kraj",
          scope_level: "gmina" as const,
          state: "ok" as const,
          rank: 120,
          of: 2479,
          percentile: "0.95",
          median: "9000",
          coverage: "1",
          reasons: [],
        },
        peers: {
          scope: "ten sam powiat",
          scope_level: "gmina" as const,
          state: "suppressed" as const,
          rank: null,
          of: null,
          percentile: null,
          median: null,
          coverage: null,
          reasons: ["za mało"],
        },
        release_id: "release-test",
      });
      const body: LocationContextOut = {
        location_id: id,
        name: place.name,
        mapping: {
          status: mapping,
          relation: mapping === "mapped" ? (i % 5 === 4 ? "within_gmina" : "gmina") : null,
          method: "name_in_powiat",
          candidates:
            mapping === "ambiguous" ? [territory("Gmina A", "gmina"), territory("Gmina B", "gmina")] : [],
        },
        chain:
          mapping === "unmatched"
            ? []
            : [
                territory(place.name, "gmina"),
                territory("Powiat testowy", "powiat"),
                territory("Polska", "country"),
              ],
        metrics:
          mapping === "unmatched"
            ? []
            : [
                metric("population_total", "Ludność ogółem", "direct", "osób", "population"),
                metric(
                  "dwelling_median_price_m2",
                  "Mediana cen za 1 m² lokali mieszkalnych",
                  "proxy",
                  "zł/m²",
                  "market",
                ),
              ],
        published_metrics: mapping === "unmatched" ? 0 : 2,
        source: {
          name: "GUS BDL",
          url: "https://example.test/fixture/1",
          attribution_pl: "Źródło: Główny Urząd Statystyczny, Bank Danych Lokalnych (BDL).",
          note_pl: "Dane roczne.",
        },
      };
      return { status: 200, body };
    },
  };
  const base = scenario("market", `A catalogue of ${places.length} places with asking-rent readings.`, [
    ...(options.unlimited === true
      ? [withMe((m) => ({ ...m, credit_balance: 0, plan: { ...m.plan, unlimited_reports: true } }))]
      : []),
    list,
    detail,
    history,
    overview,
    districts,
    ranking,
    rankingOverview,
    context,
  ]);
  return { ...base, state, places };
}

const RICH_URL = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd";

// -------------------------------------------------------------------------------------------------- saved
type SavedOut = components["schemas"]["SavedOut"];

export interface SavedFlow extends Scenario {
  /** What the server holds, by Otodom id; tests read it to prove what was stored. */
  readonly saved: Map<string, SavedOut>;
  readonly calls: string[];
}

/**
 * The analyses collection with a working saved list: PUT keeps the stored note when the body has no note key and clears it for an explicit null (as the
 * API does), DELETE is idempotent, a listing that was never analysed is a 404. Fresh state per call.
 */
export function createSaved(
  seed: readonly (readonly [index: number, note: string | null])[] = [
    [0, "Notatka testowa"],
    [1, null],
  ],
  overrides: Record<string, Reply> = {},
  audits: readonly AuditOut[] = SUCCEEDED_AUDITS,
): SavedFlow {
  const saved = new Map<string, SavedOut>();
  const calls: string[] = [];
  const latest = (otodomId: string) => audits.find((a) => a.otodom_id === otodomId);
  seed.forEach(([index, note], n) => {
    const audit = audits[index];
    if (audit === undefined) throw new Error(`no audit ${index}`);
    saved.set(audit.otodom_id, {
      otodom_id: audit.otodom_id,
      note,
      latest_audit_id: audit.audit_id,
      created_at: new Date(Date.parse("2026-10-02T10:00:00Z") - n * 3_600_000)
        .toISOString()
        .replace(".000Z", "Z"),
    });
  });
  const routes: Route[] = [
    {
      operation: "GET /api/saved",
      reply: (request) => {
        calls.push("list");
        calls.push(`list${request.url.search}`);
        return (
          overrides["GET /api/saved"] ?? {
            status: 200,
            body: [...saved.values()].sort((a, b) => b.created_at.localeCompare(a.created_at)),
          }
        );
      },
    },
    {
      operation: "PUT /api/saved/{otodom_id}",
      reply: (request) => {
        const id = request.params["otodom_id"] ?? "";
        const body = (request.body ?? {}) as { note?: string | null };
        const hasNote = "note" in body; // an absent key keeps the stored note, null clears it (RM-347)
        calls.push(`put:${id}:${hasNote ? (body.note ?? "null") : ""}`);
        const forced = overrides["PUT /api/saved/{otodom_id}"];
        if (forced !== undefined) return forced;
        const audit = latest(id);
        if (audit === undefined) return replyFrom(fx("PUT /api/saved/{otodom_id}", "never_audited"));
        const row: SavedOut = {
          otodom_id: id,
          note: hasNote ? (body.note ?? null) : (saved.get(id)?.note ?? null),
          latest_audit_id: audit.audit_id,
          created_at: saved.get(id)?.created_at ?? "2026-10-02T12:00:00Z",
        };
        saved.set(id, row);
        return { status: 200, body: row };
      },
    },
    {
      operation: "DELETE /api/saved/{otodom_id}",
      reply: (request) => {
        const id = request.params["otodom_id"] ?? "";
        calls.push(`delete:${id}`);
        const forced = overrides["DELETE /api/saved/{otodom_id}"];
        if (forced !== undefined) return forced;
        saved.delete(id);
        return { status: 204 };
      },
    },
    ...auditRoutes(audits),
  ];
  const base = scenario(
    "saved",
    "Five analyses and a working saved list: two saved, one with a note.",
    routes,
  );
  return { ...base, saved, calls };
}

// ------------------------------------------------------------------------------------------------ billing
type PurchaseOut = components["schemas"]["PurchaseOut"];
type PackOut = components["schemas"]["PackOut"];

export interface BillingFlow extends Scenario {
  /** What the server holds, by purchase id. */
  readonly purchases: Map<string, PurchaseOut>;
  /** Requests by kind, in order: `checkout:<key>:<pack>`, `lookup:<key>`, `poll:<id>`, `invoice:<id>`, `list`. */
  readonly calls: string[];
}

export interface BillingOptions {
  /** Purchases the account already has, newest first. */
  readonly existing?: readonly PurchaseOut[];
  /** How many reads of a purchase show it unsettled before the final state (default 2: created, then paid). */
  readonly settleAfter?: number;
  /** What the purchase becomes (default `granted`). */
  readonly finalState?: "granted" | "failed" | "review" | "refunded";
  /** `enabled: false` makes the shop unavailable. */
  readonly enabled?: boolean;
  readonly verified?: boolean;
  /** Replace the answer to an operation (a failing checkout, an invoice error). */
  readonly overrides?: Record<string, Reply>;
}

const FIXTURE_PACKS = bodyOf<{ packs: PackOut[] }>(fx("GET /api/billing/packs", "three_packs")).packs;

/**
 * A working shop against a fake provider: the pack list, a checkout that is idempotent by `Idempotency-Key` (the same
 * key returns the same purchase and never a second one), purchases that settle after some reads, an invoice link, and
 * a balance that rises only when the server says `granted`. Fresh state per call.
 */
export function createBilling(options: BillingOptions = {}): BillingFlow {
  const { settleAfter = 2, finalState = "granted", enabled = true, verified = true } = options;
  const overrides = options.overrides ?? {};
  const purchases = new Map<string, PurchaseOut>((options.existing ?? []).map((p) => [p.purchase_id, p]));
  const byKey = new Map<string, string>();
  const reads = new Map<string, number>();
  const calls: string[] = [];
  let counter = 0;
  const baseBalance = bodyOf<MeDetail>(fx("GET /api/me", "with_credits_and_flags")).credit_balance;
  const balance = () =>
    baseBalance +
    [...purchases.values()]
      .filter((p) => p.state === "granted" && !(options.existing ?? []).includes(p))
      .reduce((sum, p) => sum + p.reports, 0);

  const routes: Route[] = [
    {
      operation: "GET /api/me",
      reply: () => {
        const body = bodyOf<MeDetail>(fx("GET /api/me", "with_credits_and_flags"));
        return { status: 200, body: { ...body, credit_balance: balance(), email_verified: verified } };
      },
    },
    {
      operation: "GET /api/billing/packs",
      reply: () =>
        overrides["GET /api/billing/packs"] ?? {
          status: 200,
          body: { enabled, packs: enabled ? FIXTURE_PACKS : [] },
        },
    },
    {
      operation: "GET /api/billing/purchases",
      reply: (request) => {
        const wanted = request.url.searchParams.get("request_key");
        if (wanted !== null) {
          calls.push(`lookup:${wanted}`); // only the purchase created with that key, or none
          const id = byKey.get(wanted);
          const found = id === undefined ? undefined : purchases.get(id);
          return (
            overrides["GET /api/billing/purchases?request_key"] ?? {
              status: 200,
              body: { purchases: found === undefined ? [] : [found] },
            }
          );
        }
        calls.push("list");
        return (
          overrides["GET /api/billing/purchases"] ?? {
            status: 200,
            body: { purchases: [...purchases.values()] },
          }
        );
      },
    },
    {
      operation: "POST /api/billing/checkout",
      reply: (request) => {
        const key = request.headers["idempotency-key"] ?? "";
        const code = (request.body as { pack_code?: string } | null)?.pack_code ?? "";
        calls.push(`checkout:${key}:${code}`);
        const forced = overrides["POST /api/billing/checkout"];
        if (forced !== undefined) return forced;
        const replay = byKey.get(key);
        const known = replay === undefined ? undefined : purchases.get(replay);
        if (known !== undefined) return { status: 200, body: known };
        const pack = FIXTURE_PACKS.find((p) => p.code === code);
        if (pack === undefined) return replyFrom(fx("POST /api/billing/checkout", "unknown_pack"));
        counter += 1;
        const id = `00000000-0000-4000-8000-${String(900 + counter).padStart(12, "0")}`;
        const purchase: PurchaseOut = {
          purchase_id: id,
          pack_code: pack.code,
          reports: pack.reports,
          gross_pln: pack.gross_pln,
          currency: "PLN",
          state: "created",
          transaction_id: `txn_fixture${String(counter).padStart(4, "0")}`,
          checkout_url: `/pay?_ptxn=txn_fixture${String(counter).padStart(4, "0")}`,
          created_at: "2026-10-02T10:00:00Z",
          granted_at: null,
          refunded_at: null,
        };
        purchases.set(id, purchase);
        byKey.set(key, id);
        return { status: 200, body: purchase };
      },
    },
    {
      operation: "GET /api/billing/purchases/{purchase_id}",
      reply: (request) => {
        const id = request.params["purchase_id"] ?? "";
        calls.push(`poll:${id}`);
        const forced = overrides["GET /api/billing/purchases/{purchase_id}"];
        if (forced !== undefined) return forced;
        const found = purchases.get(id);
        if (found === undefined)
          return replyFrom(fx("GET /api/billing/purchases/{purchase_id}", "foreign_purchase"));
        const n = (reads.get(id) ?? 0) + 1;
        reads.set(id, n);
        if ((options.existing ?? []).includes(found)) return { status: 200, body: found };
        const state: PurchaseOut["state"] =
          n < settleAfter ? "created" : n === settleAfter ? "paid" : finalState;
        const next: PurchaseOut = {
          ...found,
          state,
          granted_at: state === "granted" ? "2026-10-02T10:05:00Z" : null,
          refunded_at: state === "refunded" ? "2026-10-02T10:06:00Z" : null,
        };
        purchases.set(id, next);
        return { status: 200, body: next };
      },
    },
    {
      operation: "GET /api/billing/purchases/{purchase_id}/invoice",
      reply: (request) => {
        const id = request.params["purchase_id"] ?? "";
        calls.push(`invoice:${id}`);
        return (
          overrides["GET /api/billing/purchases/{purchase_id}/invoice"] ?? {
            status: 200,
            body: { url: "https://invoice.example.test/document.pdf" },
          }
        );
      },
    },
  ];
  const base = scenario("billing", "A working shop against a fake provider.", routes);
  return { ...base, purchases, calls };
}

function historyPurchase(n: number, patch: Partial<PurchaseOut>): PurchaseOut {
  const pack = FIXTURE_PACKS[n % FIXTURE_PACKS.length] as PackOut;
  return {
    purchase_id: `00000000-0000-4000-8000-${String(500 + n).padStart(12, "0")}`,
    pack_code: pack.code,
    reports: pack.reports,
    gross_pln: pack.gross_pln,
    currency: "PLN",
    state: "granted",
    transaction_id: `txn_history${String(n).padStart(4, "0")}`,
    checkout_url: null,
    created_at: new Date(Date.parse("2026-10-01T10:00:00Z") - n * 86_400_000)
      .toISOString()
      .replace(".000Z", "Z"),
    granted_at: "2026-10-01T10:05:00Z",
    refunded_at: null,
    ...patch,
  };
}

/** Six purchases in six different states, newest first: what an account with a history looks like. */
export const SHOP_HISTORY: readonly PurchaseOut[] = [
  historyPurchase(0, { state: "granted" }),
  historyPurchase(1, { state: "created", granted_at: null }),
  historyPurchase(2, { state: "refunded", refunded_at: "2026-09-29T10:00:00Z" }),
  historyPurchase(3, { state: "review", granted_at: null }),
  historyPurchase(4, { state: "creation_unknown", granted_at: null, transaction_id: null }),
  historyPurchase(5, { state: "failed", granted_at: null }),
];

// ------------------------------------------------------------------------------------------------ settings
/** The account's own email in the `with_credits_and_flags` profile: what a deletion must be confirmed with. */
export const SETTINGS_EMAIL = "user-18@example.test";

/** Signed in; the settings routes answer from the fixtures. `routes` replace a default by repeating its operation. */
export function createSettings(
  routes: readonly Route[] = [],
  name = "settings",
  hasPassword = true,
): Scenario {
  return scenario(name, "Signed in on the settings page: three browsers, export, password, deletion.", [
    ...routes,
    // The account's password flag comes from the API; a scenario sets it, a route may still replace the whole answer.
    ...(routes.some((r) => r.operation === "GET /api/me")
      ? []
      : [withMe((body) => ({ ...body, has_password: hasPassword }))]),
    ...(
      [
        ["GET /api/auth/sessions", "three_sessions"],
        ["GET /api/me/export", "export"],
        ["POST /api/auth/signout-all", "signed_out_everywhere"],
        ["POST /api/auth/password/change", "changed"],
        ["DELETE /api/me", "erased"],
      ] as const
    )
      .filter(([operation]) => !routes.some((r) => r.operation === operation))
      .map(([operation, fixture]) => fromFixture(operation, fixture)),
  ]);
}

// ------------------------------------------------------------------------------------------ interior (RM-451)
type ProjectOut = components["schemas"]["ProjectOut"];
type OfferOut = components["schemas"]["OfferOut"];
type GenerationOut = components["schemas"]["GenerationOut"];
type SelectionOut = components["schemas"]["SelectionOut"];
type RevisionOut = components["schemas"]["RevisionOut"];
type CandidateOut = components["schemas"]["CandidateOut"];
type MediaRefOut = components["schemas"]["MediaRef"];

export interface InteriorOptions {
  /** The person is outside the closed beta: every interior route answers 403. */
  readonly closed?: boolean;
  /** No product source is connected: the catalogue answers 503 and the status says so. */
  readonly noCatalogue?: boolean;
  /** The image store is down: a photo upload answers 503 and the project is kept. */
  readonly storageDown?: boolean;
  /** Generation is switched off: the create route answers 503. */
  readonly generationOff?: boolean;
  /** A generation ends `failed` with this stable code instead of succeeding. */
  readonly failWith?: GenerationOut["error_code"];
  /** Start with one saved project that has a room photo (default true). */
  readonly seeded?: boolean;
  /** The seeded project also has an own item without a price, a picked product and one saved version. */
  readonly rich?: boolean;
  /** A generation stays queued (it is never picked up), so the cancel path can be looked at. */
  readonly hold?: boolean;
}

export interface InteriorFlow extends Scenario {
  readonly calls: string[];
  /** What the server holds, so a test can prove what was stored or that nothing was sent twice. */
  readonly projects: Map<string, ProjectOut>;
  readonly generations: Map<string, GenerationOut[]>;
  /** Make a picked variant stale or unavailable, as the source would after a day or a stock-out. */
  setOfferState(variantId: string, state: OfferOut["state"]): void;
}

const IID = (n: number) => `00000000-0000-4000-8000-${String(900 + n).padStart(12, "0")}`;
const SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240"><rect width="320" height="240" fill="#c8b9a6"/></svg>';

/** Whole grosze from a decimal string. Test-side bookkeeping for the fake server only; the app never does this. */
const grosze = (text: string): number => Number.parseInt(text.replace(".", ""), 10);
const decimal = (n: number): string => `${String(Math.floor(n / 100))}.${String(n % 100).padStart(2, "0")}`;

function interiorOffers(): OfferOut[] {
  const base = bodyOf<CandidateOut[]>(
    fx("GET /api/interior/projects/{project_id}/catalogue/search", "sofas"),
  )[0]?.offer;
  if (base === undefined) throw new Error("no sofa offer fixture");
  const make = (product: string, variant: string, title: string, over: Partial<OfferOut>): OfferOut => ({
    ...base,
    product_id: product,
    variant_id: variant,
    title,
    offer_id: `${product}-${variant}`,
    product_url: `https://demo.invalid/${product}?wariant=${variant}`,
    image_url: `/api/interior/catalogue/demo-image/${product}/${variant}`,
    ...over,
  });
  return [
    make("sofa-nordic", "grey", "Sofa Nordic 3-osobowa", {}),
    make("sofa-nordic", "beige", "Sofa Nordic 3-osobowa", {
      attributes: { kolor: "beżowy" },
      price_pln: "2599.00",
      delivery_pln: null,
      delivery_known: false,
    }),
    make("lamp-arc", "black", "Lampa podłogowa Arc", {
      attributes: { kolor: "czarny" },
      price_pln: "189.00",
      delivery_pln: "0.00",
      delivery_known: true,
      dimensions: null,
    }),
    make("lamp-arc", "white", "Lampa podłogowa Arc", {
      attributes: { kolor: "biały" },
      price_pln: null,
      price_is_gross: null,
      delivery_pln: "0.00",
      delivery_known: true,
      dimensions: null,
    }),
  ];
}

/**
 * The interior architect as one stateful scenario, built fresh per test. It behaves like the real API where the
 * screens depend on it: the server fetches the offer itself (the client never names a price), expired or
 * unavailable offers stay out of the sum and are counted, an unknown price is never zero, one generation is active
 * per project, cancelling works only while queued, and a generation advances queued, running, then succeeded or
 * failed each time it is read. A file whose text does not start with `FAKEIMG` is refused as not an image.
 */
export function createInterior(options: InteriorOptions = {}): InteriorFlow {
  const projects = new Map<string, ProjectOut>();
  const generations = new Map<string, GenerationOut[]>();
  const offerState = new Map<string, OfferOut["state"]>();
  const calls: string[] = [];
  const offers = interiorOffers();
  let counter = 0;
  const next = () => IID(++counter);
  const now = "2026-10-21T10:00:00Z";
  const expiry = "2026-11-20T10:00:00Z";
  const reply = (operation: string, name: string): Reply => replyFrom(fx(operation, name));
  const closed = (operation: string): Reply | null =>
    options.closed === true ? reply(operation, "not_in_beta") : null;
  const missing = (operation: string, name = "unknown"): Reply => reply(operation, name);

  const media = (purpose: MediaRefOut["purpose"]): MediaRefOut => ({
    media_id: next(),
    purpose,
    state: "stored",
    width: 640,
    height: 480,
    content_digest: `${String(counter).padStart(2, "0")}`.repeat(32),
    expires_at: expiry,
  });

  const withState = (o: OfferOut): OfferOut => ({ ...o, state: offerState.get(o.variant_id) ?? o.state });
  const rebuild = (p: ProjectOut): ProjectOut => {
    const selections = (p.selections ?? []).map((sel): SelectionOut => {
      const base = offers.find(
        (o) => o.product_id === sel.offer.product_id && o.variant_id === sel.offer.variant_id,
      );
      const offer = withState({ ...sel.offer, state: base?.state ?? "fresh" });
      const total =
        offer.state === "fresh" && offer.price_pln !== null
          ? decimal(grosze(offer.price_pln) * sel.quantity)
          : null;
      return { ...sel, offer, line_total_pln: total };
    });
    let subtotal = 0;
    let priced = 0;
    let unpriced = 0;
    let stale = 0;
    let deliveryKnown = 0;
    let deliveryUnknown = 0;
    for (const item of p.items) {
      if (item.price_pln === null) unpriced += 1;
      else {
        priced += 1;
        subtotal += grosze(item.price_pln) * item.quantity;
      }
    }
    for (const sel of selections) {
      if (sel.offer.state !== "fresh") stale += 1;
      else if (sel.offer.price_pln === null) unpriced += 1;
      else {
        priced += 1;
        subtotal += grosze(sel.offer.price_pln) * sel.quantity;
        if (sel.offer.delivery_known && sel.offer.delivery_pln !== null)
          deliveryKnown += grosze(sel.offer.delivery_pln);
        else deliveryUnknown += 1;
      }
    }
    const complete = unpriced === 0 && stale === 0 && deliveryUnknown === 0 && priced > 0;
    return {
      ...p,
      selections,
      basket: {
        known_subtotal_pln: decimal(subtotal),
        priced_lines: priced,
        unpriced_lines: unpriced,
        stale_lines: stale,
        delivery_known_pln: decimal(deliveryKnown),
        delivery_unknown_lines: deliveryUnknown,
        complete,
      },
    };
  };
  const save = (p: ProjectOut): ProjectOut => {
    const built = rebuild(p);
    projects.set(built.project_id, built);
    return built;
  };
  const blank = (name: string, room: ProjectOut["brief"]["room_type"]): ProjectOut => ({
    project_id: next(),
    name,
    brief: { room_type: room, style: null, budget_pln: null, notes: null, keep: [] },
    source: null,
    items: [],
    selections: [],
    revisions: [],
    basket: {
      known_subtotal_pln: "0.00",
      priced_lines: 0,
      unpriced_lines: 0,
      stale_lines: 0,
      delivery_known_pln: "0.00",
      delivery_unknown_lines: 0,
      complete: false,
    },
    created_at: now,
    expires_at: expiry,
  });
  const snapshot = (found: ProjectOut): ProjectOut => {
    const built = rebuild(found);
    const revision: RevisionOut = {
      revision_id: next(),
      number: found.revisions.length + 1,
      brief: built.brief,
      source_digest: found.source?.content_digest ?? null,
      items: found.items.map((i) => ({
        name: i.name,
        quantity: i.quantity,
        price_pln: i.price_pln,
        url: i.url,
        photo_digest: i.photo?.content_digest ?? null,
      })),
      selections: (built.selections ?? []).map((x) => ({ quantity: x.quantity, offer: x.offer })),
      basket: built.basket,
      created_at: now,
    };
    return save({ ...found, revisions: [revision, ...found.revisions] });
  };
  if (options.seeded !== false) {
    const seed = blank("Salon", "living_room");
    const first = save({
      ...seed,
      source: media("source"),
      brief: { ...seed.brief, style: "skandynawski", budget_pln: "5000.00" },
    });
    if (options.rich === true) {
      const offer = offers[0];
      if (offer === undefined) throw new Error("no offer");
      const item = {
        item_id: next(),
        name: "Stary fotel",
        quantity: 1,
        price_pln: null,
        url: null,
        photo: null,
        created_at: now,
      };
      const line: SelectionOut = {
        selection_id: next(),
        quantity: 1,
        offer,
        line_total_pln: null,
        checked_at: now,
      };
      snapshot(save({ ...first, items: [item], selections: [line] }));
    }
  }
  const project = (id: string | undefined): ProjectOut | undefined => projects.get(id ?? "");
  const advance = (g: GenerationOut): GenerationOut => {
    if (options.hold === true) return g;
    if (g.state === "queued") return { ...g, state: "running", started_at: now };
    if (g.state !== "running") return g;
    if (options.failWith !== undefined && options.failWith !== null)
      return {
        ...g,
        state: "failed",
        error_code: options.failWith,
        finished_at: now,
        cost_usd: options.failWith === "AMBIGUOUS" ? "0.100000" : null,
        cost_estimated: options.failWith === "AMBIGUOUS",
      };
    return {
      ...g,
      state: "succeeded",
      finished_at: now,
      output: media("render"),
      cost_usd: "0.034000",
      references_used: 2,
      references_skipped: 1,
    };
  };
  const read = (projectId: string): GenerationOut[] => {
    const all = generations.get(projectId) ?? [];
    const advanced = all.map((g) => advance(g));
    generations.set(projectId, advanced);
    return advanced;
  };

  const op = (operation: string, handler: (request: MockRequest) => Reply): Route => ({
    operation,
    reply: (request) => {
      calls.push(`${request.method} ${request.url.pathname}`);
      return closed(operation) ?? handler(request);
    },
  });
  const P = "/api/interior/projects";
  const routes: Route[] = [
    op(`GET ${P}`, () => ({
      status: 200,
      body: [...projects.values()].map((p) => ({
        project_id: p.project_id,
        name: p.name,
        room_type: p.brief.room_type,
        has_source: p.source !== null,
        revisions: p.revisions.length,
        created_at: p.created_at,
        expires_at: p.expires_at,
      })),
    })),
    op(`POST ${P}`, (r) => {
      const body = r.body as { name: string; brief: ProjectOut["brief"] };
      const created = save({
        ...blank(body.name, body.brief.room_type),
        brief: { ...body.brief, keep: body.brief.keep ?? [] },
      });
      return { status: 201, body: created };
    }),
    op(`GET ${P}/{project_id}`, (r) => {
      const found = project(r.params["project_id"]);
      return found === undefined ? missing(`GET ${P}/{project_id}`) : { status: 200, body: rebuild(found) };
    }),
    op(`PUT ${P}/{project_id}`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined) return missing(`PUT ${P}/{project_id}`);
      const body = r.body as { name: string; brief: ProjectOut["brief"] };
      return {
        status: 200,
        body: save({ ...found, name: body.name, brief: { ...body.brief, keep: body.brief.keep ?? [] } }),
      };
    }),
    op(`DELETE ${P}/{project_id}`, (r) => {
      const id = r.params["project_id"] ?? "";
      if (!projects.delete(id)) return missing(`DELETE ${P}/{project_id}`);
      generations.delete(id);
      return { status: 204 };
    }),
    op(`POST ${P}/{project_id}/items`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined) return missing(`POST ${P}/{project_id}/items`, "unknown_project");
      const body = r.body as {
        name: string;
        quantity?: number;
        price_pln?: string | null;
        url?: string | null;
      };
      const item = {
        item_id: next(),
        name: body.name,
        quantity: body.quantity ?? 1,
        price_pln: body.price_pln ?? null,
        url: body.url ?? null,
        photo: null,
        created_at: now,
      };
      return { status: 201, body: save({ ...found, items: [...found.items, item] }) };
    }),
    op(`PUT ${P}/{project_id}/items/{item_id}`, (r) => {
      const found = project(r.params["project_id"]);
      const body = r.body as {
        name: string;
        quantity?: number;
        price_pln?: string | null;
        url?: string | null;
      };
      const old = found?.items.find((i) => i.item_id === r.params["item_id"]);
      if (found === undefined || old === undefined) return missing(`PUT ${P}/{project_id}/items/{item_id}`);
      const updated = {
        ...old,
        name: body.name,
        quantity: body.quantity ?? 1,
        price_pln: body.price_pln ?? null,
        url: body.url ?? null,
      };
      return {
        status: 200,
        body: save({ ...found, items: found.items.map((i) => (i.item_id === old.item_id ? updated : i)) }),
      };
    }),
    op(`DELETE ${P}/{project_id}/items/{item_id}`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined || !found.items.some((i) => i.item_id === r.params["item_id"]))
        return missing(`DELETE ${P}/{project_id}/items/{item_id}`);
      save({ ...found, items: found.items.filter((i) => i.item_id !== r.params["item_id"]) });
      return { status: 204 };
    }),
    op(`POST ${P}/{project_id}/source`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined) return missing(`POST ${P}/{project_id}/source`);
      if (options.storageDown === true)
        return reply(`POST ${P}/{project_id}/source`, "storage_not_configured");
      if (typeof r.body !== "string" || !r.body.startsWith("FAKEIMG"))
        return reply(`POST ${P}/{project_id}/source`, "not_an_image");
      const source = media("source");
      save({ ...found, source });
      return { status: 201, body: source };
    }),
    op(`PUT ${P}/{project_id}/items/{item_id}/photo`, (r) => {
      const found = project(r.params["project_id"]);
      const old = found?.items.find((i) => i.item_id === r.params["item_id"]);
      if (found === undefined || old === undefined)
        return missing(`PUT ${P}/{project_id}/items/{item_id}/photo`, "unknown_item");
      if (typeof r.body !== "string" || !r.body.startsWith("FAKEIMG"))
        return reply(`PUT ${P}/{project_id}/items/{item_id}/photo`, "not_an_image");
      const photo = media("custom_item");
      save({ ...found, items: found.items.map((i) => (i.item_id === old.item_id ? { ...i, photo } : i)) });
      return { status: 200, body: photo };
    }),
    {
      operation: `GET ${P}/{project_id}/media/{media_id}`,
      reply: () => ({
        status: 200,
        text: SVG,
        contentType: "image/svg+xml",
        headers: { "cache-control": "private, no-store" },
      }),
    },
    op("GET /api/interior/catalogue", () =>
      options.noCatalogue === true
        ? { status: 200, body: { available: false, provider: null, source_label: null, is_demo: false } }
        : reply("GET /api/interior/catalogue", "demo_source"),
    ),
    {
      operation: "GET /api/interior/catalogue/demo-image/{product_id}/{variant_id}",
      reply: { status: 200, text: SVG, contentType: "image/svg+xml" },
    },
    op(`GET ${P}/{project_id}/catalogue/search`, (r) => {
      if (options.noCatalogue === true)
        return reply(`GET ${P}/{project_id}/catalogue/search`, "no_source_connected");
      const needle = (r.url.searchParams.get("q") ?? "").toLowerCase();
      const hits = offers.filter(
        (o) => needle === "" || `${o.title} ${o.product_id}`.toLowerCase().includes(needle),
      );
      return {
        status: 200,
        body: hits.map((offer) => ({
          offer: withState(offer),
          flags:
            offer.price_pln === null ? ["price_unknown"] : offer.delivery_known ? [] : ["delivery_unknown"],
        })),
      };
    }),
    op(`POST ${P}/{project_id}/selections`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined) return missing(`POST ${P}/{project_id}/selections`, "unknown_project");
      const body = r.body as { provider: string; product_id: string; variant_id: string; quantity?: number };
      const offer = offers.find((o) => o.product_id === body.product_id && o.variant_id === body.variant_id);
      if (offer === undefined || offerState.get(offer.variant_id) === "unavailable")
        return reply(`POST ${P}/{project_id}/selections`, "out_of_stock");
      const line: SelectionOut = {
        selection_id: next(),
        quantity: body.quantity ?? 1,
        offer,
        line_total_pln: null,
        checked_at: now,
      };
      return { status: 201, body: save({ ...found, selections: [...(found.selections ?? []), line] }) };
    }),
    op(`PUT ${P}/{project_id}/selections/{selection_id}`, (r) => {
      const found = project(r.params["project_id"]);
      const sel = found?.selections?.find((x) => x.selection_id === r.params["selection_id"]);
      if (found === undefined || sel === undefined)
        return missing(`PUT ${P}/{project_id}/selections/{selection_id}`);
      const quantity = (r.body as { quantity: number }).quantity;
      return {
        status: 200,
        body: save({
          ...found,
          selections: (found.selections ?? []).map((x) => (x === sel ? { ...x, quantity } : x)),
        }),
      };
    }),
    op(`DELETE ${P}/{project_id}/selections/{selection_id}`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined || !found.selections?.some((x) => x.selection_id === r.params["selection_id"]))
        return missing(`DELETE ${P}/{project_id}/selections/{selection_id}`);
      save({
        ...found,
        selections: (found.selections ?? []).filter((x) => x.selection_id !== r.params["selection_id"]),
      });
      return { status: 204 };
    }),
    op(`POST ${P}/{project_id}/selections/{selection_id}/refresh`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined || !found.selections?.some((x) => x.selection_id === r.params["selection_id"]))
        return missing(`POST ${P}/{project_id}/selections/{selection_id}/refresh`);
      offerState.delete(
        (found.selections ?? []).find((x) => x.selection_id === r.params["selection_id"])?.offer.variant_id ??
          "",
      );
      return { status: 200, body: save(found) };
    }),
    op(`POST ${P}/{project_id}/revisions`, (r) => {
      const found = project(r.params["project_id"]);
      if (found === undefined) return missing(`POST ${P}/{project_id}/revisions`);
      return { status: 201, body: snapshot(found) };
    }),
    op(`POST ${P}/{project_id}/generations`, (r) => {
      const id = r.params["project_id"] ?? "";
      const found = project(id);
      const body = r.body as { revision_id: string };
      const revision = found?.revisions.find((x) => x.revision_id === body.revision_id);
      if (found === undefined || revision === undefined)
        return reply(`POST ${P}/{project_id}/generations`, "unknown_revision");
      if (options.generationOff === true) return reply(`POST ${P}/{project_id}/generations`, "switched_off");
      if (revision.source_digest === null)
        return reply(`POST ${P}/{project_id}/generations`, "no_room_photo");
      const all = generations.get(id) ?? [];
      const active = all.find((g) => g.state === "queued" || g.state === "running");
      if (active !== undefined) {
        return active.revision_id === body.revision_id
          ? { status: 200, body: active }
          : reply(`POST ${P}/{project_id}/generations`, "another_revision_while_busy");
      }
      const created: GenerationOut = {
        ...bodyOf<GenerationOut>(fx(`POST ${P}/{project_id}/generations`, "queued")),
        generation_id: next(),
        revision_id: body.revision_id,
        state: "queued",
        error_code: null,
        output: null,
        cost_usd: null,
        cost_estimated: false,
        references_used: 0,
        references_skipped: 0,
        created_at: now,
        started_at: null,
        finished_at: null,
      };
      generations.set(id, [created, ...all]);
      return { status: 202, body: created };
    }),
    op(`GET ${P}/{project_id}/generations`, (r) => ({
      status: 200,
      body: read(r.params["project_id"] ?? ""),
    })),
    op(`GET ${P}/{project_id}/generations/{generation_id}`, (r) => {
      const found = read(r.params["project_id"] ?? "").find(
        (g) => g.generation_id === r.params["generation_id"],
      );
      return found === undefined
        ? missing(`GET ${P}/{project_id}/generations/{generation_id}`)
        : { status: 200, body: found };
    }),
    op(`POST ${P}/{project_id}/generations/{generation_id}/cancel`, (r) => {
      const id = r.params["project_id"] ?? "";
      const all = generations.get(id) ?? [];
      const found = all.find((g) => g.generation_id === r.params["generation_id"]);
      if (found === undefined) return missing(`POST ${P}/{project_id}/generations/{generation_id}/cancel`);
      if (found.state === "running")
        return reply(`POST ${P}/{project_id}/generations/{generation_id}/cancel`, "already_running");
      const cancelled =
        found.state === "queued" ? { ...found, state: "cancelled" as const, finished_at: now } : found;
      generations.set(
        id,
        all.map((g) => (g === found ? cancelled : g)),
      );
      return { status: 200, body: cancelled };
    }),
  ];
  const base = scenario(
    "interior",
    "Architekt wnętrz with a working fake server: projects, items, catalogue, board, versions and visualisations.",
    routes,
  );
  return {
    ...base,
    calls,
    projects,
    generations,
    setOfferState: (variantId, state) => {
      offerState.set(variantId, state);
      for (const p of projects.values()) save(p);
    },
  };
}

export const SCENARIOS = {
  firstVisit: scenario(
    "firstVisit",
    "Nobody is signed in: every session route answers 401.",
    [me("no_session")],
    [],
  ),
  empty: scenario("empty", "Signed in with credits and no analyses yet.", [EMPTY_PAGE]),
  settings: createSettings(),
  settingsNoPassword: createSettings([], "settingsNoPassword", false),
  settingsOneSession: createSettings(
    [fromFixture("GET /api/auth/sessions", "one_session")],
    "settingsOneSession",
  ),
  settingsSessionsFailing: createSettings(
    [
      {
        operation: "GET /api/auth/sessions",
        reply: { status: 503, body: NOT_READY, contentType: "application/problem+json" },
      },
    ],
    "settingsSessionsFailing",
  ),
  loaded: scenario("loaded", "Five distinct finished analyses, newest first.", auditRoutes(SUCCEEDED_AUDITS)),
  pending: scenario("pending", "An analysis was accepted and has not run yet.", [
    EMPTY_PAGE,
    fromFixture("GET /api/audits/{audit_id}", "queued_not_yet_run"),
    fromFixture("POST /api/audits", "accepted"),
  ]),
  degraded: scenario("degraded", "A finished analysis without photo assessment.", [
    fromFixture("GET /api/audits/{audit_id}", "succeeded_degraded"),
  ]),
  rejectedRent: scenario("rejectedRent", "The listing is a rental: rejected, no charge.", [
    fromFixture("GET /api/audits/{audit_id}", "rejected_rent_is_not_a_deal"),
    fromFixture("GET /api/audits/{audit_id}/events", "rejected_transcript"),
  ]),
  rejectedFractional: scenario("rejectedFractional", "A fractional share: rejected, no charge.", [
    fromFixture("GET /api/audits/{audit_id}", "rejected_fractional_ownership"),
  ]),
  failedUpstream: scenario("failedUpstream", "Otodom blocked the fetch: failed, charge released.", [
    fromFixture("GET /api/audits/{audit_id}", "failed_upstream_blocked"),
    fromFixture("GET /api/audits/{audit_id}/events", "failure_transcript"),
  ]),
  failedInput: scenario("failedInput", "The listing is gone: failed input, charge released.", [
    fromFixture("GET /api/audits/{audit_id}", "failed_input_listing_gone"),
  ]),
  insufficientCredits: scenario("insufficientCredits", "No reports left: submitting answers 402.", [
    withMe((m) => ({ ...m, credit_balance: 0 })),
    fromFixture("POST /api/audits", "no_credits"),
  ]),
  unlimited: scenario(
    "unlimited",
    "The account holds the explicit no-limit entitlement and a zero balance.",
    [withMe((m) => ({ ...m, credit_balance: 0, plan: { ...m.plan, unlimited_reports: true } }))],
  ),
  mixed: scenario("mixed", "Six analyses in six different states.", auditRoutes(MIXED_AUDITS)),
  auditsFailing: scenario("auditsFailing", "The list of analyses cannot be loaded (503).", [
    {
      operation: "GET /api/audits",
      reply: { status: 503, body: NOT_READY, contentType: "application/problem+json" },
    },
  ]),
  slow: scenario("slow", "The list of analyses takes a while: the loading state.", [
    {
      operation: "GET /api/audits",
      reply: { status: 200, body: { items: [], next_cursor: null } satisfies AuditPage, delayMs: 1500 },
    },
  ]),
  collection: createCollection(),
  shop: createBilling(),
  shopHistory: scenario(
    "shopHistory",
    "A shop and a history: one granted, one waiting for payment, one refunded, one under review.",
    [
      {
        operation: "GET /api/billing/purchases",
        reply: { status: 200, body: { purchases: SHOP_HISTORY } },
      },
      {
        operation: "GET /api/billing/purchases/{purchase_id}",
        reply: (request) => {
          const found = SHOP_HISTORY.find((p) => p.purchase_id === request.params["purchase_id"]);
          return found === undefined
            ? replyFrom(fx("GET /api/billing/purchases/{purchase_id}", "foreign_purchase"))
            : { status: 200, body: found };
        },
      },
      {
        operation: "GET /api/billing/purchases/{purchase_id}/invoice",
        reply: { status: 200, body: { url: "https://invoice.example.test/document.pdf" } },
      },
    ],
  ),
  savedLoaded: createSaved(),
  interior: createInterior({ rich: true }),
  interiorClosed: createInterior({ closed: true }),
  interiorEmpty: createInterior({ seeded: false }),
  interiorNoCatalogue: createInterior({ noCatalogue: true, rich: true }),
  market: createMarket(),
  marketEmpty: createMarket({ empty: true }),
  marketFree: createMarket({ free: true }),
  marketUnlimited: createMarket({ unlimited: true }),
  marketListFailing: createMarket({ listFails: true }),
  unsupportedReport: scenario(
    "unsupportedReport",
    "A finished audit whose stored result has a schema version this build does not know.",
    auditRoutes(withResult((r) => ({ ...r, schema_version: 2, valuation: { secret: "hidden" } }))),
  ),
  invalidReport: scenario(
    "invalidReport",
    "A finished audit whose stored result lacks required parts.",
    auditRoutes(withResult((r) => ({ schema_version: r["schema_version"] }))),
  ),
  richReport: scenario(
    "richReport",
    "A report with a link to the listing, quoted evidence and a hostile-looking excerpt.",
    auditRoutes(
      withResult((r) => {
        const listing = r["listing"] as Record<string, unknown>;
        const legal = r["legal"] as Record<string, unknown>;
        const ownership = r["ownership"] as Record<string, unknown>;
        return {
          ...r,
          listing: { ...listing, url: RICH_URL },
          legal: { ...legal, evidence: ["Cena zawiera podatek VAT 23%."] },
          ownership: { ...ownership, evidence: ["<img src=x onerror=alert(1)> własność"] },
        };
      }),
    ),
  ),
  unknownAudit: scenario("unknownAudit", "The audit id is not the person's: 404.", auditRoutes([])),
  auditUnavailable: scenario("auditUnavailable", "One analysis cannot be loaded (503).", [
    {
      operation: "GET /api/audits/{audit_id}",
      reply: { status: 503, body: NOT_READY, contentType: "application/problem+json" },
    },
  ]),
  expiredMidUse: scenario(
    "expiredMidUse",
    "The session ends while the page is in use: the next request is a 401.",
    [fromFixture("GET /api/audits", "no_session")],
  ),
  unverified: scenario("unverified", "Signed in, but the e-mail address is not confirmed yet.", [
    withMe((m) => ({ ...m, email_verified: false })),
    EMPTY_PAGE,
    fromFixture("POST /api/auth/register/resend", "accepted"),
  ]),
  breakerOpen: scenario("breakerOpen", "Otodom is rate-limiting us: the breaker is open.", [
    fromFixture("GET /api/me", "upstream_breaker_open"),
  ]),
  billingDisabled: scenario("billingDisabled", "Purchases are not enabled yet.", [
    fromFixture("GET /api/billing/packs", "billing_disabled"),
    fromFixture("POST /api/billing/checkout", "billing_disabled"),
  ]),
  sessionExpired: scenario("sessionExpired", "The session ended: every session route answers 401.", [
    me("no_session"),
    fromFixture("GET /api/audits", "no_session"),
  ]),
  offline: scenario(
    "offline",
    "The network is down: every request fails before any answer.",
    ["GET /api/me", "GET /api/audits", "GET /api/billing/packs", "GET /api/saved"].map((operation) => ({
      operation,
      reply: { status: 0, networkError: true },
    })),
    [],
  ),
  reconnecting: scenario("reconnecting", "The progress stream is interrupted.", [
    ...auditRoutes(SUCCEEDED_AUDITS).filter((r) => r.operation !== "GET /api/audits/{audit_id}/events"),
    { operation: "GET /api/audits/{audit_id}/events", reply: { status: 0, networkError: true } },
  ]),
} as const satisfies Record<string, Scenario>;

export type ScenarioName = keyof typeof SCENARIOS;
export const SCENARIO_NAMES = Object.keys(SCENARIOS) as ScenarioName[];

// ------------------------------------------------------------------------------------------- a collection
export interface CollectionOptions {
  /** How many analyses the person has (default 120). */
  readonly count?: number;
  /** Requests for pages after the first fail with a 503 until `state.failing` is set false. */
  readonly failPage?: number;
  /** A repeated read of the first page (a refresh) answers after this many milliseconds. */
  readonly refreshDelayMs?: number;
}

export interface Collection extends Scenario {
  readonly state: { requests: string[]; failing: boolean };
  readonly audits: readonly AuditSummary[];
}

/**
 * A heavy account: `count` analyses built from the captured shapes (five finished, plus queued, degraded,
 * rejected and failed ones), newest first, with the server's list semantics: filters by status, grade and
 * Otodom-id prefix, `limit`, and an opaque cursor that ends with `null`. The mock pages exactly like the API so
 * the page can be tested against paging, not against a fixed array.
 */
export function createCollection(options: CollectionOptions = {}): Collection {
  const count = options.count ?? 120;
  const pool = [...SUCCEEDED_AUDITS, ...MIXED_AUDITS.filter((a) => a.status !== "succeeded")];
  const audits: AuditSummary[] = Array.from({ length: count }, (_, i) => {
    const base = summaryOf(pool[i % pool.length] as AuditOut);
    const at = new Date(Date.parse("2026-10-14T12:00:00Z") - i * 5_400_000)
      .toISOString()
      .replace(".000Z", "Z");
    return {
      ...base,
      audit_id: `00000000-0000-4000-8000-${(0x100000 + i).toString(16).padStart(12, "0")}`,
      otodom_id: `IDLST${String(i).padStart(4, "0")}`,
      created_at: at,
      finished_at: base.finished_at === null ? null : at,
    };
  });
  const state = { requests: [] as string[], failing: options.failPage !== undefined };
  const list: Route = {
    operation: "GET /api/audits",
    reply: (request) => {
      const q = request.url.searchParams;
      state.requests.push(request.url.search);
      const cursor = q.get("cursor");
      // While `failing`, every request for a further page fails (set it false to let the retry through).
      if (cursor !== null && state.failing)
        return { status: 503, body: NOT_READY, contentType: "application/problem+json" };
      const statuses = q.getAll("status");
      const grade = q.get("grade");
      const prefix = q.get("q");
      const limit = Math.min(Number(q.get("limit") ?? "50"), 100);
      const matching = audits.filter(
        (a) =>
          (statuses.length === 0 || statuses.includes(a.status)) &&
          (grade === null || a.grade === grade) &&
          (prefix === null || a.otodom_id.startsWith(prefix)),
      );
      const start = cursor === null ? 0 : Number(atob(cursor).replace("cursor:", ""));
      if (!Number.isInteger(start) || start < 0) return replyFrom(fx("GET /api/audits", "invalid_cursor"));
      const items = matching.slice(start, start + limit);
      const next = start + limit < matching.length ? btoa(`cursor:${start + limit}`) : null;
      const slow = options.refreshDelayMs !== undefined && cursor === null && state.requests.length > 1;
      return {
        status: 200,
        body: { items, next_cursor: next } satisfies AuditPage,
        ...(slow ? { delayMs: options.refreshDelayMs } : {}),
      };
    },
  };
  const detail: Route = {
    operation: "GET /api/audits/{audit_id}",
    reply: (request) => ({
      status: 200,
      body: { ...(SUCCEEDED_AUDITS[0] as AuditOut), audit_id: request.params["audit_id"] ?? "" },
    }),
  };
  const base = scenario("collection", `A heavy account: ${count} analyses over cursor paging.`, [
    list,
    detail,
  ]);
  return { ...base, state, audits };
}

// ------------------------------------------------------------------------------------------ a run, stateful
export const RUN_AUDIT_ID = "00000000-0000-4000-8000-0000000000a1";

export interface RunOptions {
  /** How the analysis ends. Default: succeeded. */
  readonly outcome?: "succeeded" | "rejected" | "failed";
  /** The stream drops once after the first frames; the browser reconnects and the rest arrives later. */
  readonly interrupt?: boolean;
  /** The stream cannot be opened: the page must fall back to polling the audit. */
  readonly streamDown?: "http" | "network";
  /** The stream connects and delivers the first frames, then never says anything more (a silent proxy). */
  readonly silent?: boolean;
  /** The POST itself fails (a dropped connection, a problem body); the list then says whether it arrived. */
  readonly post?: Reply;
  /** The POST answers after this many milliseconds, so the busy form is there to be clicked again. */
  readonly postDelayMs?: number;
  /** What `GET /api/audits` answers after such a failure (default: an empty list). */
  readonly listAfterPost?: AuditSummary[];
  /** The list cannot be read either (the network is down): whether the POST arrived is unknowable. */
  readonly listFails?: boolean;
  /**
   * With `post` failing: the server DID create the audit for that `Idempotency-Key` and only the answer was lost.
   * The list then finds it by `request_key`, and a resend with the same key gets the same audit back.
   */
  readonly lostAnswer?: boolean;
  /** `post` fails only the first time (the connection comes back for the resend). */
  readonly postFailsOnce?: boolean;
}

export interface Run extends Scenario {
  /** `keys`: the `Idempotency-Key` of every POST, in order. */
  readonly state: { posts: number; streams: number; reads: number; settled: boolean; keys: string[] };
}

const RUN_FIXTURES = {
  succeeded: { audit: "succeeded_warszawa", events: "success_transcript" },
  rejected: { audit: "rejected_rent_is_not_a_deal", events: "rejected_transcript" },
  failed: { audit: "failed_upstream_blocked", events: "failure_transcript" },
} as const;

const reId = <T extends { audit_id: string }>(body: T): T => ({ ...body, audit_id: RUN_AUDIT_ID });

/**
 * One analysis from the click to its end, with the pieces that change while it runs: the balance (reserved at
 * once, kept on success, given back otherwise), the audit (queued, then final), the stream (frames, optionally
 * interrupted once) and the counters a test asserts on (how many POSTs, how many streams were opened).
 */
/** The list row of an analysis created a moment ago. */
function queuedSummary(): AuditSummary {
  return {
    audit_id: RUN_AUDIT_ID,
    otodom_id: "ID4abcd",
    status: "queued",
    error_code: null,
    created_at: new Date().toISOString(),
    finished_at: null,
    grade: null,
    asking_price_pln: null,
    max_bid_pln: null,
  };
}

export function createRun(options: RunOptions = {}): Run {
  const kind = options.outcome ?? "succeeded";
  const fixtures = RUN_FIXTURES[kind];
  const state = { posts: 0, streams: 0, reads: 0, settled: false, keys: [] as string[] };
  /** Request keys the server has recorded an audit for (what `?request_key=` finds). */
  const recorded = new Set<string>();
  const me = bodyOf<MeDetail>(fx("GET /api/me", "with_credits_and_flags"));
  const final = reId(bodyOf<AuditOut>(fx("GET /api/audits/{audit_id}", fixtures.audit)));
  const queued = reId(bodyOf<AuditOut>(fx("GET /api/audits/{audit_id}", "queued_not_yet_run")));
  const transcript = fx("GET /api/audits/{audit_id}/events", fixtures.events).events ?? [];
  const frames = transcript.map((e) => ({
    ...e,
    data: { ...(e.data as Record<string, unknown>), audit_id: RUN_AUDIT_ID },
  }));
  const partial = frames.filter((e) => e.event === "progress").slice(0, 3);
  const withRetry = (list: typeof frames) => `retry: 50\n\n${eventStreamText(list)}`;
  const streamReply = (): Reply => {
    state.streams += 1;
    if (options.streamDown === "network") return { status: 0, networkError: true };
    if (options.streamDown === "http")
      return { status: 503, body: NOT_READY, contentType: "application/problem+json" };
    const headers = { "cache-control": "no-store" };
    if (options.silent === true)
      return {
        status: 200,
        text: `retry: 500\n\n${eventStreamText(partial)}`,
        contentType: "text/event-stream",
        headers,
      };
    const type = "text/event-stream";
    if (options.interrupt === true && state.streams === 1)
      return { status: 200, text: withRetry(partial), contentType: type, headers };
    // The second answer repeats the last frame the first one sent: the page must show it once.
    const rest =
      options.interrupt === true ? [...partial.slice(-1), ...frames.slice(partial.length)] : frames;
    state.settled = true;
    return {
      status: 200,
      text: withRetry(rest),
      contentType: type,
      headers,
      ...(options.interrupt === true ? { delayMs: 900 } : {}),
    };
  };
  const routes: Route[] = [
    {
      operation: "GET /api/me",
      reply: () => ({
        status: 200,
        body: {
          ...me,
          credit_balance:
            me.credit_balance - (state.posts > 0 && !(state.settled && kind !== "succeeded") ? 1 : 0),
        },
      }),
    },
    {
      operation: "POST /api/audits",
      reply: (request) => {
        state.posts += 1;
        const key = request.headers["idempotency-key"] ?? "";
        state.keys.push(key);
        const failed =
          options.post !== undefined &&
          (options.postFailsOnce === true
            ? state.posts === 1
            : !(options.lostAnswer === true && recorded.has(key)));
        if (options.lostAnswer === true || !failed) recorded.add(key);
        if (failed && options.post !== undefined) return options.post;
        return {
          status: 202,
          body: {
            audit_id: RUN_AUDIT_ID,
            credits_remaining: me.credit_balance - 1,
            events_url: `/api/audits/${RUN_AUDIT_ID}/events`,
            status: "queued",
          },
          ...(options.postDelayMs !== undefined ? { delayMs: options.postDelayMs } : {}),
        };
      },
    },
    {
      operation: "GET /api/audits/{audit_id}",
      reply: () => {
        state.reads += 1;
        // Without a stream the page polls: the analysis finishes between two polls.
        if ((options.streamDown !== undefined || options.silent === true) && state.reads >= 2)
          state.settled = true;
        return { status: 200, body: state.settled ? final : queued };
      },
    },
    { operation: "GET /api/audits/{audit_id}/events", reply: streamReply },
    {
      operation: "GET /api/audits",
      reply: (request) => {
        if (options.listFails === true) return { status: 0, networkError: true };
        const key = request.url.searchParams.get("request_key");
        const items =
          key === null
            ? (options.listAfterPost ?? [])
            : recorded.has(key)
              ? [{ ...queuedSummary(), audit_id: RUN_AUDIT_ID }]
              : [];
        return { status: 200, body: { items, next_cursor: null } satisfies AuditPage };
      },
    },
  ];
  const base = scenario("run", "One analysis from the click to its end.", routes);
  return { ...base, state };
}

// ----------------------------------------------------------------------------------------------- matching
const PARAM = /\{([a-z_]+)\}/g;

/** `/api/audits/{audit_id}` -> a matcher that also returns the path parameters. */
export function compileTemplate(template: string): (path: string) => Record<string, string> | null {
  const names: string[] = [];
  const pattern = new RegExp(
    `^${template.replace(PARAM, (_, name: string) => (names.push(name), "([^/]+)"))}$`,
  );
  return (path) => {
    const match = pattern.exec(path);
    if (match === null) return null;
    return Object.fromEntries(names.map((name, i) => [name, decodeURIComponent(match[i + 1] ?? "")]));
  };
}

export interface Matched {
  readonly route: Route;
  readonly params: Record<string, string>;
}

/** The scenario's route for a request, or null: the caller turns null into a loud failure. */
export function matchRoute(scenario: Scenario, method: string, path: string): Matched | null {
  for (const route of scenario.routes) {
    const [routeMethod, template] = route.operation.split(" ", 2);
    if (routeMethod !== method || template === undefined) continue;
    const params = compileTemplate(template)(path);
    if (params !== null) return { route, params };
  }
  return null;
}

export function resolveReply(matched: Matched, request: MockRequest): Reply {
  const { reply } = matched.route;
  return typeof reply === "function" ? reply(request) : reply;
}

// ------------------------------------------------------------------------------------------- auth flow
const wrongPassword = "wrong-password-1";
const WEAK = "password1234";

export interface AuthFlow extends Scenario {
  /** Mutable: a successful sign-in flips it, so a following GET /api/me answers like the real API would. */
  readonly state: { signedIn: boolean };
  readonly calls: string[];
}

/**
 * The sign-in surface as one stateful scenario: GET /api/me answers 401 until a sign-in succeeds, then the
 * signed-in profile, and 401 again after sign-out. Tokens and passwords steer the answer: a token starting with
 * `invalid` is refused, `exists` is an account that already exists, `wrong-password-1` is a bad password and
 * `password1234` a weak one. Built fresh per test (the state is the point), from the same fixtures as the others.
 */
export function createAuthFlow(overrides: Record<string, Reply> = {}): AuthFlow {
  const state = { signedIn: false };
  const calls: string[] = [];
  const me = bodyOf<MeDetail>(fx("GET /api/me", "with_credits_and_flags"));
  const reply = (operation: string, scenarioName: string): Reply =>
    overrides[operation] ?? replyFrom(fx(operation, scenarioName));
  const signIn = (operation: string, scenarioName: string): Reply => {
    state.signedIn = true;
    return reply(operation, scenarioName);
  };
  const tokenOf = (request: MockRequest): string => {
    const token = (request.body as { token?: unknown } | null)?.token;
    return typeof token === "string" ? token : "";
  };
  const routes: Route[] = [
    MARKET_EMPTY,
    OVERVIEW_EMPTY,
    {
      operation: "GET /api/me",
      reply: () => (state.signedIn ? { status: 200, body: me } : replyFrom(fx("GET /api/me", "no_session"))),
    },
    {
      operation: "POST /api/auth/login",
      reply: (request) => {
        calls.push("login");
        const password = (request.body as { password?: string } | null)?.password;
        if (overrides["POST /api/auth/login"] !== undefined) return overrides["POST /api/auth/login"];
        return password === wrongPassword
          ? replyFrom(fx("POST /api/auth/login", "wrong_password"))
          : signIn("POST /api/auth/login", "signed_in");
      },
    },
    {
      operation: "POST /api/auth/google",
      reply: (request) => {
        calls.push("google");
        const credential = (request.body as { credential?: string } | null)?.credential ?? "";
        if (credential.includes("unverified"))
          return replyFrom(fx("POST /api/auth/google", "email_unverified"));
        if (credential.includes("confirm"))
          return replyFrom(fx("POST /api/auth/google", "email_confirmation_required"));
        return signIn("POST /api/auth/google", "new_account");
      },
    },
    {
      operation: "POST /api/auth/email/start",
      reply: () => (calls.push("email-start"), reply("POST /api/auth/email/start", "accepted")),
    },
    {
      operation: "POST /api/auth/email/verify",
      reply: (request) => {
        calls.push(`email-verify:${tokenOf(request)}`);
        return tokenOf(request).startsWith("invalid")
          ? replyFrom(fx("POST /api/auth/email/verify", "link_invalid"))
          : signIn("POST /api/auth/email/verify", "signed_in");
      },
    },
    {
      operation: "POST /api/auth/register",
      reply: (request) => {
        calls.push("register");
        const password = (request.body as { password?: string } | null)?.password;
        return password === WEAK
          ? replyFrom(fx("POST /api/auth/register", "weak_password"))
          : reply("POST /api/auth/register", "accepted");
      },
    },
    {
      operation: "POST /api/auth/register/resend",
      reply: () => (calls.push("register-resend"), reply("POST /api/auth/register/resend", "accepted")),
    },
    {
      operation: "POST /api/auth/register/verify",
      reply: (request) => {
        const token = tokenOf(request);
        calls.push(`register-verify:${token}`);
        if (token.startsWith("invalid"))
          return replyFrom(fx("POST /api/auth/register/verify", "link_invalid"));
        if (token.startsWith("exists"))
          return replyFrom(fx("POST /api/auth/register/verify", "account_exists"));
        return signIn("POST /api/auth/register/verify", "account_created");
      },
    },
    {
      operation: "POST /api/auth/password/forgot",
      reply: () => (calls.push("forgot"), reply("POST /api/auth/password/forgot", "accepted")),
    },
    {
      operation: "POST /api/auth/password/reset",
      reply: (request) => {
        const token = tokenOf(request);
        calls.push(`reset:${token}`);
        const password = (request.body as { password?: string } | null)?.password;
        if (token.startsWith("invalid"))
          return replyFrom(fx("POST /api/auth/password/reset", "link_invalid"));
        return password === WEAK
          ? replyFrom(fx("POST /api/auth/password/reset", "weak_password"))
          : reply("POST /api/auth/password/reset", "password_set");
      },
    },
    {
      operation: "POST /api/auth/signout",
      reply: () => {
        calls.push("signout");
        // An override (a dropped connection, a 5xx) is a sign-out the server never performed: the session stays.
        const failed = overrides["POST /api/auth/signout"];
        if (failed !== undefined) return failed;
        state.signedIn = false;
        return reply("POST /api/auth/signout", "signed_out");
      },
    },
    SAVED_EMPTY,
    PACKS,
    EMPTY_PAGE,
  ];
  return {
    name: "authFlow",
    description: "Sign-in methods against a stateful session.",
    routes,
    state,
    calls,
  };
}
