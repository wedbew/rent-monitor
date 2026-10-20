import { formatCount, formatDate } from "../../api/format";
import type { StatMeta } from "../../charts/meta";
import { t } from "../../i18n";

/**
 * The five answers for the Otodom asking-rent figures, built once so every card and chart on the Rynek pages says the
 * same thing (`.agent/rules/statistics.md`). `area` already names the kind of area ("miejscowość z katalogu Otodom",
 * "dzielnica wg Otodom"); `day` is the reading date.
 */
export interface AskingContext {
  readonly area: string;
  readonly group: string;
  readonly day: string | null;
  readonly pricedCount: number | null;
}

const period = (day: string | null): string =>
  day === null
    ? t.rynek.sources.otodomFacts.period
    : t.rynek.stats.meta.periodWithDay({ period: t.rynek.sources.otodomFacts.period, day: formatDate(day) });

const sample = (count: number | null, group: string): string =>
  count === null
    ? t.rynek.stats.meta.sampleGroup({ group })
    : t.rynek.stats.meta.sampleOffers({ count: formatCount(count), group });

export function ppm2Meta(c: AskingContext): StatMeta {
  return {
    measure: t.rynek.place.cards.ppm2,
    unit: t.rynek.compare.ppm2Unit,
    area: c.area,
    period: period(c.day),
    source: t.rynek.sources.otodomFacts.source,
    sample: sample(c.pricedCount, c.group),
    interpretation: `${t.rynek.stats.median} ${t.rynek.stats.askingNote}`,
  };
}

export function rentMeta(c: AskingContext): StatMeta {
  return {
    measure: t.rynek.place.cards.rent,
    unit: t.rynek.stats.meta.rentUnit,
    area: c.area,
    period: period(c.day),
    source: t.rynek.sources.otodomFacts.source,
    sample: sample(c.pricedCount, c.group),
    interpretation: `${t.rynek.stats.median} ${t.rynek.stats.askingNote}`,
  };
}

export function rangeMeta(c: AskingContext): StatMeta {
  return {
    measure: t.rynek.place.cards.range,
    unit: t.rynek.compare.ppm2Unit,
    area: c.area,
    period: period(c.day),
    source: t.rynek.sources.otodomFacts.source,
    sample: sample(c.pricedCount, c.group),
    interpretation: t.rynek.stats.quartiles,
  };
}

export function sampleMeta(c: AskingContext): StatMeta {
  return {
    measure: t.rynek.place.cards.sample,
    unit: t.rynek.stats.meta.countUnit,
    area: c.area,
    period: period(c.day),
    source: t.rynek.sources.otodomFacts.source,
    sample: t.rynek.stats.meta.sampleGroup({ group: c.group }),
    interpretation: t.rynek.stats.meta.sampleInterpretation,
  };
}

export const trendMeta = (c: AskingContext, first: string | null, last: string | null): StatMeta => ({
  measure: t.rynek.stats.legendMedian,
  unit: t.rynek.compare.ppm2Unit,
  area: c.area,
  period:
    first === null || last === null
      ? t.rynek.sources.otodomFacts.period
      : t.rynek.stats.meta.seriesPeriod({ from: formatDate(first), to: formatDate(last) }),
  source: t.rynek.sources.otodomFacts.source,
  sample: t.rynek.stats.meta.sampleGroup({ group: c.group }),
  interpretation: `${t.rynek.stats.median} ${t.rynek.stats.quartiles} ${t.rynek.stats.askingNote}`,
});
