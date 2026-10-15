import type { DealAnalysis } from "../../../api/report";
import { t } from "../../../i18n";

/**
 * Words for the engine's closed vocabularies. Each map is exhaustive over the generated type, so a value the
 * engine adds is a compile error here, not a blank on the page.
 */
type Valuation = DealAnalysis["valuation"];

export const VERDICT: Readonly<Record<Valuation["verdict"], { title: string; body: string }>> =
  t.analyses.report.vocab.verdict;

export const GRADE: Readonly<Record<Valuation["grade"], string>> = t.analyses.report.vocab.grade;

export const CONFIDENCE: Readonly<Record<DealAnalysis["confidence"], string>> =
  t.analyses.report.vocab.confidence;

export const CONDITION: Readonly<Record<DealAnalysis["capex"]["condition_used"], string>> =
  t.analyses.report.vocab.condition;

export const TIER: Readonly<Record<DealAnalysis["capex"]["tier"], string>> = t.analyses.report.vocab.tier;

export const TITLE_FORM: Readonly<Record<DealAnalysis["ownership"]["title_form"], string>> =
  t.analyses.report.vocab.titleForm;

export const LEGAL_CLASS: Readonly<Record<DealAnalysis["legal"]["legal_class"], string>> =
  t.analyses.report.vocab.legalClass;

export const PRICE_BASIS: Readonly<Record<DealAnalysis["legal"]["price_basis"], string>> =
  t.analyses.report.vocab.priceBasis;

export const RENT_BASIS: Readonly<Record<DealAnalysis["rent"]["basis"], string>> =
  t.analyses.report.vocab.rentBasis;
