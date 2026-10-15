/**
 * The one place numbers become text (guide section 7, rules/frontend.md section 7). Two jobs, kept apart:
 *
 * - **Digits** are exact. The API sends money, areas and ratios as decimal strings; they are rounded here by integer
 *   arithmetic on the digits (half away from zero), never through `Number`, `parseFloat` or a binary float.
 * - **Layout** comes from `Intl` for the locale: grouping and decimal separators, where the currency, percent sign
 *   and minus go, the currency symbol, plural categories, dates. `formatToParts` gives that layout; the exact
 *   digits are put into it. (Passing the decimal string to `Intl` directly is exact only where the browser
 *   implements Intl.NumberFormat v3; this way is exact everywhere.)
 *
 * House policy on top of the locale, stated once: grouping always (also 4-digit numbers), a real minus sign (U+2212),
 * never a negative zero, `m²` as the area label (ECMA-402 has no square-metre unit). Unknown is not zero: `null`
 * or an unreadable value is "nie obliczono" and never gets a unit. Dates are shown in Europe/Warsaw.
 */

import { type PluralForms, t } from "../i18n";

export const NOT_COMPUTED = t.format.notComputed;
const NBSP = "\u00a0";
const MINUS = "\u2212";
const DECIMAL_RE = /^(-?)(\d+)(?:\.(\d+))?$/;
/** Longest input accepted: far beyond any real price, short enough that BigInt work stays trivial. */
const MAX_INPUT = 64;
/** Fraction digits any formatter may be asked for. */
const MAX_PLACES = 6;

interface Parsed {
  readonly negative: boolean;
  /** all digits, no separator: value = digits / 10 ** scale */
  readonly digits: bigint;
  readonly scale: number;
}

function parse(value: string): Parsed | null {
  if (value.length > MAX_INPUT) return null;
  const match = DECIMAL_RE.exec(value.trim());
  if (match === null) return null;
  const [, sign = "", whole = "", fraction = ""] = match;
  return { negative: sign === "-", digits: BigInt(whole + fraction), scale: fraction.length };
}

/** A precision argument the formatters accept: an integer 0..6; anything else falls back to `fallback`. */
function places(requested: number, fallback: number): number {
  return Number.isInteger(requested) && requested >= 0 && requested <= MAX_PLACES ? requested : fallback;
}

/** Round half away from zero to `places` decimals; returns the scaled integer (value * 10 ** places). */
function scaledTo(parsed: Parsed, decimals: number): bigint {
  const diff = decimals - parsed.scale;
  if (diff >= 0) return parsed.digits * 10n ** BigInt(diff);
  const divisor = 10n ** BigInt(-diff);
  const quotient = parsed.digits / divisor;
  return (parsed.digits % divisor) * 2n >= divisor ? quotient + 1n : quotient;
}

type Style = "decimal" | "currency" | "percent";

/** All number and plural formatting for one locale. The app uses `pl-PL`; tests also build another one. */
export function createNumberFormat(locale: string) {
  const integers = new Intl.NumberFormat(locale, { useGrouping: "always", maximumFractionDigits: 0 });
  const layouts = new Map<string, Intl.NumberFormatPart[]>();
  const pluralRules = new Intl.PluralRules(locale);

  /** The locale's layout for this style, sign and number of decimals (cached), from a stand-in value. */
  function layout(style: Style, negative: boolean, decimals: number): Intl.NumberFormatPart[] {
    const key = `${style}:${negative ? "-" : "+"}:${decimals}`;
    let parts = layouts.get(key);
    if (parts === undefined) {
      const format = new Intl.NumberFormat(locale, {
        style,
        ...(style === "currency" ? { currency: "PLN" } : {}),
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
        useGrouping: "always",
      });
      // A stand-in of the right sign; percent style multiplies by 100, so 0.01 shows as "1".
      const standIn = (style === "percent" ? 0.01 : 1) * (negative ? -1 : 1);
      parts = format.formatToParts(standIn);
      layouts.set(key, parts);
    }
    return parts;
  }

  /** The exact `scaled / 10 ** decimals` in the locale's layout for `style`. */
  function compose(style: Style, negative: boolean, scaled: bigint, decimals: number): string {
    const unit = 10n ** BigInt(decimals);
    const showMinus = negative && scaled !== 0n; // never a negative zero
    const whole = integers.format(scaled / unit);
    const fraction = (scaled % unit).toString().padStart(decimals, "0");
    let out = "";
    let wroteInteger = false;
    for (const part of layout(style, showMinus, decimals)) {
      if (part.type === "minusSign") out += MINUS;
      else if (part.type === "integer" || part.type === "group") {
        if (!wroteInteger) out += whole; // the stand-in's integer (and any group) is replaced once
        wroteInteger = true;
      } else if (part.type === "fraction") out += fraction;
      else out += part.value; // decimal separator, currency, percent sign, spacing: the locale's
    }
    return out;
  }

  /** `count` in the locale's plural category, choosing one of `[one, few, many]` (and `other` for fractions). */
  function plural(
    count: number,
    forms: readonly [one: string, few: string, many: string, other?: string],
  ): string {
    const category = pluralRules.select(Math.abs(count));
    if (category === "one") return forms[0];
    if (category === "few") return forms[1];
    if (category === "other" && forms[3] !== undefined) return forms[3];
    return forms[2];
  }

  /** An integer count, grouped like every other number; a non-integer or non-finite count is not a count. */
  function formatCount(count: number): string {
    return Number.isSafeInteger(count) ? integers.format(count) : NOT_COMPUTED;
  }

  return { compose, plural, formatCount };
}

const pl = createNumberFormat("pl-PL");
export const plural = pl.plural;
export const formatCount = pl.formatCount;

export interface MoneyOptions {
  /** 2 (default) shows grosze; 0 rounds to whole złoty for headline figures. */
  readonly decimals?: 0 | 2;
}

export function formatMoney(value: string | null | undefined, { decimals = 2 }: MoneyOptions = {}): string {
  if (value === null || value === undefined) return NOT_COMPUTED;
  const parsed = parse(value);
  if (parsed === null) return NOT_COMPUTED;
  const d = places(decimals, 2);
  return pl.compose("currency", parsed.negative, scaledTo(parsed, d), d);
}

/** A ratio such as "0.0734" (7.34 %); `digits` is 0..6, default 1. */
export function formatRatio(value: string | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return NOT_COMPUTED;
  const parsed = parse(value);
  if (parsed === null) return NOT_COMPUTED;
  const d = places(digits, 1);
  // ×100 exactly by moving the decimal point two places, then the locale's percent layout.
  const shifted: Parsed =
    parsed.scale >= 2
      ? { ...parsed, scale: parsed.scale - 2 }
      : { ...parsed, digits: parsed.digits * 10n ** BigInt(2 - parsed.scale), scale: 0 };
  // The percent layout's stand-in is 0.01 → "1 %": the shifted value already is the number of percent.
  return pl.compose("percent", parsed.negative, scaledTo(shifted, d), d);
}

/** A plain decimal (area, rooms): at most `maxDecimals` (0..6, default 2), trailing zeros dropped. */
export function formatDecimal(value: string | null | undefined, maxDecimals = 2): string {
  if (value === null || value === undefined) return NOT_COMPUTED;
  const parsed = parse(value);
  if (parsed === null) return NOT_COMPUTED;
  let d = Math.min(parsed.scale, places(maxDecimals, 2));
  let scaled = scaledTo(parsed, d);
  while (d > 0 && scaled % 10n === 0n) {
    scaled /= 10n; // trailing zeros carry no information: 62.0 is 62
    d -= 1;
  }
  return pl.compose("decimal", parsed.negative, scaled, d);
}

/** An area with the `m²` label; an unknown or unreadable value is "nie obliczono", never "nie obliczono m²". */
export function formatArea(value: string | null | undefined): string {
  const text = formatDecimal(value, 2);
  return text === NOT_COMPUTED ? NOT_COMPUTED : `${text}${NBSP}${t.format.areaUnit}`;
}

/** A whole percentage already on the 0..100 scale (progress): the locale's percent layout, never `${n}%`. */
export function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return NOT_COMPUTED;
  return pl.compose("percent", value < 0, BigInt(Math.round(Math.abs(value))), 0);
}

const dateFormat = new Intl.DateTimeFormat("pl-PL", {
  timeZone: "Europe/Warsaw",
  day: "numeric",
  month: "long",
  year: "numeric",
});
const dateTimeFormat = new Intl.DateTimeFormat("pl-PL", {
  timeZone: "Europe/Warsaw",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function toDate(iso: string | null | undefined): Date | null {
  if (iso === null || iso === undefined) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(iso: string | null | undefined): string {
  const date = toDate(iso);
  return date === null ? t.format.noDate : dateFormat.format(date);
}

export function formatDateTime(iso: string | null | undefined): string {
  const date = toDate(iso);
  return date === null ? t.format.noDate : dateTimeFormat.format(date);
}

/** "5 raportów", "1 234 raporty", "3 sekundy": the count grouped, the noun in its plural form. */
export function formatCounted(count: number, forms: PluralForms): string {
  const text = formatCount(count);
  return text === NOT_COMPUTED ? NOT_COMPUTED : `${text}${NBSP}${plural(count, forms)}`;
}

export function formatReports(count: number): string {
  return formatCounted(count, t.format.nouns.reports);
}

export function formatAnalyses(count: number): string {
  return formatCounted(count, t.format.nouns.analyses);
}
