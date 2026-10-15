import type { ReactNode } from "react";

import {
  formatArea,
  formatCount,
  formatCounted,
  formatDate,
  formatDecimal,
  formatMoney,
  formatRatio,
  formatPercent,
  NOT_COMPUTED,
  plural,
} from "../../../api/format";
import type { DealAnalysis } from "../../../api/report";
import { t } from "../../../i18n";
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

const M = t.analyses.report.text;

/** The engine's clamp on vision adjustments (invariant 4), shown as a percentage. */
const CLAMP = formatPercent(15);

const money2 = (value: string | null) => formatMoney(value, { decimals: 2 });
const text = (value: string | number | null | undefined) =>
  value === null || value === undefined || value === "" ? M.notInListing : String(value);

export const SECTIONS = [
  { id: "podsumowanie", label: M.podsumowanie },
  { id: "czynsz", label: M.czynsz },
  { id: "koszty", label: M.kosztyStan },
  { id: "cena", label: M.cenaZakupu },
  { id: "sprawdz", label: M.coSprawdzic },
  { id: "zrodla", label: M.zrodla },
] as const;

function jumpTo(id: string) {
  const heading = document.getElementById(`sekcja-${id}`);
  if (heading === null) return;
  heading.scrollIntoView({ block: "start" });
  heading.focus();
}

function SectionNav() {
  return (
    <nav className={styles["nav"]} aria-label={M.sekcjeRaportu}>
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
    formatCounted(listing.rooms, M.rooms),
    listing.floor !== null
      ? listing.building_floors !== null
        ? M.floorOf({ floor: listing.floor, floors: formatCount(listing.building_floors) })
        : M.floor({ floor: listing.floor })
      : null,
    listing.build_year !== null ? M.builtIn({ year: String(listing.build_year) }) : null,
  ].filter(Boolean);
  return (
    <Section id="podsumowanie" title={M.podsumowanie}>
      <div className={styles["identity"]}>
        <h3>{listing.title}</h3>
        <p className={styles["muted"]}>{[where, facts.join(" · ")].filter(Boolean).join(" · ")}</p>
        <p className={styles["muted"]}>
          {listing.modified_at !== null
            ? M.listingUpdated({ id: listing.otodom_id, date: formatDate(listing.modified_at) })
            : t.common.listingTitle({ id: listing.otodom_id })}
        </p>
        {listing.url !== null ? (
          <a className={styles["external"]} href={listing.url} target="_blank" rel="noopener noreferrer">
            {M.zobaczOgloszenieOtodom}
            <Icon name="arrow" />
          </a>
        ) : null}
      </div>

      <div className={styles["conclusion"]}>
        <h3>{verdict.title}</h3>
        <p>{verdict.body}</p>
        <p className={styles["grade"]}>
          {M.engineGrade} <strong>{GRADE[valuation.grade]}</strong>
          <span>{M.resultConfidence({ confidence: CONFIDENCE[report.confidence] })}</span>
        </p>
        {degraded ? <p className={styles["muted"]}>{M.analizaJestGotowaAleWszystkie}</p> : null}
      </div>

      <dl className={styles["figures"]}>
        <Figure
          label={M.wynikWlascicielaRoku1}
          value={cash.years[0]?.net_cash_flow_pln ?? null}
          hint={M.kosztachWlascicielaPodatkuDochodowym}
        />
        <Figure
          label={M.kapitalStart}
          value={cash.total_invested_pln}
          hint={M.cenaOfertowaKosztyZakupuRemont}
        />
        <Figure
          label={M.cenaSpelniajacaProgZwrotu}
          value={valuation.max_bid_pln}
          hint={
            valuation.max_bid_pln === null
              ? M.noPriceMeetsHurdle
              : M.hurdlePerYear({ hurdle: formatRatio(valuation.hurdle) })
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
    <Section id="czynsz" title={M.czynsz}>
      <dl className={styles["figures"]}>
        <Figure
          label={M.szacowanyCzynszMiesiecznie}
          value={rent.monthly_used_pln}
          hint={M.basedOn({ basis: RENT_BASIS[rent.basis] })}
          decimals={0}
        />
        <div className={styles["figure"]}>
          <dt>{M.podobneOferty}</dt>
          <dd>
            <span className={styles["value"]}>{formatCount(rent.comparables)}</span>
            <span className={styles["hint"]}>
              {M.comparablesConfidence({
                offers: plural(rent.comparables, M.offers),
                confidence: CONFIDENCE[rent.confidence],
              })}
            </span>
          </dd>
        </div>
        <div className={styles["figure"]}>
          <dt>{M.czynszAdministracyjny}</dt>
          <dd>
            <Money value={report.listing.admin_fee_pln} />
            <span className={styles["hint"]}>{M.adminFeeHint}</span>
          </dd>
        </div>
      </dl>
      <DisclosureGroup
        items={[
          {
            value: "rent-how",
            title: M.jakPoliczylismyCzynsz,
            children: (
              <dl className={styles["rows"]}>
                <Row label={M.czynszPorownan}>{money2(rent.input_monthly_pln)}</Row>
                <Row label={M.ostroznosciowaObnizka}>{formatRatio(rent.haircut)}</Row>
                <Row label={M.czynszObnizce}>{money2(rent.monthly_after_haircut_pln)}</Row>
                <Row label={M.czynszUzytyObliczeniach} total>
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
    <Section id="koszty" title={M.kosztyStan}>
      {capex.prices_are_placeholders ? (
        <InlineNotice tone="warning" title={M.kosztRemontuJestWstepny}>
          {M.cenyRemontuTymRaporcieTo}
        </InlineNotice>
      ) : null}
      <dl className={styles["rows"]}>
        <Row label={M.cenaOfertowa}>{money2(purchase.price_pln)}</Row>
        <Row label={M.kosztyZakupu}>{money2(purchase.total_costs_pln)}</Row>
        <Row label={M.remontSzacunek}>
          {money2(report.capex_used_pln)}{" "}
          {capex.prices_are_placeholders ? <span className={styles["prelim"]}>{M.wstepny}</span> : null}
        </Row>
        <Row label={M.razemStart} total>
          {money2(cash.total_invested_pln)}
        </Row>
      </dl>
      <DisclosureGroup
        items={[
          {
            value: "purchase",
            title: M.kosztyZakupuSzczegoly,
            children: (
              <dl className={styles["rows"]}>
                <Row label={M.podatekCzynnosciCywilnoprawnych}>{money2(purchase.pcc_pln)}</Row>
                <Row label={M.taksaNotarialna}>{money2(purchase.notary_pln)}</Row>
                <Row label={M.oplatySadowe}>{money2(purchase.court_fee_pln)}</Row>
                <Row label={M.wypisyAktu}>{money2(purchase.deed_copies_pln)}</Row>
                <Row label={M.posrednik}>{money2(purchase.broker_pln)}</Row>
                <Row label={M.razemKosztyZakupu} total>
                  {money2(purchase.total_costs_pln)}
                </Row>
              </dl>
            ),
          },
          {
            value: "owner-costs",
            title: M.kosztyWlascicielaRoku1,
            children:
              year1 === undefined ? (
                <p className={styles["muted"]}>{NOT_COMPUTED}</p>
              ) : (
                <dl className={styles["rows"]}>
                  <Row label={M.czynszAdministracyjny}>{money2(year1.costs.admin_fee_pln)}</Row>
                  <Row label={M.ubezpieczenie}>{money2(year1.costs.insurance_pln)}</Row>
                  <Row label={M.remontyUtrzymanie}>{money2(year1.costs.maintenance_pln)}</Row>
                  <Row label={M.zarzadzanie}>{money2(year1.costs.management_pln)}</Row>
                  <Row label={M.podatekNieruchomosci}>{money2(year1.costs.property_tax_pln)}</Row>
                  <Row label={M.razemKosztyRocznie} total>
                    {money2(year1.costs.total_pln)}
                  </Row>
                </dl>
              ),
          },
          {
            value: "capex",
            title: M.remontSzacunekZalozenia,
            children: (
              <dl className={styles["rows"]}>
                <Row label={M.stanMieszkania}>
                  {CONDITION[capex.condition_used]}
                  {capex.condition_assumed ? M.conditionAssumed : ""}
                </Row>
                <Row label={M.rodzajMiasta}>{TIER[capex.tier]}</Row>
                <Row label={M.cenaZaMetrKwadratowy}>{money2(capex.pln_per_m2)}</Row>
                <Row label={M.mnoznik}>{formatDecimal(capex.multiplier, 2)}</Row>
                <Row label={M.szacunekPodstawowy}>{money2(capex.base_pln)}</Row>
                <Row label={M.zakres}>
                  {M.range({ low: money2(capex.low_pln), high: money2(capex.high_pln) })}
                </Row>
                <Row label={M.pewnoscSzacunku}>{CONFIDENCE[capex.confidence]}</Row>
                <Row label={M.wersjaCennika}>{capex.catalog_version}</Row>
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
  return negative ? M.belowAsking({ size }) : M.aboveAsking({ size });
}

function PriceSection({ report }: { readonly report: DealAnalysis }) {
  const { valuation, cash_flow: cash } = report;
  const gap = discountSentence(valuation.discount_to_asking);
  return (
    <Section id="cena" title={M.cenaZakupu}>
      <dl className={styles["figures"]}>
        <div className={styles["figure"]}>
          <dt>{M.cenaProgowaOfertowa}</dt>
          <dd>
            {gap === null ? (
              <span className={styles["unknown"]}>{NOT_COMPUTED}</span>
            ) : (
              <span className={styles["value"]}>{gap}</span>
            )}
            <span className={styles["hint"]}>
              {valuation.max_bid_pln === null
                ? M.noPriceMeetsHurdle
                : M.maxBidIs({ price: formatMoney(valuation.max_bid_pln, { decimals: 0 }) })}
            </span>
          </dd>
        </div>
        <Figure
          label={M.cenaOfertowa}
          value={valuation.asking_price_pln}
          hint={M.cenaOgloszeniaCenaTransakcyjna}
        />
        <div className={styles["figure"]}>
          <dt>{M.zwrotPrzyCenieOfertowej}</dt>
          <dd>
            <span className={styles["value"]}>
              {valuation.irr_at_asking === null ? (
                <span className={styles["unknown"]}>{NOT_COMPUTED}</span>
              ) : (
                formatRatio(valuation.irr_at_asking)
              )}
            </span>
            <span className={styles["hint"]}>{M.irrHint({ hurdle: formatRatio(valuation.hurdle) })}</span>
          </dd>
        </div>
      </dl>
      {!valuation.max_bid_bounded ? (
        <InlineNotice tone="info" title={M.wynikJestTylkoGornaGranica}>
          {M.progZwrotuBylbySpelnionyNawet}
        </InlineNotice>
      ) : null}
      <DisclosureGroup
        items={[
          {
            value: "sensitivity",
            title: M.zwrotyWyjscieWrazliwoscWzrostCen,
            children: (
              <dl className={styles["rows"]}>
                <Row label={M.rentownoscBrutto}>{formatRatio(cash.returns.gross_yield, 2)}</Row>
                <Row label={M.rentownoscNetto}>{formatRatio(cash.returns.net_yield, 2)}</Row>
                <Row label={M.stopaZwrotuIrr}>{formatRatio(cash.returns.irr, 2)}</Row>
                <Row label={M.sredniRocznyWzrostKapitaluCagr}>{formatRatio(cash.returns.cagr, 2)}</Row>
                <Row label={M.mnoznikKapitaluMoic}>{formatDecimal(cash.returns.moic, 2)}</Row>
                <Row label={M.wartoscSprzedazy10Latach}>{money2(cash.exit.exit_value_pln)}</Row>
                <Row label={M.kosztySprzedazy}>{money2(cash.exit.selling_costs_pln)}</Row>
                <Row label={M.podatekPrzySprzedazy}>{money2(cash.exit.sale_tax_pln)}</Row>
                <Row label={M.wplywyNettoZeSprzedazy} total>
                  {money2(cash.exit.net_proceeds_pln)}
                </Row>
                <Row label={M.cenaProgowaGdyCenyRosna}>
                  {money2(valuation.max_bid_if_appreciation_minus_1pp_pln)}
                </Row>
                <Row label={M.cenaProgowaGdyCenyRosna2}>
                  {money2(valuation.max_bid_if_appreciation_plus_1pp_pln)}
                </Row>
              </dl>
            ),
          },
          {
            value: "years",
            title: M.przeplywyPieniezneRokRoku,
            children: (
              <div className={styles["tableWrap"]}>
                <table className={styles["table"]}>
                  <caption>{M.kwotyZlotychBezKapitaluStart}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{M.rok}</th>
                      <th scope="col">{M.czynsz}</th>
                      <th scope="col">{M.koszty}</th>
                      <th scope="col">{M.podatek}</th>
                      <th scope="col">{M.wynik}</th>
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
      title: M.formaWlasnosciJestUstalona,
      check: M.sprawdzKsiedzeWieczystejJakiePrawo,
    });
  if (report.legal.price_basis === "unknown")
    extra.push({
      title: M.wiadomoCzyCenaZawieraVat,
      check: M.zapytajSprzedajacegoCzyCenaJest,
    });
  return (
    <Section id="sprawdz" title={M.coSprawdzicPrzedOferta}>
      {warnings.length === 0 && extra.length === 0 ? (
        <p className={styles["muted"]}>{M.silnikZglosilZastrzezenToZastepuje}</p>
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
      title: M.daneOgloszenia,
      children: (
        <dl className={styles["rows"]}>
          <Row label={M.numerOgloszenia}>{listing.otodom_id}</Row>
          <Row label={M.miasto}>{text(listing.city)}</Row>
          <Row label={M.ulica}>{text(listing.street)}</Row>
          <Row label={M.powierzchnia}>{formatArea(listing.area_m2)}</Row>
          <Row label={M.liczbaPokoi}>{formatCount(listing.rooms)}</Row>
          <Row label={M.pietro}>{text(listing.floor)}</Row>
          <Row label={M.rokBudowy}>{text(listing.build_year)}</Row>
          <Row label={M.rodzajBudynku}>{text(listing.building_type)}</Row>
          <Row label={M.ogrzewanie}>{text(listing.heating)}</Row>
          <Row label={M.okna}>{text(listing.windows)}</Row>
          <Row label={M.formaWlasnosci}>{TITLE_FORM[ownership.title_form]}</Row>
          <Row label={M.rodzajLokalu}>{LEGAL_CLASS[legal.legal_class]}</Row>
          <Row label={M.rozliczenieCeny}>{PRICE_BASIS[legal.price_basis]}</Row>
          <Row label={M.dodano}>{formatDate(listing.created_at)}</Row>
          <Row label={M.zaktualizowano}>{formatDate(listing.modified_at)}</Row>
          <Row label={M.zdjeciaOgloszeniu}>{formatCount(listing.photo_urls.length)}</Row>
          <Row label={M.rzutyOgloszeniu}>{formatCount(listing.floor_plan_urls.length)}</Row>
        </dl>
      ),
    },
    {
      value: "vision",
      title: M.ocenaZdjec,
      children:
        vision === null ? (
          <p className={styles["muted"]}>{M.zdjecOcenionoWiecStanMieszkania}</p>
        ) : (
          <dl className={styles["rows"]}>
            <Row label={M.zdjeciaOcenie}>{formatCount(vision.photos_total)}</Row>
            <Row label={M.zdjeciaPominiete}>{formatCount(vision.photos_excluded)}</Row>
            <Row label={M.stanWgZdjec}>{CONDITION[vision.condition]}</Row>
            <Row label={M.korektaCzynszu}>
              {vision.rent === null
                ? M.none
                : vision.rent.clamped
                  ? M.adjustmentClamped({ value: formatRatio(vision.rent.applied), clamp: CLAMP })
                  : formatRatio(vision.rent.applied)}
            </Row>
            <Row label={M.korektaKosztuRemontu}>
              {vision.capex === null
                ? M.none
                : vision.capex.clamped
                  ? M.adjustmentClamped({ value: formatRatio(vision.capex.applied), clamp: CLAMP })
                  : formatRatio(vision.capex.applied)}
            </Row>
            <Row label={M.modelWersjaInstrukcji}>
              {vision.model}, {vision.prompt_version}
            </Row>
          </dl>
        ),
    },
    ...(evidence.length > 0
      ? [
          {
            value: "evidence",
            title: M.evidenceTitle({ count: formatCount(evidence.length) }),
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
    <Section id="zrodla" title={M.zrodlaZalozenia}>
      <DisclosureGroup items={items} />
      <div className={styles["footer"]}>
        <span>{M.versions({ engine: report.engine_version, assumptions: report.assumptions_version })}</span>
        <span>{M.cenyOfertoweToCenyOgloszen}</span>
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
