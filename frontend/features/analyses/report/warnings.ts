import { t } from "../../../i18n";

/**
 * What an engine warning means for the person, and what to do about it. The engine's codes are stable; an unknown
 * one is still shown (generically, with its code) so that nothing the engine flagged is ever hidden.
 */
export interface WarningCopy {
  /** Material: it changes how far the result can be trusted, so it is visible before any click. */
  readonly material: boolean;
  readonly title: string;
  /** The practical next step, for the "what to verify" list. */
  readonly check: string;
}

/** Material warnings change how far the result can be trusted (behaviour, not copy; the words are in the catalog). */
const MATERIAL: Readonly<Record<string, boolean>> = {
  vision_unavailable: true,
  capex_prices_are_placeholders: true,
  admin_fee_missing: true,
  rent_refused_too_few_comparables: true,
  rent_thin_market: true,
  size_window_widened: false,
  comparables_dropped_implausible: false,
  irr_not_computable: true,
  legal_class_needs_review: true,
  city_missing: true,
  street_missing: false,
  coordinates_missing: false,
  coordinates_invalid: false,
  coordinates_outside_poland: false,
  building_type_missing: false,
  heating_missing: false,
  windows_missing: false,
};

const KNOWN: Readonly<Record<string, { readonly title: string; readonly check: string }>> =
  t.analyses.report.warnings.known;

export function warningCopy(code: string): WarningCopy {
  // Own keys only: the code is engine data and must not reach the prototype.
  const known = Object.hasOwn(KNOWN, code) ? KNOWN[code] : undefined;
  if (known !== undefined) return { ...known, material: MATERIAL[code] === true };
  return { material: false, ...t.analyses.report.warnings.unknown({ code }) };
}

/** Unique codes, material first, otherwise in the order the engine reported them. */
export function orderedWarnings(codes: readonly string[]): readonly { code: string; copy: WarningCopy }[] {
  const unique = [...new Set(codes)].map((code) => ({ code, copy: warningCopy(code) }));
  return [...unique.filter((w) => w.copy.material), ...unique.filter((w) => !w.copy.material)];
}
