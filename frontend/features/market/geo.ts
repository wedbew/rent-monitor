/**
 * Map geometry and colour classes: pure, no network. The boundaries are the official PRG outlines
 * (`public/geo/*.json`, joined to places by TERYT code, never by name). Network data is untrusted, so the file is
 * checked field by field before anything is drawn; a malformed file yields `null` and the page falls back to the
 * table. A gmina's outline is an administrative area, not the position of any listing.
 */

export type Ring = readonly (readonly [number, number])[];
export interface Geometry {
  readonly bbox: readonly [number, number, number, number];
  readonly gminas: ReadonlyMap<string, readonly Ring[]>;
  readonly points: ReadonlyMap<string, readonly [number, number]>;
}

const isNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isPoint = (v: unknown): v is readonly [number, number] =>
  Array.isArray(v) && v.length === 2 && isNumber(v[0]) && isNumber(v[1]);

export function parseGeometry(raw: unknown): Geometry | null {
  if (typeof raw !== "object" || raw === null) return null;
  const { bbox, gminas, points } = raw as Record<string, unknown>;
  if (!Array.isArray(bbox) || bbox.length !== 4 || !bbox.every(isNumber)) return null;
  if (typeof gminas !== "object" || gminas === null || typeof points !== "object" || points === null)
    return null;
  const shapes = new Map<string, readonly Ring[]>();
  for (const [code, rings] of Object.entries(gminas)) {
    if (!/^\d{7}$/.test(code) || !Array.isArray(rings)) return null;
    for (const ring of rings as unknown[]) {
      if (!Array.isArray(ring) || ring.length < 4 || !ring.every(isPoint)) return null;
    }
    shapes.set(code, rings as Ring[]);
  }
  const centres = new Map<string, readonly [number, number]>();
  for (const [code, point] of Object.entries(points)) {
    if (!isPoint(point)) return null;
    centres.set(code, point);
  }
  return { bbox: bbox as unknown as Geometry["bbox"], gminas: shapes, points: centres };
}

export interface View {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

/** Equirectangular with the longitude squeezed by cos(52 deg): good enough at the scale of one country. */
const SQUEEZE = Math.cos((52 * Math.PI) / 180);
export const project = ([lon, lat]: readonly [number, number]): readonly [number, number] => [
  lon * SQUEEZE * 100,
  -lat * 100,
];

export function fullView(bbox: Geometry["bbox"]): View {
  const [x0, y0] = project([bbox[0], bbox[3]]);
  const [x1, y1] = project([bbox[2], bbox[1]]);
  return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
}

export function pathOf(rings: readonly Ring[]): string {
  return rings
    .map((ring) =>
      ring
        .map((point, i) => {
          const [x, y] = project(point);
          return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(""),
    )
    .map((d) => `${d}Z`)
    .join("");
}

/** Zoom about the centre, never past the whole country and never closer than 1/40 of it. */
export function zoomView(view: View, whole: View, factor: number): View {
  const width = Math.min(whole.width, Math.max(whole.width / 40, view.width / factor));
  const height = (width / whole.width) * whole.height;
  return { x: view.x + (view.width - width) / 2, y: view.y + (view.height - height) / 2, width, height };
}

export function panView(view: View, whole: View, dx: number, dy: number): View {
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
  return {
    ...view,
    x: clamp(view.x + dx, whole.x, whole.x + whole.width - view.width),
    y: clamp(view.y + dy, whole.y, whole.y + whole.height - view.height),
  };
}

/** Five equal-count classes over the values shown; null stays unclassified, never class 0. */
export function classify(values: readonly (number | null)[], classes = 5): (number | null)[] {
  const sorted = values.filter((v): v is number => v !== null).sort((a, b) => a - b);
  if (sorted.length === 0) return values.map(() => null);
  const cuts = Array.from(
    { length: classes - 1 },
    (_, i) => sorted[Math.floor(((i + 1) * sorted.length) / classes)] ?? 0,
  );
  return values.map((v) => (v === null ? null : cuts.filter((c) => v >= c).length));
}

export function classRanges(values: readonly number[], classes = 5): readonly [number, number][] {
  const sorted = [...values].sort((a, b) => a - b);
  if (sorted.length === 0) return [];
  const edges = [
    0,
    ...Array.from({ length: classes - 1 }, (_, i) => Math.floor(((i + 1) * sorted.length) / classes)),
    sorted.length,
  ];
  return edges
    .slice(0, -1)
    .map(
      (start, i) =>
        [sorted[start] ?? 0, sorted[(edges[i + 1] ?? sorted.length) - 1] ?? 0] as [number, number],
    );
}
