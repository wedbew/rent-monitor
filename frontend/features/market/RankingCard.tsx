import { formatCount, formatDecimal, NOT_COMPUTED } from "../../api/format";
import { BarCompare } from "../../charts/BarCompare";
import { ChartFigure } from "../../charts/ChartFigure";
import { DataTable } from "../../charts/DataTable";
import { plotValue } from "../../charts/meta";
import { t } from "../../i18n";
import { Link } from "react-router";
import { InlineNotice } from "../../ui/Status";
import type { IndexComponent, IndexView } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import styles from "./gus.module.css";

// LEGAL[third-party-data]: a statistical summary derived from GUS BDL indicators (B-012) (RM-439)

const valueText = (c: IndexComponent): string =>
  c.value === null ? t.rynek.gus.components.noValue : `${formatDecimal(c.value, 2)} ${c.unit_pl}`;

/**
 * The experimental locality index of one gmina: the score and what 100 means, the position with its denominator and
 * the named cohort it was counted among, the regional position, then every component with its value, year and unit,
 * its position among all gminas, its own 0 to 100 score, its weight and its contribution in points. It says plainly
 * that a higher score is more favourable, which sources and years it rests on, how much of the weight was available,
 * and what is missing; when the publication cannot support a score or a rank it says that instead and shows no number.
 * It is statistics about an area: never a property valuation, a return or a forecast.
 */
export function RankingCard({
  index,
  placeName,
  profileHref,
}: {
  readonly index: IndexView;
  readonly placeName: string;
  readonly profileHref: (metricKey: string) => string;
}) {
  const scored = index.score !== null;
  const national = index.positions.find((p) => p.scope === "national");
  const region = index.positions.find((p) => p.scope === "voivodeship");
  const heading = t.rynek.gus.cardTitle;
  const ranked = scored && national !== undefined && national.rank !== null && national.of !== null;

  const title =
    index.state === "no_data" || index.state === "unavailable"
      ? t.rynek.gus.unavailableTitle
      : index.state === "not_scored"
        ? t.rynek.gus.notScoredTitle
        : index.state === "scored_not_ranked"
          ? t.rynek.gus.notRankedTitle
          : null;

  return (
    <article className={styles["card"]} aria-labelledby="gus-card-title" data-testid="ranking-card">
      <header className={styles["cardHead"]}>
        <h2 id="gus-card-title" className={styles["cardTitle"]}>
          {heading}
        </h2>
        <span className={styles["badge"]}>{t.rynek.gus.experimental}</span>
      </header>
      <p className={styles["muted"]}>{index.caveat_pl}</p>

      {index.gmina === null ? null : (
        <p className={styles["context"]}>{t.rynek.gus.gminaNote({ gmina: index.gmina.name })}</p>
      )}

      {title === null ? null : (
        <InlineNotice
          tone={index.state === "scored_not_ranked" ? "warning" : "info"}
          title={title}
          live="status"
        >
          {index.reasons.length === 0 ? null : (
            <span>
              {t.rynek.gus.reasons}: {index.reasons.join("; ")}
            </span>
          )}
        </InlineNotice>
      )}

      {scored ? (
        <div className={styles["scoreBlock"]}>
          <div>
            <p className={styles["scoreLabel"]}>{t.rynek.gus.score}</p>
            <p className={styles["score"]} data-testid="index-score">
              {formatDecimal(index.score, 1)} <span className={styles["scoreOf"]}>{t.rynek.gus.scoreOf}</span>
            </p>
            <div
              className={styles["meter"]}
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={plotValue(index.score) ?? 0}
              aria-valuetext={`${formatDecimal(index.score, 1)} ${t.rynek.gus.scoreOf}`}
              aria-label={t.rynek.gus.score}
            >
              <span
                className={styles["meterFill"]}
                style={{ width: `${Math.max(0, Math.min(100, plotValue(index.score) ?? 0))}%` }}
              />
            </div>
            <p className={styles["direction"]}>{t.rynek.gus.higherBetter}</p>
          </div>
          <div className={styles["positions"]}>
            {ranked && national.rank !== null && national.of !== null ? (
              <>
                <p className={styles["position"]} data-testid="index-position">
                  {t.rynek.gus.positionNational({
                    rank: formatCount(national.rank),
                    of: formatCount(national.of),
                  })}
                </p>
                <p className={styles["muted"]}>{t.rynek.gus.positionLine({ cohort: national.name_pl })}</p>
                {national.percentile === null ? null : (
                  <p className={styles["muted"]}>
                    {t.rynek.gus.percentile({ value: formatDecimal(national.percentile, 0) })}
                  </p>
                )}
              </>
            ) : null}
            {region === undefined || region.rank === null || region.of === null ? null : (
              <p className={styles["muted"]}>
                {t.rynek.gus.regionLine({
                  rank: formatCount(region.rank),
                  of: formatCount(region.of),
                  region: region.unit_name ?? "",
                })}
              </p>
            )}
          </div>
        </div>
      ) : null}
      <p className={styles["muted"]}>{t.rynek.gus.scoreHelp}</p>

      <section aria-labelledby="gus-components" className={styles["componentsSection"]}>
        <h3 id="gus-components">{t.rynek.gus.components.heading}</h3>
        <p className={styles["muted"]}>{t.rynek.gus.components.lead}</p>
        <ScrollRegion label={t.rynek.gus.components.tableCaption}>
          <table className={styles["table"]}>
            <caption>{t.rynek.gus.components.tableCaption}</caption>
            <thead>
              <tr>
                <th scope="col">{t.rynek.gus.components.columns.name}</th>
                <th scope="col" className={styles["num"]}>
                  {t.rynek.gus.components.columns.value}
                </th>
                <th scope="col" className={styles["num"]}>
                  {t.rynek.gus.components.columns.rank}
                </th>
                <th scope="col" className={styles["num"]}>
                  {t.rynek.gus.components.columns.score}
                </th>
                <th scope="col" className={styles["num"]}>
                  {t.rynek.gus.components.columns.weight}
                </th>
                <th scope="col" className={styles["num"]}>
                  {t.rynek.gus.components.columns.points}
                </th>
              </tr>
            </thead>
            <tbody>
              {index.components.map((c) => (
                <tr key={c.key}>
                  <th scope="row">
                    <span className={styles["componentName"]}>{c.name_pl}</span>
                    <span className={styles["componentNote"]}>
                      {c.pillar_pl}. {c.explain_pl} {c.favourable_pl}.
                    </span>
                    <Link
                      to={profileHref(c.metric_key)}
                      aria-label={t.rynek.gus.components.detailLink({ name: c.name_pl })}
                      className={styles["detailLink"]}
                    >
                      {t.rynek.gus.components.detail}
                    </Link>
                  </th>
                  <td className={styles["num"]}>
                    {valueText(c)}
                    {c.year === null ? null : (
                      <span className={styles["componentNote"]}>
                        {t.rynek.gus.components.yearLabel({ year: String(c.year) })},{" "}
                        {c.basis === "proxy" && c.measured !== null
                          ? t.rynek.gus.components.proxy({ unit: c.measured.name })
                          : t.rynek.gus.components.direct}
                      </span>
                    )}
                  </td>
                  <td className={styles["num"]}>
                    {c.national_rank === null || c.national_of === null
                      ? NOT_COMPUTED
                      : t.rynek.gus.components.rankOf({
                          rank: formatCount(c.national_rank),
                          of: formatCount(c.national_of),
                        })}
                  </td>
                  <td className={styles["num"]}>
                    {c.score === null ? NOT_COMPUTED : formatDecimal(c.score, 1)}
                  </td>
                  <td className={styles["num"]}>
                    {t.rynek.gus.components.weight({ percent: `${formatCount(c.weight)}%` })}
                  </td>
                  <td className={styles["num"]}>
                    {c.points === null
                      ? NOT_COMPUTED
                      : t.rynek.gus.components.pointsOf({ points: formatDecimal(c.points, 1) })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      {scored ? (
        <ChartFigure
          title={t.rynek.gus.components.chartTitle}
          meta={{
            measure: t.rynek.gus.components.chartTitle,
            unit: t.rynek.gus.components.pointsUnit,
            area: placeName,
            period:
              index.newest_year === null || index.oldest_year === null
                ? ""
                : t.rynek.gus.periods({ from: String(index.oldest_year), to: String(index.newest_year) }),
            source: t.rynek.gus.sourceLine,
            sample:
              national?.of === undefined || national.of === null
                ? t.rynek.gus.coverageValue({
                    percent: `${formatDecimal(String((plotValue(index.weight_coverage) ?? 0) * 100), 0)}%`,
                  })
                : `${formatCount(national.of)} ${national.name_pl}`,
            interpretation: t.rynek.gus.scoreHelp,
          }}
          table={
            <DataTable
              caption={t.rynek.gus.components.chartTitle}
              columns={[
                { key: "name", header: t.rynek.gus.components.columns.name },
                { key: "points", header: t.rynek.gus.components.columns.points, numeric: true },
              ]}
              rows={index.components.map((c) => ({
                id: c.key,
                cells: {
                  name: c.name_pl,
                  points:
                    c.points === null
                      ? NOT_COMPUTED
                      : t.rynek.gus.components.pointsOf({ points: formatDecimal(c.points, 1) }),
                },
              }))}
            />
          }
        >
          <BarCompare
            label={t.rynek.gus.components.chartTitle}
            max={100}
            items={index.components.map((c) => ({
              id: c.key,
              name: c.name_pl,
              value: c.points === null ? null : plotValue(c.points),
              valueText:
                c.points === null
                  ? NOT_COMPUTED
                  : t.rynek.gus.components.pointsOf({ points: formatDecimal(c.points, 1) }),
              meta:
                c.score === null
                  ? undefined
                  : `${t.rynek.gus.components.columns.score}: ${formatDecimal(c.score, 1)}`,
              withheldText: t.rynek.gus.components.noValue,
            }))}
          />
        </ChartFigure>
      ) : null}

      <dl className={styles["facts"]}>
        <div>
          <dt>{t.rynek.gus.coverage}</dt>
          <dd>
            {index.weight_coverage === null
              ? NOT_COMPUTED
              : t.rynek.gus.coverageValue({
                  percent: `${formatDecimal(String((plotValue(index.weight_coverage) ?? 0) * 100), 0)}%`,
                })}
          </dd>
        </div>
        <div>
          <dt>{t.rynek.gus.method}</dt>
          <dd>{t.rynek.gus.methodVersion({ version: String(index.method_version) })}</dd>
        </div>
        <div>
          <dt>{t.rynek.gus.periodsLabel}</dt>
          <dd>
            {index.newest_year === null || index.oldest_year === null
              ? NOT_COMPUTED
              : t.rynek.gus.periods({ from: String(index.oldest_year), to: String(index.newest_year) })}
          </dd>
        </div>
        <div>
          <dt>{t.rynek.gus.sourceLabel}</dt>
          <dd>{t.rynek.gus.sourceLine}</dd>
        </div>
        <div>
          <dt>{t.rynek.gus.exclusions}</dt>
          <dd>
            {index.missing.length === 0 ? (
              t.rynek.gus.exclusionsNone
            ) : (
              <ul className={styles["plain"]}>
                {index.missing.map((name) => (
                  <li key={name}>{t.rynek.gus.exclusionItem({ name })}</li>
                ))}
              </ul>
            )}
          </dd>
        </div>
      </dl>
    </article>
  );
}
