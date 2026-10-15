import type { ReactNode } from "react";

import {
  formatArea,
  formatDate,
  formatDecimal,
  formatMoney,
  formatRatio,
  NOT_COMPUTED,
  plural,
} from "../../../api/format";
import type { DealAnalysis } from "../../../api/report";
import { DisclosureGroup } from "../../../ui/Accordion";
import { Icon } from "../../../ui/Icon";
import { InlineNotice } from "../../../ui/Status";
import {
  CONDITION,
  CONFIDENCE,
  GRADE,
  LEGAL_CLASS,
  PRICE_BASIS,
  RENT_BASIS,
  TIER,
  TITLE_FORM,
  VERDICT,
} from "./copy";
import { orderedWarnings } from "./warnings";
import styles from "./ReportView.module.css";

/** A money value exactly as the engine reported it. Unknown is said in words; a real zero stays "0,00 zł". */
function Money({ value, decimals = 0 }: { readonly value: string | null; readonly decimals?: 0 | 2 }) {
  if (value === null) return <span className={styles["unknown"]}>{NOT_COMPUTED}</span>;
  return <span className={styles["value"]}>{formatMoney(value, { decimals })}</span>;
}

function Row({
  label,
  children,
  total = false,
}: {
  readonly label: string;
  readonly children: ReactNode;
  readonly total?: boolean;
}) {
  return (
    <div className={`${styles["row"]} ${total ? styles["total"] : ""}`}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

const money2 = (value: string | null) => formatMoney(value, { decimals: 2 });
const text = (value: string | number | null | undefined) =>
  value === null || value === undefined || value === "" ? "brak w ogłoszeniu" : String(value);

export const SECTIONS = [
  { id: "podsumowanie", label: "Podsumowanie" },
  { id: "czynsz", label: "Czynsz" },
  { id: "koszty", label: "Koszty i stan" },
  { id: "cena", label: "Cena zakupu" },
  { id: "sprawdz", label: "Co sprawdzić" },
  { id: "zrodla", label: "Źródła" },
] as const;

function jumpTo(id: string) {
  const heading = document.getElementById(`sekcja-${id}`);
  if (heading === null) return;
  heading.scrollIntoView({ block: "start" });
  heading.focus();
}

function SectionNav() {
  return (
    <nav className={styles["nav"]} aria-label="Sekcje raportu">
      {SECTIONS.map((section) => (
        <a
          key={section.id}
          href={`#sekcja-${section.id}`}
          onClick={(event) => {
            event.preventDefault();
            jumpTo(section.id);
          }}
        >
          {section.label}
        </a>
      ))}
    </nav>
  );
}

function Section({
  id,
  title,
  children,
}: {
  readonly id: string;
  readonly title: string;
  readonly children: ReactNode;
}) {
  return (
    <section className={styles["section"]} aria-labelledby={`sekcja-${id}`}>
      <h2 id={`sekcja-${id}`} tabIndex={-1}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Figure({
  label,
  value,
  hint,
  decimals = 0,
}: {
  readonly label: string;
  readonly value: string | null;
  readonly hint?: string | undefined;
  readonly decimals?: 0 | 2;
}) {
  return (
    <div className={styles["figure"]}>
      <dt>{label}</dt>
      <dd>
        <Money value={value} decimals={decimals} />
        {hint ? <span className={styles["hint"]}>{hint}</span> : null}
      </dd>
    </div>
  );
}

function Overview({ report, degraded }: { readonly report: DealAnalysis; readonly degraded: boolean }) {
  const { listing, valuation, cash_flow: cash } = report;
  const verdict = VERDICT[valuation.verdict];
  const material = orderedWarnings([...report.warnings, ...listing.warnings]).filter((w) => w.copy.material);
  const where = [listing.street, listing.city].filter(Boolean).join(", ");
  const facts = [
    formatArea(listing.area_m2),
    `${listing.rooms} ${plural(listing.rooms, ["pokój", "pokoje", "pokoi"])}`,
    listing.floor !== null
      ? `piętro ${listing.floor}${listing.building_floors !== null ? ` z ${listing.building_floors}` : ""}`
      : null,
    listing.build_year !== null ? `rok budowy ${listing.build_year}` : null,
  ].filter(Boolean);
  return (
    <Section id="podsumowanie" title="Podsumowanie">
      <div className={styles["identity"]}>
        <h3>{listing.title}</h3>
        <p className={styles["muted"]}>{[where, facts.join(" · ")].filter(Boolean).join(" · ")}</p>
        <p className={styles["muted"]}>
          Ogłoszenie {listing.otodom_id}
          {listing.modified_at !== null ? `, zaktualizowane ${formatDate(listing.modified_at)}` : ""}
        </p>
        {listing.url !== null ? (
          <a className={styles["external"]} href={listing.url} target="_blank" rel="noopener noreferrer">
            Zobacz ogłoszenie na Otodom
            <Icon name="arrow" />
          </a>
        ) : null}
      </div>

      <div className={styles["conclusion"]}>
        <h3>{verdict.title}</h3>
        <p>{verdict.body}</p>
        <p className={styles["grade"]}>
          Ocena silnika: <strong>{GRADE[valuation.grade]}</strong>
          <span>· pewność wyniku: {CONFIDENCE[report.confidence]}</span>
        </p>
        {degraded ? (
          <p className={styles["muted"]}>
            Analiza jest gotowa, ale nie wszystkie dane były dostępne: wniosek jest mniej pewny.
          </p>
        ) : null}
      </div>

      <dl className={styles["figures"]}>
        <Figure
          label="Wynik właściciela w roku 1"
          value={cash.years[0]?.net_cash_flow_pln ?? null}
          hint="po kosztach właściciela i podatku dochodowym"
        />
        <Figure
          label="Kapitał na start"
          value={cash.total_invested_pln}
          hint="cena ofertowa, koszty zakupu i remont"
        />
        <Figure
          label="Cena spełniająca próg zwrotu"
          value={valuation.max_bid_pln}
          hint={
            valuation.max_bid_pln === null
              ? "żadna cena nie spełnia progu przy tych założeniach"
              : `próg zwrotu ${formatRatio(valuation.hurdle)} rocznie`
          }
        />
      </dl>

      {material.length > 0 ? (
        <div className={styles["notices"]}>
          {material.map(({ code, copy }) => (
            <InlineNotice key={code} tone="warning" title={copy.title} />
          ))}
        </div>
      ) : null}
    </Section>
  );
}

function RentSection({ report }: { readonly report: DealAnalysis }) {
  const { rent } = report;
  return (
    <Section id="czynsz" title="Czynsz">
      <dl className={styles["figures"]}>
        <Figure
          label="Szacowany czynsz miesięcznie"
          value={rent.monthly_used_pln}
          hint={`na podstawie: ${RENT_BASIS[rent.basis]}`}
          decimals={0}
        />
        <div className={styles["figure"]}>
          <dt>Podobne oferty</dt>
          <dd>
            <span className={styles["value"]}>{rent.comparables}</span>
            <span className={styles["hint"]}>
              {plural(rent.comparables, ["oferta", "oferty", "ofert"])} wynajmu · pewność{" "}
              {CONFIDENCE[rent.confidence]}
            </span>
          </dd>
        </div>
        <div className={styles["figure"]}>
          <dt>Czynsz administracyjny</dt>
          <dd>
            <Money value={report.listing.admin_fee_pln} />
            <span className={styles["hint"]}>miesięcznie · koszt właściciela, nie przychód z najmu</span>
          </dd>
        </div>
      </dl>
      <DisclosureGroup
        items={[
          {
            value: "rent-how",
            title: "Jak policzyliśmy czynsz",
            children: (
              <dl className={styles["rows"]}>
                <Row label="Czynsz z porównań">{money2(rent.input_monthly_pln)}</Row>
                <Row label="Ostrożnościowa obniżka">{formatRatio(rent.haircut)}</Row>
                <Row label="Czynsz po obniżce">{money2(rent.monthly_after_haircut_pln)}</Row>
                <Row label="Czynsz użyty w obliczeniach" total>
                  {money2(rent.monthly_used_pln)}
                </Row>
              </dl>
            ),
          },
        ]}
      />
    </Section>
  );
}

function CostsSection({ report }: { readonly report: DealAnalysis }) {
  const { capex, cash_flow: cash } = report;
  const year1 = cash.years[0];
  const purchase = cash.purchase;
  return (
    <Section id="koszty" title="Koszty i stan">
      {capex.prices_are_placeholders ? (
        <InlineNotice tone="warning" title="Koszt remontu jest wstępny">
          Ceny remontu w tym raporcie to tymczasowe wartości, a nie rynkowy cennik. Zbierz wycenę od
          wykonawcy.
        </InlineNotice>
      ) : null}
      <dl className={styles["rows"]}>
        <Row label="Cena ofertowa">{money2(purchase.price_pln)}</Row>
        <Row label="Koszty zakupu">{money2(purchase.total_costs_pln)}</Row>
        <Row label="Remont (szacunek)">
          {money2(report.capex_used_pln)}{" "}
          {capex.prices_are_placeholders ? <span className={styles["prelim"]}>wstępny</span> : null}
        </Row>
        <Row label="Razem na start" total>
          {money2(cash.total_invested_pln)}
        </Row>
      </dl>
      <DisclosureGroup
        items={[
          {
            value: "purchase",
            title: "Koszty zakupu: szczegóły",
            children: (
              <dl className={styles["rows"]}>
                <Row label="Podatek od czynności cywilnoprawnych">{money2(purchase.pcc_pln)}</Row>
                <Row label="Taksa notarialna">{money2(purchase.notary_pln)}</Row>
                <Row label="Opłaty sądowe">{money2(purchase.court_fee_pln)}</Row>
                <Row label="Wypisy aktu">{money2(purchase.deed_copies_pln)}</Row>
                <Row label="Pośrednik">{money2(purchase.broker_pln)}</Row>
                <Row label="Razem koszty zakupu" total>
                  {money2(purchase.total_costs_pln)}
                </Row>
              </dl>
            ),
          },
          {
            value: "owner-costs",
            title: "Koszty właściciela w roku 1",
            children:
              year1 === undefined ? (
                <p className={styles["muted"]}>{NOT_COMPUTED}</p>
              ) : (
                <dl className={styles["rows"]}>
                  <Row label="Czynsz administracyjny">{money2(year1.costs.admin_fee_pln)}</Row>
                  <Row label="Ubezpieczenie">{money2(year1.costs.insurance_pln)}</Row>
                  <Row label="Remonty i utrzymanie">{money2(year1.costs.maintenance_pln)}</Row>
                  <Row label="Zarządzanie">{money2(year1.costs.management_pln)}</Row>
                  <Row label="Podatek od nieruchomości">{money2(year1.costs.property_tax_pln)}</Row>
                  <Row label="Razem koszty rocznie" total>
                    {money2(year1.costs.total_pln)}
                  </Row>
                </dl>
              ),
          },
          {
            value: "capex",
            title: "Remont: szacunek i założenia",
            children: (
              <dl className={styles["rows"]}>
                <Row label="Stan mieszkania">
                  {CONDITION[capex.condition_used]}
                  {capex.condition_assumed ? " (założony: bez oceny zdjęć)" : ""}
                </Row>
                <Row label="Rodzaj miasta">{TIER[capex.tier]}</Row>
                <Row label="Cena za metr kwadratowy">{money2(capex.pln_per_m2)}</Row>
                <Row label="Mnożnik">{formatDecimal(capex.multiplier, 2)}</Row>
                <Row label="Szacunek podstawowy">{money2(capex.base_pln)}</Row>
                <Row label="Zakres">
                  {money2(capex.low_pln)} do {money2(capex.high_pln)}
                </Row>
                <Row label="Pewność szacunku">{CONFIDENCE[capex.confidence]}</Row>
                <Row label="Wersja cennika">{capex.catalog_version}</Row>
              </dl>
            ),
          },
        ]}
      />
    </Section>
  );
}

function discountSentence(discount: string | null): string | null {
  if (discount === null) return null;
  const negative = discount.startsWith("-");
  const size = formatRatio(negative ? discount.slice(1) : discount);
  return negative ? `${size} poniżej ceny ofertowej` : `${size} powyżej ceny ofertowej`;
}

function PriceSection({ report }: { readonly report: DealAnalysis }) {
  const { valuation, cash_flow: cash } = report;
  const gap = discountSentence(valuation.discount_to_asking);
  return (
    <Section id="cena" title="Cena zakupu">
      <dl className={styles["figures"]}>
        <div className={styles["figure"]}>
          <dt>Cena progowa a ofertowa</dt>
          <dd>
            {gap === null ? (
              <span className={styles["unknown"]}>{NOT_COMPUTED}</span>
            ) : (
              <span className={styles["value"]}>{gap}</span>
            )}
            <span className={styles["hint"]}>
              {valuation.max_bid_pln === null
                ? "żadna cena nie spełnia progu przy tych założeniach"
                : `cena progowa ${formatMoney(valuation.max_bid_pln, { decimals: 0 })}`}
            </span>
          </dd>
        </div>
        <Figure
          label="Cena ofertowa"
          value={valuation.asking_price_pln}
          hint="cena z ogłoszenia, nie cena transakcyjna"
        />
        <div className={styles["figure"]}>
          <dt>Zwrot przy cenie ofertowej</dt>
          <dd>
            <span className={styles["value"]}>
              {valuation.irr_at_asking === null ? (
                <span className={styles["unknown"]}>{NOT_COMPUTED}</span>
              ) : (
                formatRatio(valuation.irr_at_asking)
              )}
            </span>
            <span className={styles["hint"]}>
              stopa zwrotu (IRR) w 10 lat, próg {formatRatio(valuation.hurdle)}
            </span>
          </dd>
        </div>
      </dl>
      {!valuation.max_bid_bounded ? (
        <InlineNotice tone="info" title="Wynik jest tylko górną granicą">
          Próg zwrotu byłby spełniony nawet przy cenie wielokrotnie wyższej od ofertowej, więc podana cena to
          górna granica obliczeń.
        </InlineNotice>
      ) : null}
      <DisclosureGroup
        items={[
          {
            value: "sensitivity",
            title: "Zwroty, wyjście i wrażliwość na wzrost cen",
            children: (
              <dl className={styles["rows"]}>
                <Row label="Rentowność brutto">{formatRatio(cash.returns.gross_yield, 2)}</Row>
                <Row label="Rentowność netto">{formatRatio(cash.returns.net_yield, 2)}</Row>
                <Row label="Stopa zwrotu IRR">{formatRatio(cash.returns.irr, 2)}</Row>
                <Row label="Średni roczny wzrost kapitału (CAGR)">{formatRatio(cash.returns.cagr, 2)}</Row>
                <Row label="Mnożnik kapitału (MOIC)">{formatDecimal(cash.returns.moic, 2)}</Row>
                <Row label="Wartość sprzedaży po 10 latach">{money2(cash.exit.exit_value_pln)}</Row>
                <Row label="Koszty sprzedaży">{money2(cash.exit.selling_costs_pln)}</Row>
                <Row label="Podatek przy sprzedaży">{money2(cash.exit.sale_tax_pln)}</Row>
                <Row label="Wpływy netto ze sprzedaży" total>
                  {money2(cash.exit.net_proceeds_pln)}
                </Row>
                <Row label="Cena progowa, gdy ceny rosną o 1 pkt proc. mniej">
                  {money2(valuation.max_bid_if_appreciation_minus_1pp_pln)}
                </Row>
                <Row label="Cena progowa, gdy ceny rosną o 1 pkt proc. więcej">
                  {money2(valuation.max_bid_if_appreciation_plus_1pp_pln)}
                </Row>
              </dl>
            ),
          },
          {
            value: "years",
            title: "Przepływy pieniężne rok po roku",
            children: (
              <div className={styles["tableWrap"]}>
                <table className={styles["table"]}>
                  <caption>Kwoty w złotych, bez kapitału na start</caption>
                  <thead>
                    <tr>
                      <th scope="col">Rok</th>
                      <th scope="col">Czynsz</th>
                      <th scope="col">Koszty</th>
                      <th scope="col">Podatek</th>
                      <th scope="col">Wynik</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cash.years.map((row) => (
                      <tr key={row.year}>
                        <th scope="row">{row.year}</th>
                        <td>{formatMoney(row.rent_collected_pln, { decimals: 0 })}</td>
                        <td>{formatMoney(row.costs.total_pln, { decimals: 0 })}</td>
                        <td>{formatMoney(row.income_tax_pln, { decimals: 0 })}</td>
                        <td>{formatMoney(row.net_cash_flow_pln, { decimals: 0 })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ),
          },
        ]}
      />
    </Section>
  );
}

function CheckSection({ report }: { readonly report: DealAnalysis }) {
  const warnings = orderedWarnings([...report.warnings, ...report.listing.warnings]);
  const extra: { title: string; check: string }[] = [];
  if (report.ownership.title_form === "unknown")
    extra.push({
      title: "Forma własności nie jest ustalona",
      check: "Sprawdź w księdze wieczystej, jakie prawo przysługuje sprzedającemu.",
    });
  if (report.legal.price_basis === "unknown")
    extra.push({
      title: "Nie wiadomo, czy cena zawiera VAT",
      check: "Zapytaj sprzedającego, czy cena jest ceną brutto.",
    });
  return (
    <Section id="sprawdz" title="Co sprawdzić przed ofertą">
      {warnings.length === 0 && extra.length === 0 ? (
        <p className={styles["muted"]}>
          Silnik nie zgłosił zastrzeżeń. To nie zastępuje oględzin i księgi wieczystej.
        </p>
      ) : (
        <ul className={styles["checklist"]}>
          {warnings.map(({ code, copy }) => (
            <li key={code} data-material={copy.material}>
              <strong>{copy.title}</strong>
              <span>{copy.check}</span>
            </li>
          ))}
          {extra.map((item) => (
            <li key={item.title} data-material="false">
              <strong>{item.title}</strong>
              <span>{item.check}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// LEGAL[republication]: shows listing fields and excerpts of the listing text to the person who analysed it (RM-274)
function SourceSection({ report }: { readonly report: DealAnalysis }) {
  const { listing, vision, legal, ownership } = report;
  const evidence = [...legal.evidence, ...ownership.evidence];
  const items = [
    {
      value: "listing",
      title: "Dane z ogłoszenia",
      children: (
        <dl className={styles["rows"]}>
          <Row label="Numer ogłoszenia">{listing.otodom_id}</Row>
          <Row label="Miasto">{text(listing.city)}</Row>
          <Row label="Ulica">{text(listing.street)}</Row>
          <Row label="Powierzchnia">{formatArea(listing.area_m2)}</Row>
          <Row label="Liczba pokoi">{listing.rooms}</Row>
          <Row label="Piętro">{text(listing.floor)}</Row>
          <Row label="Rok budowy">{text(listing.build_year)}</Row>
          <Row label="Rodzaj budynku">{text(listing.building_type)}</Row>
          <Row label="Ogrzewanie">{text(listing.heating)}</Row>
          <Row label="Okna">{text(listing.windows)}</Row>
          <Row label="Forma własności">{TITLE_FORM[ownership.title_form]}</Row>
          <Row label="Rodzaj lokalu">{LEGAL_CLASS[legal.legal_class]}</Row>
          <Row label="Rozliczenie ceny">{PRICE_BASIS[legal.price_basis]}</Row>
          <Row label="Dodano">{formatDate(listing.created_at)}</Row>
          <Row label="Zaktualizowano">{formatDate(listing.modified_at)}</Row>
          <Row label="Zdjęcia w ogłoszeniu">{listing.photo_urls.length}</Row>
          <Row label="Rzuty w ogłoszeniu">{listing.floor_plan_urls.length}</Row>
        </dl>
      ),
    },
    {
      value: "vision",
      title: "Ocena zdjęć",
      children:
        vision === null ? (
          <p className={styles["muted"]}>Zdjęć nie oceniono, więc stan mieszkania jest założeniem.</p>
        ) : (
          <dl className={styles["rows"]}>
            <Row label="Zdjęcia w ocenie">{vision.photos_total}</Row>
            <Row label="Zdjęcia pominięte">{vision.photos_excluded}</Row>
            <Row label="Stan wg zdjęć">{CONDITION[vision.condition]}</Row>
            <Row label="Korekta czynszu">
              {vision.rent === null
                ? "brak"
                : `${formatRatio(vision.rent.applied)}${vision.rent.clamped ? " (ograniczona do 15%)" : ""}`}
            </Row>
            <Row label="Korekta kosztu remontu">
              {vision.capex === null
                ? "brak"
                : `${formatRatio(vision.capex.applied)}${vision.capex.clamped ? " (ograniczona do 15%)" : ""}`}
            </Row>
            <Row label="Model i wersja instrukcji">
              {vision.model}, {vision.prompt_version}
            </Row>
          </dl>
        ),
    },
    ...(evidence.length > 0
      ? [
          {
            value: "evidence",
            title: `Fragmenty ogłoszenia użyte w ocenie (${evidence.length})`,
            children: (
              <div>
                {evidence.map((quote, index) => (
                  <blockquote key={`${index}-${quote}`} className={styles["quote"]}>
                    {quote}
                  </blockquote>
                ))}
              </div>
            ),
          },
        ]
      : []),
  ];
  return (
    <Section id="zrodla" title="Źródła i założenia">
      <DisclosureGroup items={items} />
      <div className={styles["footer"]}>
        <span>
          Zdjęcia z ogłoszenia nie są tu wyświetlane. Wersje: silnik {report.engine_version}, założenia{" "}
          {report.assumptions_version}.
        </span>
        <span>
          Ceny ofertowe to ceny z ogłoszeń, nie ceny transakcyjne. Raport nie jest poradą inwestycyjną ani
          prawną.
        </span>
      </div>
    </Section>
  );
}

/**
 * The canonical result, in the order of the questions a buyer asks: what does this suggest, what rent, what does
 * it cost, what price, what to check. Every number is the engine's own string, formatted and never calculated; an
 * unknown value is said to be unknown and never shown as zero (docs/FRONTEND-PLAN.md, invariant 4).
 */
export function ReportView({
  report,
  degraded,
}: {
  readonly report: DealAnalysis;
  readonly degraded: boolean;
}) {
  return (
    <div className={styles["report"]}>
      <SectionNav />
      <Overview report={report} degraded={degraded} />
      <RentSection report={report} />
      <CostsSection report={report} />
      <PriceSection report={report} />
      <CheckSection report={report} />
      <SourceSection report={report} />
    </div>
  );
}
