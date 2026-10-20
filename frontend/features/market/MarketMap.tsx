import { useQuery } from "@tanstack/react-query";
import {
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { formatCount, formatDecimal, formatPricePerArea } from "../../api/format";
import { t } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { InlineNotice } from "../../ui/Status";
import {
  classify,
  classRanges,
  fullView,
  type Geometry,
  pathOf,
  parseGeometry,
  project,
  type Ring,
} from "./geo";
import {
  type Camera,
  clusterMarkers,
  easeInOut,
  fitBox,
  isVisible,
  lerpCamera,
  limitCamera,
  type Marker,
  type MarkerInput,
  panBy,
  placeLabels,
  reservedAreas,
  sameCamera,
  type Size,
  TARGET,
  viewBoxOf,
  wholeCamera,
  zoomAt,
} from "./mapCamera";
import { MapPreview } from "./MapPreview";
import type { OverviewPlace } from "./queries";
import styles from "./map.module.css";

// LEGAL[third-party-data]: official PRG boundaries (GUGiK); terms to be confirmed (B-012, L-095) (RM-282)
// LEGAL[republication]: markers show aggregates of Otodom asking rents per place, never a listing (RM-282, RM-439)

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

export interface MarketMapProps {
  readonly places: readonly OverviewPlace[];
  readonly metric: MapMetric;
  readonly selected: string | null;
  readonly compared: readonly string[];
  readonly compareFull: boolean;
  readonly groupLabel: string;
  readonly placeHref: (id: string) => string;
  readonly onSelect: (id: string | null) => void;
  readonly onToggleCompare: (id: string) => void;
}

export function MarketMap(props: MarketMapProps) {
  const geometry = useGeometry();
  if (geometry.isPending)
    return (
      <p className={styles["note"]} role="status" aria-busy="true">
        {t.rynek.map.loading}
      </p>
    );
  if (geometry.isError || geometry.data === null || geometry.data === undefined)
    return <InlineNotice tone="warning" title={t.rynek.map.failed} live="status" />;
  return <Drawn {...props} geometry={geometry.data} />;
}

const DURATION_MS = 360;
const WHEEL_MS = 160;
const KEY_PAN_PX = 96;
const ZOOM_STEP = 1.7;
const reducedMotion = (): boolean =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;

/** The country, the areas of the mapped gminas and their outlines: drawn once, not on every camera frame. */
const Basemap = memo(function Basemap({
  background,
  areas,
}: {
  readonly background: string;
  readonly areas: readonly { readonly id: string; readonly d: string; readonly cls: number | null }[];
}) {
  return (
    <>
      <path d={background} className={styles["land"]} />
      {areas.map((a) => (
        <path
          key={a.id}
          d={a.d}
          className={`${styles["area"]} ${a.cls === null ? styles["none"] : styles[`c${a.cls}`]}`}
        />
      ))}
    </>
  );
});

function useFrameSize(ref: React.RefObject<HTMLElement | null>): Size {
  const [size, setSize] = useState<Size>({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (el === null) return;
    const read = () => {
      const box = el.getBoundingClientRect();
      setSize((prev) =>
        Math.abs(prev.width - box.width) < 0.5 && Math.abs(prev.height - box.height) < 0.5
          ? prev
          : { width: box.width, height: box.height },
      );
    };
    read();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return size;
}

/** Source names carry their powiat and voivodeship after a comma; a map label is the place alone. */
const shortName = (name: string): string => name.split(",")[0]?.trim() ?? name;

function summaryOf(place: OverviewPlace): string {
  if (place.data_status === "unavailable" || place.priced_count === null) return t.rynek.map.summaryNone;
  const sample = formatCount(place.priced_count);
  if (place.sufficient !== true) return t.rynek.map.summaryWithheld({ sample });
  return t.rynek.map.summaryData({ ppm2: formatPricePerArea(place.median_ppm2), sample: `${sample} ofert` });
}

function Drawn({
  geometry,
  places,
  metric,
  selected,
  compared,
  compareFull,
  groupLabel,
  placeHref,
  onSelect,
  onToggleCompare,
}: MarketMapProps & { readonly geometry: Geometry }) {
  const frameRef = useRef<HTMLDivElement>(null);
  const size = useFrameSize(frameRef);
  const whole = useMemo(() => fullView(geometry.bbox), [geometry]);
  const [camera, setCamera] = useState<Camera | null>(null);
  const camRef = useRef<Camera | null>(null);
  const targetRef = useRef<Camera | null>(null);
  const raf = useRef<number | null>(null);
  const atWhole = useRef(true);
  const active = useRef(false);
  const [hover, setHover] = useState<string | null>(null);
  const [cluster, setCluster] = useState<readonly string[] | null>(null);
  const hintId = useId();

  const commit = useCallback((next: Camera) => {
    camRef.current = next;
    setCamera(next);
  }, []);

  const stop = useCallback(() => {
    if (raf.current !== null) cancelAnimationFrame(raf.current);
    raf.current = null;
  }, []);

  const animateTo = useCallback(
    (target: Camera, ms = DURATION_MS) => {
      stop();
      targetRef.current = target;
      const start = camRef.current;
      if (start === null || ms <= 0 || reducedMotion() || sameCamera(start, target)) {
        commit(target);
        return;
      }
      const t0 = performance.now();
      const step = (now: number) => {
        const k = Math.min(1, (now - t0) / ms);
        commit(k >= 1 ? target : lerpCamera(start, target, easeInOut(k)));
        raf.current = k < 1 ? requestAnimationFrame(step) : null;
      };
      raf.current = requestAnimationFrame(step);
    },
    [commit, stop],
  );

  useEffect(() => stop, [stop]);

  // First fit, and refit on resize while the whole country is showing; otherwise keep the view inside the limits.
  useLayoutEffect(() => {
    if (size.width <= 0 || size.height <= 0) return;
    const base = wholeCamera(whole, size);
    if (camRef.current === null || atWhole.current) {
      stop();
      targetRef.current = base;
      commit(base);
    } else {
      commit(limitCamera(camRef.current, whole, size));
    }
  }, [size, whole, commit, stop]);

  const byId = useMemo(() => new Map(places.map((p) => [p.location_id, p])), [places]);
  const values = useMemo(() => places.map((p) => metricValue(p, metric)), [places, metric]);
  const classes = useMemo(() => classify(values), [values]);
  const classOf = useMemo(
    () => new Map(places.map((p, i) => [p.location_id, classes[i] ?? null])),
    [places, classes],
  );
  const ranges = useMemo(() => classRanges(values.filter((v): v is number => v !== null)), [values]);
  const maxSample = useMemo(() => Math.max(1, ...places.map((p) => p.priced_count ?? 0)), [places]);

  const background = useMemo(() => pathOf([...geometry.gminas.values()].flat()), [geometry]);
  const areas = useMemo(
    () =>
      places.flatMap((p) => {
        const rings: readonly Ring[] | undefined =
          p.mapping === "mapped" && p.relation === "gmina" && p.gmina_teryt !== null
            ? geometry.gminas.get(p.gmina_teryt)
            : undefined;
        return rings === undefined
          ? []
          : [{ id: p.location_id, d: pathOf(rings), cls: classOf.get(p.location_id) ?? null }];
      }),
    [places, geometry, classOf],
  );

  const inputs = useMemo<MarkerInput[]>(
    () =>
      places.flatMap((p) => {
        const c =
          p.mapping === "mapped" && p.gmina_teryt !== null ? geometry.points.get(p.gmina_teryt) : undefined;
        if (c === undefined) return [];
        const [x, y] = project(c);
        return [{ id: p.location_id, x, y, weight: p.priced_count ?? 0 }];
      }),
    [places, geometry],
  );
  const pointOf = useMemo(() => new Map(inputs.map((i) => [i.id, i])), [inputs]);

  const previewOpen = selected !== null || cluster !== null;
  const markers: Marker[] = useMemo(
    () =>
      camera === null || size.width <= 0
        ? []
        : clusterMarkers(inputs, camera, size, undefined, reservedAreas(size, previewOpen)),
    [inputs, camera, size, previewOpen],
  );
  const labels = useMemo(() => {
    if (camera === null) return new Map<string, { left: number; top: number }>();
    const singles = markers.flatMap((m) => (m.kind === "place" ? [m] : []));
    const placed = placeLabels(
      singles.flatMap((m) => {
        const p = byId.get(m.id);
        return p === undefined
          ? []
          : [{ id: m.id, sx: m.sx, sy: m.sy, text: shortName(p.name), weight: p.priced_count ?? 0 }];
      }),
      markers.map((m) => [m.sx, m.sy] as const),
      size,
    );
    return new Map(placed.map((l) => [l.id, { left: l.left, top: l.top }]));
  }, [markers, byId, camera, size]);

  // A selection made elsewhere (the table) brings its marker into view.
  const lastSelected = useRef<string | null>(null);
  useEffect(() => {
    if (selected === null || selected === lastSelected.current) {
      lastSelected.current = selected;
      return;
    }
    lastSelected.current = selected;
    const at = pointOf.get(selected);
    const cam = camRef.current;
    if (at === undefined || cam === null || size.width <= 0) return;
    if (isVisible(cam, size, at.x, at.y, 40) && markers.some((m) => m.kind === "place" && m.id === selected))
      return;
    atWhole.current = false;
    const target = fitBox(
      { x0: at.x, y0: at.y, x1: at.x, y1: at.y },
      whole,
      size,
      120,
      wholeCamera(whole, size).scale * 14,
    );
    // On a phone the preview is a sheet over the lower part: put the place in the upper quarter, beside the card
    // on a wide frame: in the free middle, so the marker the person chose is never under what describes it.
    const shifted: Camera =
      size.width <= 640
        ? { ...target, cy: at.y + (size.height * 0.25) / target.scale }
        : { ...target, cx: at.x - (size.width * 0.15) / target.scale };
    animateTo(limitCamera(shifted, whole, size));
  }, [selected, pointOf, markers, size, whole, animateTo]);

  // --- gestures ----------------------------------------------------------------------------------------
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ dist: number; mid: readonly [number, number] } | null>(null);
  const localPoint = (clientX: number, clientY: number): readonly [number, number] => {
    const box = frameRef.current?.getBoundingClientRect();
    return [clientX - (box?.left ?? 0), clientY - (box?.top ?? 0)];
  };
  const isUi = (target: EventTarget | null) =>
    target instanceof Element && target.closest("[data-map-ui]") !== null;

  const interrupt = () => {
    stop();
    atWhole.current = false;
  };

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    active.current = true;
    if (isUi(e.target)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // The pointer is already gone (a finger lifted between the events): the gesture simply continues without capture.
    }
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()] as [{ x: number; y: number }, { x: number; y: number }];
      gesture.current = {
        dist: Math.hypot(a.x - b.x, a.y - b.y),
        mid: localPoint((a.x + b.x) / 2, (a.y + b.y) / 2),
      };
    }
    frameRef.current?.focus({ preventScroll: true });
  };
  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const prev = pointers.current.get(e.pointerId);
    const cam = camRef.current;
    if (prev === undefined || cam === null) return;
    const next = { x: e.clientX, y: e.clientY };
    pointers.current.set(e.pointerId, next);
    interrupt();
    if (pointers.current.size === 1) {
      const moved = panBy(cam, whole, size, next.x - prev.x, next.y - prev.y);
      targetRef.current = moved;
      commit(moved);
    } else if (pointers.current.size === 2 && gesture.current !== null) {
      const [a, b] = [...pointers.current.values()] as [{ x: number; y: number }, { x: number; y: number }];
      const dist = Math.hypot(a.x - b.x, a.y - b.y);
      const mid = localPoint((a.x + b.x) / 2, (a.y + b.y) / 2);
      let out = panBy(cam, whole, size, mid[0] - gesture.current.mid[0], mid[1] - gesture.current.mid[1]);
      if (gesture.current.dist > 0)
        out = zoomAt(out, whole, size, dist / gesture.current.dist, mid[0], mid[1]);
      gesture.current = { dist, mid };
      targetRef.current = out;
      commit(out);
    }
  };
  const onPointerEnd = (e: ReactPointerEvent<HTMLDivElement>) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) gesture.current = null;
  };

  // The wheel zooms only after the map was clicked or with Ctrl (a trackpad pinch is a Ctrl wheel), so a page
  // scrolling past the map is never captured by accident.
  useEffect(() => {
    const el = frameRef.current;
    if (el === null) return;
    const onWheel = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey || active.current)) return;
      const cam = targetRef.current ?? camRef.current;
      if (cam === null) return;
      e.preventDefault();
      interrupt();
      const k = Math.exp(-e.deltaY * (e.ctrlKey ? 0.012 : e.deltaMode === 1 ? 0.05 : 0.0016));
      const [sx, sy] = localPoint(e.clientX, e.clientY);
      animateTo(zoomAt(cam, whole, size, k, sx, sy), WHEEL_MS);
    };
    const away = (e: PointerEvent) => {
      if (!el.contains(e.target as Node)) active.current = false;
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    document.addEventListener("pointerdown", away);
    return () => {
      el.removeEventListener("wheel", onWheel);
      document.removeEventListener("pointerdown", away);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handlers read refs and the latest size/whole
  }, [animateTo, size, whole]);

  const zoom = (factor: number) => {
    const cam = targetRef.current ?? camRef.current;
    if (cam === null) return;
    interrupt();
    animateTo(zoomAt(cam, whole, size, factor, size.width / 2, size.height / 2));
  };
  const reset = () => {
    stop();
    atWhole.current = true;
    animateTo(wholeCamera(whole, size));
  };
  const nudge = (dx: number, dy: number) => {
    const cam = targetRef.current ?? camRef.current;
    if (cam === null) return;
    interrupt();
    animateTo(panBy(cam, whole, size, dx, dy), 140);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) {
      if (e.key === "Escape") {
        onSelect(null);
        setCluster(null);
      }
      return;
    }
    const keys: Record<string, () => void> = {
      ArrowLeft: () => nudge(KEY_PAN_PX, 0),
      ArrowRight: () => nudge(-KEY_PAN_PX, 0),
      ArrowUp: () => nudge(0, KEY_PAN_PX),
      ArrowDown: () => nudge(0, -KEY_PAN_PX),
      "+": () => zoom(ZOOM_STEP),
      "=": () => zoom(ZOOM_STEP),
      "-": () => zoom(1 / ZOOM_STEP),
      _: () => zoom(1 / ZOOM_STEP),
      "0": reset,
      Home: reset,
      Escape: () => {
        onSelect(null);
        setCluster(null);
      },
    };
    const action = keys[e.key];
    if (action !== undefined) {
      e.preventDefault();
      action();
    }
  };

  const openCluster = (m: Extract<Marker, { kind: "cluster" }>) => {
    const cam = camRef.current;
    if (cam === null) return;
    const target = fitBox(m.box, whole, size, 110);
    if (m.inseparable || target.scale <= cam.scale * 1.05) {
      onSelect(null);
      setCluster(m.ids);
      return;
    }
    interrupt();
    setCluster(null);
    animateTo(target);
  };

  const opener = useRef<string | null>(null);
  const selectPlace = (id: string) => {
    setCluster(null);
    opener.current = id;
    onSelect(id);
  };
  // After the preview closes, keyboard focus goes back to the marker that opened it.
  useEffect(() => {
    if (selected !== null || cluster !== null || opener.current === null) return;
    const id = opener.current;
    opener.current = null;
    frameRef.current
      ?.querySelector<HTMLElement>(`[data-place="${CSS.escape(id)}"]`)
      ?.focus({ preventScroll: true });
  }, [selected, cluster, markers]);

  const selectedPlace = selected === null ? undefined : byId.get(selected);
  const hovered = hover === null ? undefined : byId.get(hover);
  const hoverMarker = hover === null ? undefined : markers.find((m) => m.kind === "place" && m.id === hover);
  const zoomLevel = camera === null ? 1 : camera.scale / wholeCamera(whole, size).scale;
  const placeIsMapped = inputs.length > 0;

  return (
    <figure className={styles["figure"]}>
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- the map is a keyboard-operable widget: arrows pan, plus and minus zoom (named in its description) */}
      <div
        ref={frameRef}
        className={styles["frame"]}
        data-testid="market-map"
        role="group"
        aria-label={t.rynek.map.frame}
        aria-describedby={hintId}
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- focus is how the keyboard reaches the map controls
        tabIndex={0}
        onKeyDown={onKeyDown}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
      >
        {camera === null ? null : (
          <svg
            className={styles["map"]}
            viewBox={viewBoxOf(camera, size)}
            preserveAspectRatio="none"
            role="img"
            aria-label={t.rynek.map.label}
          >
            <Basemap background={background} areas={areas} />
          </svg>
        )}

        <div className={styles["markers"]}>
          {markers.map((m) => {
            if (m.kind === "cluster") {
              const names = m.ids
                .slice(0, 3)
                .map((id) => byId.get(id)?.name ?? id)
                .join(", ");
              const label = (
                m.inseparable ? t.rynek.map.markerClusterInseparable : t.rynek.map.markerCluster
              )({
                count: formatCount(m.ids.length),
                names,
              });
              return (
                <button
                  key={m.key}
                  type="button"
                  data-map-ui
                  data-cluster={m.ids.length}
                  className={styles["marker"]}
                  style={{ transform: `translate(${m.sx - TARGET / 2}px, ${m.sy - TARGET / 2}px)` }}
                  aria-label={label}
                  onClick={() => openCluster(m)}
                >
                  <span className={styles["clusterSymbol"]} aria-hidden="true">
                    {formatCount(m.ids.length)}
                  </span>
                </button>
              );
            }
            const place = byId.get(m.id);
            if (place === undefined) return null;
            const cls = classOf.get(m.id) ?? null;
            const noData = place.data_status === "unavailable" || place.priced_count === null;
            const withheld = !noData && place.sufficient !== true;
            const diameter = 14 + Math.round(12 * Math.sqrt((place.priced_count ?? 0) / maxSample));
            const isSelected = m.id === selected;
            const isCompared = compared.includes(m.id);
            return (
              <button
                key={m.id}
                type="button"
                data-map-ui
                data-place={m.id}
                className={styles["marker"]}
                style={{ transform: `translate(${m.sx - TARGET / 2}px, ${m.sy - TARGET / 2}px)` }}
                aria-label={t.rynek.map.markerPlace({ name: place.name, summary: summaryOf(place) })}
                aria-pressed={isSelected}
                aria-describedby={hover === m.id ? `${hintId}-tip` : undefined}
                onClick={() => selectPlace(m.id)}
                onPointerEnter={() => setHover(m.id)}
                onPointerLeave={() => setHover((h) => (h === m.id ? null : h))}
                onFocus={() => setHover(m.id)}
                onBlur={() => setHover((h) => (h === m.id ? null : h))}
              >
                <span
                  className={`${styles["symbol"]} ${
                    noData
                      ? styles["symbolNone"]
                      : withheld
                        ? styles["symbolWithheld"]
                        : styles[`s${cls ?? 0}`]
                  } ${isSelected ? styles["symbolSelected"] : ""}`}
                  style={{ width: diameter, height: diameter }}
                  aria-hidden="true"
                >
                  {isCompared ? <Icon name="check" size={12} /> : null}
                </span>
              </button>
            );
          })}
          {[...labels.entries()].map(([id, at]) => (
            <span
              key={id}
              className={styles["label"]}
              style={{ transform: `translate(${at.left}px, ${at.top}px)` }}
              aria-hidden="true"
            >
              {shortName(byId.get(id)?.name ?? "")}
            </span>
          ))}
          {hovered !== undefined && hoverMarker !== undefined ? (
            <div
              id={`${hintId}-tip`}
              role="tooltip"
              className={styles["tooltip"]}
              style={{
                transform: `translate(${Math.min(Math.max(hoverMarker.sx, 90), Math.max(size.width - 90, 90))}px, ${Math.max(hoverMarker.sy - 30, 8)}px) translate(-50%, -100%)`,
              }}
            >
              <strong>{hovered.name}</strong>
              <span>{summaryOf(hovered)}</span>
            </div>
          ) : null}
        </div>

        <div className={styles["controls"]} role="group" aria-label={t.rynek.map.controls} data-map-ui>
          <button
            type="button"
            className={styles["control"]}
            aria-label={t.rynek.map.zoomIn}
            onClick={() => zoom(ZOOM_STEP)}
          >
            <Icon name="plus" size={20} />
          </button>
          <button
            type="button"
            className={styles["control"]}
            aria-label={t.rynek.map.zoomOut}
            onClick={() => zoom(1 / ZOOM_STEP)}
          >
            <Icon name="minus" size={20} />
          </button>
          <button
            type="button"
            className={`${styles["control"]} ${styles["controlWide"]}`}
            aria-label={t.rynek.map.resetLabel}
            onClick={reset}
          >
            {t.rynek.map.reset}
          </button>
        </div>

        {selectedPlace !== undefined || cluster !== null ? (
          <MapPreview
            place={selectedPlace}
            cluster={
              cluster === null
                ? null
                : cluster.flatMap((id) => (byId.get(id) === undefined ? [] : [byId.get(id) as OverviewPlace]))
            }
            groupLabel={groupLabel}
            compared={selectedPlace === undefined ? false : compared.includes(selectedPlace.location_id)}
            compareFull={compareFull}
            href={selectedPlace === undefined ? "" : placeHref(selectedPlace.location_id)}
            onClose={() => {
              onSelect(null);
              setCluster(null);
            }}
            onToggleCompare={() => selectedPlace !== undefined && onToggleCompare(selectedPlace.location_id)}
            onPick={selectPlace}
          />
        ) : null}

        <p id={hintId} className={styles["hint"]}>
          {t.rynek.map.help}
        </p>
        <span className={styles["zoomState"]} role="status">
          {t.rynek.map.zoomState({ level: formatDecimal(String(Math.round(zoomLevel * 10) / 10), 1) })}
        </span>
      </div>

      {placeIsMapped ? null : <p className={styles["note"]}>{t.rynek.map.noPoints}</p>}
      <figcaption className={styles["caption"]}>
        <ul className={styles["legend"]} aria-label={t.rynek.map.legend}>
          {ranges.map(([low, high], i) => (
            <li key={`${low}-${high}`}>
              <span className={`${styles["swatch"]} ${styles[`s${i}`]}`} aria-hidden="true" />
              {formatDecimal(String(low), 2)} – {formatDecimal(String(high), 2)}
            </li>
          ))}
        </ul>
        <p>{t.rynek.map.legendColor}</p>
        <p>{t.rynek.map.legendShapes}</p>
        <p>{t.rynek.map.areaNote}</p>
        <p>{t.rynek.map.attribution}</p>
      </figcaption>
    </figure>
  );
}
