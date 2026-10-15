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

const KNOWN: Readonly<Record<string, WarningCopy>> = {
  vision_unavailable: {
    material: true,
    title: "Nie oceniliśmy zdjęć",
    check:
      "Obejrzyj zdjęcia i rzut samodzielnie i oceń stan; koszt remontu poniżej jest założeniem, nie oceną.",
  },
  capex_prices_are_placeholders: {
    material: true,
    title: "Koszt remontu jest wstępny",
    check: "Zbierz wycenę remontu od wykonawcy. Ceny w raporcie to tymczasowe wartości, nie rynkowy cennik.",
  },
  admin_fee_missing: {
    material: true,
    title: "Brak czynszu administracyjnego",
    check:
      "Zapytaj sprzedającego o miesięczny czynsz administracyjny: to stały koszt właściciela i wpływa na wynik.",
  },
  rent_refused_too_few_comparables: {
    material: true,
    title: "Za mało podobnych ofert do wyceny czynszu",
    check: "Sprawdź czynsze podobnych mieszkań w okolicy; raport nie ma wystarczającej próby.",
  },
  rent_thin_market: {
    material: true,
    title: "Mało podobnych ofert wynajmu",
    check: "Potraktuj czynsz jako przybliżony i porównaj go z aktualnymi ofertami w okolicy.",
  },
  size_window_widened: {
    material: false,
    title: "Porównano mieszkania o bardziej różnym metrażu",
    check: "Sprawdź, czy porównywane mieszkania są naprawdę podobne wielkością.",
  },
  comparables_dropped_implausible: {
    material: false,
    title: "Odrzuciliśmy nieprawdopodobne oferty wynajmu",
    check: "Nic do zrobienia; część ofert miała ceny, które odbiegały od rynku.",
  },
  irr_not_computable: {
    material: true,
    title: "Nie da się obliczyć stopy zwrotu",
    check: "Wynik nie ma sensu rachunkowego dla tych założeń; nie opieraj decyzji na stopie zwrotu.",
  },
  legal_class_needs_review: {
    material: true,
    title: "Rodzaj lokalu lub rozliczenie VAT wymaga sprawdzenia",
    check: "Zapytaj w księdze wieczystej i u sprzedającego, czy to lokal mieszkalny i czy cena zawiera VAT.",
  },
  city_missing: {
    material: true,
    title: "Brak miasta w ogłoszeniu",
    check: "Ustal dokładną lokalizację; porównania czynszów zależą od miasta.",
  },
  street_missing: {
    material: false,
    title: "Brak ulicy w ogłoszeniu",
    check: "Ustal dokładny adres przed oglądaniem.",
  },
  coordinates_missing: {
    material: false,
    title: "Brak współrzędnych ogłoszenia",
    check: "Sprawdź lokalizację na mapie.",
  },
  coordinates_invalid: {
    material: false,
    title: "Współrzędne ogłoszenia są niepoprawne",
    check: "Sprawdź lokalizację na mapie.",
  },
  coordinates_outside_poland: {
    material: false,
    title: "Współrzędne ogłoszenia są poza Polską",
    check: "Sprawdź lokalizację i adres w ogłoszeniu.",
  },
  building_type_missing: {
    material: false,
    title: "Brak rodzaju budynku",
    check: "Zapytaj o rodzaj budynku i jego stan techniczny.",
  },
  heating_missing: {
    material: false,
    title: "Brak informacji o ogrzewaniu",
    check: "Zapytaj o rodzaj ogrzewania i koszty miesięczne.",
  },
  windows_missing: {
    material: false,
    title: "Brak informacji o oknach",
    check: "Sprawdź stan okien podczas oglądania.",
  },
};

export function warningCopy(code: string): WarningCopy {
  return (
    KNOWN[code] ?? {
      material: false,
      title: "Dodatkowe zastrzeżenie silnika",
      check: `Skontaktuj się z pomocą, jeśli to ważne (kod: ${code}).`,
    }
  );
}

/** Unique codes, material first, otherwise in the order the engine reported them. */
export function orderedWarnings(codes: readonly string[]): readonly { code: string; copy: WarningCopy }[] {
  const unique = [...new Set(codes)].map((code) => ({ code, copy: warningCopy(code) }));
  return [...unique.filter((w) => w.copy.material), ...unique.filter((w) => !w.copy.material)];
}
