/**
 * The one place numbers become text (guide section 7). The API sends money, areas and ratios as decimal strings so
 * nothing is rounded in transit; they are formatted here by integer arithmetic on the digits, never through
 * `Number`, `parseFloat` or a binary float (ESLint bans both on `*_pln` fields). Unknown is not zero: `null` is
 * "nie obliczono". Dates are shown in Europe/Warsaw, numbers in pl-PL.
 */

export const NOT_COMPUTED = "nie obliczono";
const NBSP = " ";
const MINUS = "−";
const DECIMAL_RE = /^(-?)(\d+)(?:\.(\d+))?$/;

interface Parsed {
  readonly negative: boolean;
  /** all digits, no separator: value = digits / 10 ** scale */
  readonly digits: bigint;
  readonly scale: number;
}

function parse(value: string): Parsed | null {
  const match = DECIMAL_RE.exec(value.trim());
  if (match === null) return null;
  const [, sign = "", whole = "", fraction = ""] = match;
  return { negative: sign === "-", digits: BigInt(whole + fraction), scale: fraction.length };
}

/** Round half away from zero to `places` decimals; returns the scaled integer (value * 10 ** places). */
function scaledTo(parsed: Parsed, places: number): bigint {
  const diff = places - parsed.scale;
  if (diff >= 0) return parsed.digits * 10n ** BigInt(diff);
  const divisor = 10n ** BigInt(-diff);
  const quotient = parsed.digits / divisor;
  return (parsed.digits % divisor) * 2n >= divisor ? quotient + 1n : quotient;
}

const grouping = new Intl.NumberFormat("pl-PL", { useGrouping: "always", maximumFractionDigits: 0 });

function compose(negative: boolean, scaled: bigint, places: number): string {
  const unit = 10n ** BigInt(places);
  const whole = grouping.format(scaled / unit);
  const fraction = places === 0 ? "" : `,${(scaled % unit).toString().padStart(places, "0")}`;
  const sign = negative && scaled !== 0n ? MINUS : "";
  return `${sign}${whole}${fraction}`;
}

export interface MoneyOptions {
  /** 2 (default) shows grosze; 0 rounds to whole złoty for headline figures. */
  readonly decimals?: 0 | 2;
}

export function formatMoney(value: string | null | undefined, { decimals = 2 }: MoneyOptions = {}): string {
  if (value === null || value === undefined) return NOT_COMPUTED;
  const parsed = parse(value);
  if (parsed === null) return NOT_COMPUTED;
  return `${compose(parsed.negative, scaledTo(parsed, decimals), decimals)}${NBSP}zł`;
}

/** A ratio such as "0.0734" (7.34 %). */
export function formatRatio(value: string | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return NOT_COMPUTED;
  const parsed = parse(value);
  if (parsed === null) return NOT_COMPUTED;
  const shifted: Parsed =
    parsed.scale >= 2
      ? { ...parsed, scale: parsed.scale - 2 }
      : { ...parsed, digits: parsed.digits * 10n ** BigInt(2 - parsed.scale), scale: 0 };
  return `${compose(parsed.negative, scaledTo(shifted, digits), digits)}%`;
}

/** A plain decimal (area, rooms): at most `maxDecimals`, trailing zeros dropped. */
export function formatDecimal(value: string | null | undefined, maxDecimals = 2): string {
  if (value === null || value === undefined) return NOT_COMPUTED;
  const parsed = parse(value);
  if (parsed === null) return NOT_COMPUTED;
  const places = Math.min(parsed.scale, maxDecimals);
  const text = compose(parsed.negative, scaledTo(parsed, places), places);
  return text.includes(",") ? text.replace(/,?0+$/, "") : text;
}

export function formatArea(value: string | null | undefined): string {
  return value === null || value === undefined ? NOT_COMPUTED : `${formatDecimal(value, 2)}${NBSP}m²`;
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
  return date === null ? "—" : dateFormat.format(date);
}

export function formatDateTime(iso: string | null | undefined): string {
  const date = toDate(iso);
  return date === null ? "—" : dateTimeFormat.format(date);
}

/** Polish plural: 1 raport, 2-4 raporty (not 12-14), otherwise raportów. */
export function plural(count: number, forms: readonly [one: string, few: string, many: string]): string {
  const abs = Math.abs(count);
  if (abs === 1) return forms[0];
  const lastTwo = abs % 100;
  const last = abs % 10;
  return last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14) ? forms[1] : forms[2];
}

export function formatReports(count: number): string {
  return `${count}${NBSP}${plural(count, ["raport", "raporty", "raportów"])}`;
}

export function formatAnalyses(count: number): string {
  return `${count}${NBSP}${plural(count, ["analiza", "analizy", "analiz"])}`;
}
