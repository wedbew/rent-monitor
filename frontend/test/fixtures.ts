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

/**
 * Vite (Vitest, the catalog) globs the JSON files at build time; Playwright runs under plain Node, where
 * `import.meta.glob` does not exist, so it reads the same directory from disk.
 */
const globbed: Record<string, Fixture> | undefined =
  typeof import.meta.glob === "function"
    ? import.meta.glob<Fixture>("./fixtures/*/*.json", { eager: true, import: "default" })
    : undefined;

async function readFromDisk(): Promise<Fixture[]> {
  const { readdirSync, readFileSync } = await import("node:fs");
  const root = new URL("./fixtures/", import.meta.url);
  return readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap((dir) =>
      readdirSync(new URL(`${dir.name}/`, root))
        .filter((file) => file.endsWith(".json"))
        .map((file) => JSON.parse(readFileSync(new URL(`${dir.name}/${file}`, root), "utf8")) as Fixture),
    );
}

export const ALL_FIXTURES: readonly Fixture[] =
  globbed === undefined ? await readFromDisk() : Object.values(globbed);

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
