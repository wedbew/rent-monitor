import { formatReports } from "../api/format";
import { t } from "../i18n";

interface Balance {
  readonly credit_balance: number;
  readonly plan: { readonly unlimited_reports?: boolean };
}

/** The server decides this (an explicit entitlement on the account); nothing here derives it from an e-mail. */
export const hasNoLimit = (me: Balance): boolean => me.plan.unlimited_reports === true;

/** What to show where a number of reports would be: "Bez limitu" for an entitled account, else the balance. */
export const balanceLabel = (me: Balance): string =>
  hasNoLimit(me) ? t.common.unlimited : formatReports(me.credit_balance);
