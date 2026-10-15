/**
 * Sanitised API answers derived from a capture by scripts/derive_ui_fixtures.py (docs/FRONTEND-PLAN.md section 3).
 * Framework-neutral: Vitest (through MSW), the component catalog and the Playwright mocked lane all read these.
 * Never imported by production code (ESLint) and never present in `dist/` (`pnpm check:dist`).
 */

export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

export interface FixtureEvent {
  readonly id: string | null;
  readonly event: string | null;
  readonly data: unknown;
}

export interface Fixture {
  readonly operation: {
    readonly key: string;
    readonly operation_id: string;
    readonly method: HttpMethod;
    readonly path: string;
  };
  readonly scenario: string;
  readonly request: { readonly path: string; readonly body: unknown };
  readonly status: number;
  readonly content_type: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly body: unknown;
  readonly events?: readonly FixtureEvent[];
}

const modules = import.meta.glob<Fixture>("./fixtures/*/*.json", { eager: true, import: "default" });

export const ALL_FIXTURES: readonly Fixture[] = Object.values(modules);

const byKey = new Map<string, Fixture>(ALL_FIXTURES.map((f) => [`${f.operation.key} :: ${f.scenario}`, f]));

/** `fx("GET /api/audits/{audit_id}", "succeeded_torun")`; a typo fails loudly instead of rendering nothing. */
export function fx(operation: string, scenario: string): Fixture {
  const found = byKey.get(`${operation} :: ${scenario}`);
  if (found === undefined) {
    throw new Error(`no fixture "${scenario}" for ${operation}`);
  }
  return found;
}

export function fixturesFor(operation: string): readonly Fixture[] {
  return ALL_FIXTURES.filter((f) => f.operation.key === operation);
}

/** The body of a fixture as a typed value; the caller names the type it expects. */
export function bodyOf<T>(fixture: Fixture): T {
  return fixture.body as T;
}

export function eventStreamText(events: readonly FixtureEvent[]): string {
  return events
    .map(
      (e) =>
        `${e.id === null ? "" : `id: ${e.id}\n`}event: ${e.event ?? "message"}\ndata: ${JSON.stringify(e.data)}\n\n`,
    )
    .join("");
}
