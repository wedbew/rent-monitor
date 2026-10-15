/**
 * Pure logic of the interaction gate (no browser): reading an ARIA snapshot, matching it against the registry and
 * comparing what was exercised with what is registered. Unit-tested in gate.test.ts; used by inventory.spec.ts and
 * coverage-reporter.ts.
 */
import {
  EVERY_PAGE,
  EVERY_PUBLIC_PAGE,
  type InteractiveRole,
  type Interaction,
  type Popup,
} from "./interactions";

export const INTERACTIVE_ROLES: ReadonlySet<string> = new Set<InteractiveRole>([
  "button",
  "link",
  "textbox",
  "searchbox",
  "checkbox",
  "radio",
  "combobox",
  "listbox",
  "option",
  "menuitem",
  "menuitemcheckbox",
  "menuitemradio",
  "tab",
  "switch",
  "slider",
  "spinbutton",
  "treeitem",
]);

export interface AriaNode {
  readonly role: string;
  readonly name: string | null;
  readonly attributes: readonly string[];
}

const LINE = /^([a-z]+)(?: "((?:[^"\\]|\\.)*)")?((?: \[[^\]]+\])*)(?::(?: .*)?)?$/;

/** The text content of a quoted YAML scalar line (Playwright quotes lines holding `:` or other specials). */
function unquote(text: string): string {
  if (text.startsWith("'") && text.endsWith("'")) return text.slice(1, -1).replace(/''/g, "'");
  return text;
}

/**
 * Nodes of a Playwright `ariaSnapshot()` (YAML-like). Only role, accessible name and bracketed attributes are read;
 * `text:`, `/url:` and similar property lines are skipped.
 */
export function parseAriaSnapshot(snapshot: string): AriaNode[] {
  const nodes: AriaNode[] = [];
  for (const raw of snapshot.split("\n")) {
    const trimmed = raw.trim();
    if (!trimmed.startsWith("- ")) continue;
    const body = unquote(trimmed.slice(2).trim());
    const match = LINE.exec(body);
    if (match === null) continue;
    const [, role = "", name, attrs = ""] = match;
    nodes.push({
      role,
      name: name === undefined ? null : name.replace(/\\"/g, '"').replace(/\\\\/g, "\\"),
      attributes: attrs.match(/\[[^\]]+\]/g) ?? [],
    });
  }
  return nodes;
}

export function interactiveNodes(snapshot: string): AriaNode[] {
  return parseAriaSnapshot(snapshot).filter((node) => INTERACTIVE_ROLES.has(node.role));
}

export function nameMatches(expected: string | RegExp, actual: string | null): boolean {
  if (actual === null) return false;
  return typeof expected === "string" ? expected === actual : expected.test(actual);
}

export interface Violation {
  readonly kind: "unnamed" | "unregistered" | "missing";
  readonly message: string;
}

export interface Scope {
  readonly page: string;
  readonly scenario: string;
  readonly viewport?: "desktop" | "mobile";
  readonly layout?: "app" | "public";
  /** The page state being inspected (see PageState); undefined is the base state. */
  readonly state?: string;
  /** Popup being inspected, or undefined for the page itself. */
  readonly within?: string;
}

function applies(entry: { readonly scenarios?: readonly string[] | undefined }, scenario: string): boolean {
  return entry.scenarios === undefined || entry.scenarios.includes(scenario);
}

/**
 * Compare what the browser shows with what is registered. An element that is nameless or unregistered is a
 * violation; so is a registered element (for this page, scenario and popup) that is not on the screen, which keeps
 * the registry from rotting.
 */
export function findViolations(
  snapshot: string,
  registry: readonly Interaction[],
  scope: Scope,
): Violation[] {
  const where = `${scope.page} / ${scope.scenario}${scope.state ? ` / ${scope.state}` : ""}${scope.within ? ` / ${scope.within}` : ""}`;
  const candidates = registry.filter(
    (e) =>
      (e.page === scope.page ||
        (e.page === EVERY_PAGE && scope.layout !== "public") ||
        (e.page === EVERY_PUBLIC_PAGE && scope.layout === "public")) &&
      e.within === scope.within &&
      // A page state brings its own scenario (often a factory with no registry name): its scenario is not filtered.
      (scope.state !== undefined || applies(e, scope.scenario)) &&
      (e.viewport === undefined || scope.viewport === undefined || e.viewport === scope.viewport),
  );
  // A state inventory accepts the page's base elements too (they are usually still there) but only demands the
  // elements registered for that very state; the base state demands only base elements.
  const accepted = candidates.filter((e) => e.state === undefined || e.state === scope.state);
  const expected = candidates.filter((e) =>
    scope.state === undefined ? e.state === undefined : e.state === scope.state,
  );
  const shown = interactiveNodes(snapshot);
  const violations: Violation[] = [];
  for (const node of shown) {
    if (node.name === null || node.name.trim() === "") {
      violations.push({ kind: "unnamed", message: `${where}: ${node.role} without an accessible name` });
    } else if (!accepted.some((e) => e.role === node.role && nameMatches(e.name, node.name))) {
      violations.push({
        kind: "unregistered",
        message: `${where}: ${node.role} "${node.name}" is not in e2e/interactions.ts`,
      });
    }
  }
  for (const entry of expected) {
    if (!shown.some((node) => node.role === entry.role && nameMatches(entry.name, node.name))) {
      violations.push({
        kind: "missing",
        message: `${where}: registered ${entry.id} (${entry.role} ${String(entry.name)}) is not on the page`,
      });
    }
  }
  return violations;
}

// ------------------------------------------------------------------------------------------- coverage
export interface Recorded {
  readonly id: string;
  readonly kind: string;
}

export interface CoverageReport {
  readonly missing: readonly string[];
  readonly wrongOutcome: readonly string[];
  readonly unknown: readonly string[];
}

/** Ids a full run must have exercised: every interaction, and `popup:<id>` for every popup. */
export function requiredIds(interactions: readonly Interaction[], popups: readonly Popup[]): string[] {
  return [...interactions.map((i) => i.id), ...popups.map((p) => `popup:${p.id}`)];
}

export function compareCoverage(
  recorded: readonly Recorded[],
  interactions: readonly Interaction[],
  popups: readonly Popup[],
): CoverageReport {
  const outcomeOf = new Map<string, string>([
    ...interactions.map((i) => [i.id, i.outcome] as const),
    ...popups.map((p) => [`popup:${p.id}`, "dialog"] as const),
  ]);
  const seen = new Set(recorded.filter((r) => outcomeOf.get(r.id) === r.kind).map((r) => r.id));
  return {
    missing: requiredIds(interactions, popups).filter((id) => !seen.has(id)),
    wrongOutcome: recorded
      .filter((r) => outcomeOf.has(r.id) && outcomeOf.get(r.id) !== r.kind)
      .map((r) => `${r.id}: asserted ${r.kind}, registry says ${outcomeOf.get(r.id)}`),
    unknown: [...new Set(recorded.filter((r) => !outcomeOf.has(r.id)).map((r) => r.id))],
  };
}

export function coverageFailed(report: CoverageReport): boolean {
  return report.missing.length > 0 || report.wrongOutcome.length > 0 || report.unknown.length > 0;
}
