import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useMatches, useOutletContext, useSearchParams } from "react-router";

import { t } from "../../i18n";
import { PageHeading } from "../../shell/PageHeading";
import { gusAddress, gusPlaceAddress, GUS, otodomAddress, placeAddress } from "./addresses";
import { COHORT_KEYS, type CohortKey } from "./filters";
import styles from "./layout.module.css";

const ID = /^[a-z0-9-]{1,64}$/;

interface LayoutContext {
  readonly setTitle: (title: string | null) => void;
}

/** A page under Rynek names itself: the layout owns the one `h1` and shows this name in it. */
export function useMarketTitle(title: string | null): void {
  const context = useOutletContext<LayoutContext | null>();
  const setTitle = context?.setTitle;
  useEffect(() => {
    setTitle?.(title);
    return () => setTitle?.(null);
  }, [setTitle, title]);
}

/**
 * Rynek has two sources that are never mixed, so it has two tabs, each a path of its own: Otodom (asking rents,
 * the default) and GUS (official statistics and the ranking). Switching tab keeps what is meaningful in both: the
 * place being looked at and the group of flats. The tab says what its source is, for which period and at what
 * territorial grain, so an Otodom place and a GUS gmina are never mistaken for each other.
 */
export function MarketLayout() {
  const location = useLocation();
  const [title, setTitle] = useState<string | null>(null);
  const [params] = useSearchParams();
  const matches = useMatches();
  const onGus = location.pathname.startsWith(GUS);
  const fromPath = [...matches].reverse().find((m) => typeof m.params["locationId"] === "string")?.params[
    "locationId"
  ];
  const sel = params.get("sel");
  const place = fromPath ?? (sel !== null && ID.test(sel) ? sel : null);
  const cohortRaw = params.get("cohort");
  const cohort: CohortKey = COHORT_KEYS.find((c) => c === cohortRaw) ?? "all";

  const otodomTo = place === null ? otodomAddress({ cohort }) : placeAddress(place, cohort);
  const gusTo = place === null ? gusAddress() : gusPlaceAddress(place);
  const tabs = [
    {
      id: "otodom",
      label: t.rynek.tabs.otodom,
      hint: t.rynek.tabs.otodomHint,
      to: otodomTo,
      current: !onGus,
    },
    { id: "gus", label: t.rynek.tabs.gus, hint: t.rynek.tabs.gusHint, to: gusTo, current: onGus },
  ] as const;

  return (
    <div className={styles["page"]}>
      <PageHeading
        title={title ?? t.rynek.title}
        eyebrow={t.rynek.eyebrow}
        lead={onGus ? t.rynek.sources.gusLead : t.rynek.sources.otodomLead}
      />
      <nav aria-label={t.rynek.tabs.label} className={styles["tabs"]}>
        <ul>
          {tabs.map((tab) => (
            <li key={tab.id}>
              <Link
                to={tab.to}
                className={`${styles["tab"]} ${tab.current ? styles["current"] : ""}`}
                aria-current={tab.current ? "true" : undefined}
                data-tab={tab.id}
              >
                <span className={styles["tabName"]}>{tab.label}</span>
                <span className={styles["tabHint"]}>{tab.hint}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <section
        className={styles["source"]}
        aria-label={onGus ? t.rynek.sources.gusTitle : t.rynek.sources.otodomTitle}
      >
        <h2 className={styles["sourceTitle"]}>
          {onGus ? t.rynek.sources.gusTitle : t.rynek.sources.otodomTitle}
        </h2>
        <ul className={styles["facts"]}>
          {(onGus
            ? [
                t.rynek.sources.gusFacts.source,
                t.rynek.sources.gusFacts.period,
                t.rynek.sources.gusFacts.grain,
              ]
            : [
                t.rynek.sources.otodomFacts.source,
                t.rynek.sources.otodomFacts.period,
                t.rynek.sources.otodomFacts.grain,
              ]
          ).map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      </section>
      <Outlet context={{ setTitle } satisfies LayoutContext} />
    </div>
  );
}
