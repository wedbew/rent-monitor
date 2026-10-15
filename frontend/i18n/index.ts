/**
 * The copy of the app (audit F06, #305, rules/frontend.md section 7). Components read `t.<area>.<key>`; nothing
 * user-visible is written as a literal in a component (ESLint, eslint.copy.mjs). A message with values is a
 * function of named, already formatted strings: `t.dashboard.greeting({ name })`. Counts and money are formatted
 * by api/format.ts and passed in; plural forms are catalog entries that api/format.ts selects with Intl.PluralRules.
 *
 * Only Polish exists. `Catalog` is the shape a second language would have to fill completely: a missing key or a
 * message with different parameters is a type error, not a runtime blank.
 */
import { pl } from "./pl";

type Widen<T> = T extends string
  ? string
  : T extends (...args: infer A) => infer R
    ? (...args: A) => R
    : { readonly [K in keyof T]: Widen<T[K]> }; // tuples (plural forms) stay tuples

export type Catalog = Widen<typeof pl>;

export const t: Catalog = pl;

/** Plural forms: one, few, many (and `other` for fractions, Polish "1,5 raportu"). */
export type PluralForms = readonly [one: string, few: string, many: string];
