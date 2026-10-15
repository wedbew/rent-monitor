import type { DealAnalysis } from "../../../api/report";

/**
 * Words for the engine's closed vocabularies. Each map is exhaustive over the generated type, so a value the
 * engine adds is a compile error here, not a blank on the page.
 */
type Valuation = DealAnalysis["valuation"];

export const VERDICT: Readonly<Record<Valuation["verdict"], { title: string; body: string }>> = {
  buy_at_asking: {
    title: "Cena ofertowa mieści się w progu zwrotu",
    body: "Przy cenie z ogłoszenia inwestycja spełnia próg zwrotu przyjęty w obliczeniach.",
  },
  negotiate: {
    title: "Warto negocjować cenę",
    body: "Przy cenie z ogłoszenia inwestycja nie spełnia progu zwrotu, ale przy niższej cenie by go spełniła.",
  },
  pass: {
    title: "Przy tej cenie inwestycja nie spełnia progu zwrotu",
    body: "Nawet po negocjacjach wynik wymaga bardzo dużej obniżki ceny lub innych założeń.",
  },
  insufficient_data: {
    title: "Za mało danych na wniosek",
    body: "Brakuje danych potrzebnych do oceny ceny. Poniżej widać, czego brakuje.",
  },
};

export const GRADE: Readonly<Record<Valuation["grade"], string>> = {
  A: "A",
  B: "B",
  C: "C",
  D: "D",
  E: "E",
  N: "bez oceny",
};

export const CONFIDENCE: Readonly<Record<DealAnalysis["confidence"], string>> = {
  high: "wysoka",
  medium: "średnia",
  low: "niska",
};

export const CONDITION: Readonly<Record<DealAnalysis["capex"]["condition_used"], string>> = {
  good: "dobry",
  refresh: "do odświeżenia",
  renovation: "do remontu",
  shell: "stan deweloperski lub surowy",
  unknown: "nieznany",
};

export const TIER: Readonly<Record<DealAnalysis["capex"]["tier"], string>> = {
  metro: "metropolia",
  major: "duże miasto",
  other: "pozostałe miasta",
};

export const TITLE_FORM: Readonly<Record<DealAnalysis["ownership"]["title_form"], string>> = {
  full_ownership: "pełna własność",
  cooperative_ownership: "spółdzielcze własnościowe prawo do lokalu",
  cooperative_tenancy: "spółdzielcze lokatorskie prawo do lokalu",
  unknown: "nieustalona",
};

export const LEGAL_CLASS: Readonly<Record<DealAnalysis["legal"]["legal_class"], string>> = {
  residential: "lokal mieszkalny",
  vat_sale: "sprzedaż z VAT",
  non_residential: "lokal niemieszkalny",
};

export const PRICE_BASIS: Readonly<Record<DealAnalysis["legal"]["price_basis"], string>> = {
  gross: "cena brutto",
  net_plus_vat: "cena netto plus VAT",
  unknown: "nie wiadomo, czy cena zawiera VAT",
};

export const RENT_BASIS: Readonly<Record<DealAnalysis["rent"]["basis"], string>> = {
  asking: "ceny ofertowe z ogłoszeń, nie umowy najmu",
  achieved: "zawarte umowy najmu",
};
