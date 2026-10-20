import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";

import { formatDecimal } from "../../api/format";
import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import {
  classify,
  classRanges,
  fullView,
  type Geometry,
  pathOf,
  panView,
  parseGeometry,
  project,
  type View,
  zoomView,
} from "./geo";
import type { OverviewPlace } from "./queries";
import styles from "./map.module.css";

// LEGAL[third-party-data]: official PRG boundaries (GUGiK); terms to be confirmed (B-012, L-095) (RM-282)
// LEGAL[republication]: colours show aggregates of Otodom asking rents per place, never a listing (RM-282)

export type MapMetric = "ppm2" | "rent" | "sample";

export const metricValue = (place: OverviewPlace, metric: MapMetric): number | null => {
  const raw =
    metric === "ppm2" ? place.median_ppm2 : metric === "rent" ? place.median_rent_pln : place.priced_count;
  if (raw === null || raw === undefined) return null;
  if (metric !== "sample" && place.sufficient !== true) return null; // a withheld sample is never coloured
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
};

async function loadGeometry(signal: AbortSignal): Promise<Geometry | null> {
  const response = await fetch("/geo/gminas.json", { signal, credentials: "same-origin" });
  if (!response.ok) throw new Error("geometry");
  return parseGeometry(await response.json());
}

function useGeometry() {
  return useQuery({
    queryKey: ["geo", "gminas", "v1"],
    queryFn: ({ signal }) => loadGeometry(signal),
    staleTime: Infinity,
    retry: 1,
  });
}

interface Props {
  readonly places: readonly OverviewPlace[];
  readonly metric: MapMetric;
  readonly selected: string | null;
  readonly onSelect: (id: string) => void;
}

export function MarketMap({ places, metric, selected, onSelect }: Props) {
  const geometry = useGeometry();
  if (geometry.isPending)
    return (
      <p className={styles["note"]} role="status" aria-busy="true">
        {t.market.explore.mapLoading}
      </p>
    );
  if (geometry.isError || geometry.data === null || geometry.data === undefined)
    return <InlineNotice tone="warning" title={t.market.explore.mapFailed} live="status" />;
  return (
    <Drawn geometry={geometry.data} places={places} metric={metric} selected={selected} onSelect={onSelect} />
  );
}

/** View units per screen pixel, read when the pointer moves (never during render). */
const scale = (el: SVGSVGElement, v: View): number => v.width / (el.clientWidth || 800);

function Drawn({ geometry, places, metric, selected, onSelect }: Props & { readonly geometry: Geometry }) {
  const whole = useMemo(() => fullView(geometry.bbox), [geometry]);
  const [view, setView] = useState<View>(whole);
  const drag = useRef<{ x: number; y: number } | null>(null);

  const background = useMemo(() => pathOf([...geometry.gminas.values()].flat()), [geometry]);
  const values = places.map((p) => metricValue(p, metric));
  const classes = classify(values);
  const ranges = classRanges(values.filter((v): v is number => v !== null));

  const shapes = places.flatMap((place, i) => {
    const code = place.gmina_teryt;
    if (place.mapping !== "mapped" || code === null) return [];
    const cls = classes[i] ?? null;
    const rings = geometry.gminas.get(code);
    const centre = geometry.points.get(code);
    return [{ place, cls, rings, centre }];
  });

  return (
    <figure className={styles["figure"]}>
      <div className={styles["tools"]}>
        <Button type="button" small onClick={() => setView((v) => zoomView(v, whole, 1.6))}>
          {t.market.explore.zoomIn}
        </Button>
        <Button type="button" small onClick={() => setView((v) => zoomView(v, whole, 1 / 1.6))}>
          {t.market.explore.zoomOut}
        </Button>
        <Button type="button" small onClick={() => setView(whole)}>
          {t.market.explore.reset}
        </Button>
      </div>
      <svg
        className={styles["map"]}
        viewBox={`${view.x} ${view.y} ${view.width} ${view.height}`}
        role="img"
        aria-label={t.market.explore.mapLabel}
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const start = drag.current;
          if (start === null) return;
          drag.current = { x: e.clientX, y: e.clientY };
          const el = e.currentTarget; // read now: the event is gone when the updater runs
          const [dx, dy] = [e.clientX - start.x, e.clientY - start.y];
          setView((v) => panView(v, whole, -dx * scale(el, v), -dy * scale(el, v)));
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
      >
        <path d={background} className={styles["land"]} />
        {shapes.map(({ place, cls, rings }) =>
          rings === undefined || place.relation !== "gmina" ? null : (
            <path
              key={place.location_id}
              d={pathOf(rings)}
              className={`${styles["area"]} ${cls === null ? styles["none"] : styles[`c${cls}`]} ${
                place.location_id === selected ? styles["selected"] : ""
              }`}
              data-place={place.location_id}
              onClick={() => onSelect(place.location_id)}
            >
              <title>{t.market.explore.pick({ name: place.name })}</title>
            </path>
          ),
        )}
        {shapes.map(({ place, cls, centre }) => {
          if (centre === undefined || place.relation !== "within_gmina") return null;
          const [x, y] = project(centre);
          return (
            <circle
              key={place.location_id}
              cx={x}
              cy={y}
              r={Math.max(view.width / 260, 0.6)}
              className={`${styles["dot"]} ${cls === null ? styles["none"] : styles[`c${cls}`]} ${
                place.location_id === selected ? styles["selected"] : ""
              }`}
              data-place={place.location_id}
              onClick={() => onSelect(place.location_id)}
            >
              <title>{t.market.explore.pick({ name: place.name })}</title>
            </circle>
          );
        })}
      </svg>
      <figcaption className={styles["caption"]}>
        <ul className={styles["legend"]} aria-label={t.market.explore.legend}>
          {ranges.map(([low, high], i) => (
            <li key={`${low}-${high}`}>
              <span className={`${styles["swatch"]} ${styles[`c${i}`]}`} aria-hidden="true" />
              {formatDecimal(String(low), 2)} – {formatDecimal(String(high), 2)}
            </li>
          ))}
          <li>
            <span className={`${styles["swatch"]} ${styles["none"]}`} aria-hidden="true" />
            {t.market.explore.noData}
          </li>
        </ul>
        <span>{t.market.explore.mapNote}</span> <span>{t.market.explore.noGeometry}</span>{" "}
        <span>{t.market.explore.attribution}</span>
      </figcaption>
    </figure>
  );
}
