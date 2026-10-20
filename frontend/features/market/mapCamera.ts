/**
 * The map's camera and its markers: pure geometry, no DOM. The basemap is drawn in projected units (`geo.ts`); the
 * camera is a centre (projected units) and a scale (pixels per unit), so a point's place on screen is
 * `(point - centre) * scale + size / 2`. Markers are HTML buttons laid over the drawing, which is what lets each
 * keep a 44 px target however small its symbol is and lets the keyboard reach it.
 *
 * Nothing here is finance (invariant 4): it places dots and groups neighbours.
 */
import type { Geometry, View } from "./geo";

export interface Size {
  readonly width: number;
  readonly height: number;
}

export interface Camera {
  readonly cx: number;
  readonly cy: number;
  /** pixels per projected unit */
  readonly scale: number;
}

/** How much closer than the whole country the camera may go. */
export const MAX_ZOOM = 60;
/** Smallest target of a marker or a control, in CSS pixels (WCAG 2.2 AAA 2.5.5, the owner's requirement). */
export const TARGET = 44;
/** Neighbours within this many pixels of each other share one cluster marker. */
export const CLUSTER_CELL = 56;
/** Two markers closer than this (centre to centre) are one cluster. */
const MERGE_PX = 44;

export const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));

/** The scale at which the whole country fits the frame with a small margin. */
export function fitScale(whole: View, size: Size, margin = 28): number {
  if (size.width <= 0 || size.height <= 0) return 1;
  return Math.min(
    Math.max(size.width - margin * 2, 1) / whole.width,
    Math.max(size.height - margin * 2, 1) / whole.height,
  );
}

export function wholeCamera(whole: View, size: Size): Camera {
  return { cx: whole.x + whole.width / 2, cy: whole.y + whole.height / 2, scale: fitScale(whole, size) };
}

/** Keep the camera centre inside the country and the scale between "whole country" and `MAX_ZOOM` times that. */
export function limitCamera(camera: Camera, whole: View, size: Size): Camera {
  const min = fitScale(whole, size);
  const scale = clamp(camera.scale, min, min * MAX_ZOOM);
  return {
    scale,
    cx: clamp(camera.cx, whole.x, whole.x + whole.width),
    cy: clamp(camera.cy, whole.y, whole.y + whole.height),
  };
}

export function toScreen(camera: Camera, size: Size, x: number, y: number): readonly [number, number] {
  return [(x - camera.cx) * camera.scale + size.width / 2, (y - camera.cy) * camera.scale + size.height / 2];
}

export function toWorld(camera: Camera, size: Size, sx: number, sy: number): readonly [number, number] {
  return [
    (sx - size.width / 2) / camera.scale + camera.cx,
    (sy - size.height / 2) / camera.scale + camera.cy,
  ];
}

/** The SVG `viewBox` that shows exactly the camera's window, so the drawing and the markers agree. */
export function viewBoxOf(camera: Camera, size: Size): string {
  const w = size.width / camera.scale;
  const h = size.height / camera.scale;
  return `${camera.cx - w / 2} ${camera.cy - h / 2} ${w} ${h}`;
}

/** Zoom by `factor` keeping the world point under screen point `(sx, sy)` where it is (wheel, pinch, double tap). */
export function zoomAt(
  camera: Camera,
  whole: View,
  size: Size,
  factor: number,
  sx: number,
  sy: number,
): Camera {
  const [wx, wy] = toWorld(camera, size, sx, sy);
  const next = limitCamera({ ...camera, scale: camera.scale * factor }, whole, size);
  return limitCamera(
    {
      scale: next.scale,
      cx: wx - (sx - size.width / 2) / next.scale,
      cy: wy - (sy - size.height / 2) / next.scale,
    },
    whole,
    size,
  );
}

export function panBy(camera: Camera, whole: View, size: Size, dxPx: number, dyPx: number): Camera {
  return limitCamera(
    { ...camera, cx: camera.cx - dxPx / camera.scale, cy: camera.cy - dyPx / camera.scale },
    whole,
    size,
  );
}

export interface Box {
  readonly x0: number;
  readonly y0: number;
  readonly x1: number;
  readonly y1: number;
}

/** The camera that shows `box` with `paddingPx` around it, never closer than `maxScale`. */
export function fitBox(box: Box, whole: View, size: Size, paddingPx = 96, maxScale?: number): Camera {
  const w = Math.max(box.x1 - box.x0, 1e-6);
  const h = Math.max(box.y1 - box.y0, 1e-6);
  const raw = Math.min(
    Math.max(size.width - paddingPx * 2, 1) / w,
    Math.max(size.height - paddingPx * 2, 1) / h,
  );
  const min = fitScale(whole, size);
  const ceiling = maxScale ?? min * MAX_ZOOM;
  return limitCamera(
    { cx: (box.x0 + box.x1) / 2, cy: (box.y0 + box.y1) / 2, scale: Math.min(raw, ceiling) },
    whole,
    size,
  );
}

export const sameCamera = (a: Camera, b: Camera, eps = 1e-6): boolean =>
  Math.abs(a.cx - b.cx) < eps && Math.abs(a.cy - b.cy) < eps && Math.abs(a.scale / b.scale - 1) < 1e-6;

/** An easing that starts and ends gently; `t` in 0..1. */
export const easeInOut = (t: number): number => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

/** The camera `t` of the way from `a` to `b`; the scale moves geometrically so a zoom feels even. */
export function lerpCamera(a: Camera, b: Camera, t: number): Camera {
  return {
    cx: a.cx + (b.cx - a.cx) * t,
    cy: a.cy + (b.cy - a.cy) * t,
    scale: a.scale * (b.scale / a.scale) ** t,
  };
}

// ------------------------------------------------------------------------------------------------ markers

export interface MarkerInput {
  readonly id: string;
  readonly x: number;
  readonly y: number;
  /** larger first: the heavier place keeps the label and the cluster's anchor */
  readonly weight: number;
}

export interface SingleMarker {
  readonly kind: "place";
  readonly id: string;
  readonly sx: number;
  readonly sy: number;
}

export interface ClusterMarker {
  readonly kind: "cluster";
  readonly key: string;
  readonly ids: readonly string[];
  readonly sx: number;
  readonly sy: number;
  /** the members' bounding box in projected units, to zoom into */
  readonly box: Box;
  /** every member sits at the same point: zooming cannot separate them */
  readonly inseparable: boolean;
}

export type Marker = SingleMarker | ClusterMarker;

/** A screen rectangle in frame pixels. */
export interface Rect {
  readonly x0: number;
  readonly y0: number;
  readonly x1: number;
  readonly y1: number;
}

const hits = (sx: number, sy: number, r: Rect): boolean =>
  sx + TARGET / 2 > r.x0 && sx - TARGET / 2 < r.x1 && sy + TARGET / 2 > r.y0 && sy - TARGET / 2 < r.y1;

/**
 * What the frame keeps for itself: the zoom controls in the corner and, while one is open, the preview. A marker
 * whose 44 px target would sit under either is not drawn (it could not be hit, and an overlapped target is an
 * accessibility defect); it comes back when the map is moved or the preview closed.
 */
export function reservedAreas(size: Size, preview: boolean): Rect[] {
  const out: Rect[] = [{ x0: size.width - 12 - 136, y0: 0, x1: size.width, y1: 12 + 3 * 44 + 2 * 8 + 8 }];
  if (preview) {
    out.push(
      size.width <= 640
        ? { x0: 0, y0: size.height * 0.4, x1: size.width, y1: size.height }
        : { x0: 0, y0: 0, x1: 12 + 336 + 8, y1: size.height },
    );
  }
  return out;
}

/**
 * Group markers that would overlap at this scale. The grid is anchored in the world, not on the screen, so
 * panning never regroups neighbours and zooming does, in one predictable way. A cell with one place is that
 * place; a cell with several is one cluster that remembers its members. Only markers inside the frame (plus
 * half a cell) are returned, so the page never holds hundreds of invisible buttons.
 */
export function clusterMarkers(
  inputs: readonly MarkerInput[],
  camera: Camera,
  size: Size,
  cell: number = CLUSTER_CELL,
  avoid: readonly Rect[] = [],
): Marker[] {
  const worldCell = cell / camera.scale;
  const cells = new Map<string, MarkerInput[]>();
  for (const input of inputs) {
    const key = `${Math.floor(input.x / worldCell)}:${Math.floor(input.y / worldCell)}`;
    const bucket = cells.get(key);
    if (bucket === undefined) cells.set(key, [input]);
    else bucket.push(input);
  }
  // Neighbouring cells can leave two centroids closer than a marker is wide: merge those too, so no two markers
  // ever overlap on screen (a symbol is at most 34 px across).
  let groups = [...cells.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([key, members]) => ({ key, members: [...members] }));
  const centre = (g: { members: MarkerInput[] }) => ({
    x: g.members.reduce((sum, m) => sum + m.x, 0) / g.members.length,
    y: g.members.reduce((sum, m) => sum + m.y, 0) / g.members.length,
  });
  const screenOf = (g: { members: MarkerInput[] }) => {
    const c = centre(g);
    return toScreen(camera, size, c.x, c.y);
  };
  for (let changed = true; changed;) {
    changed = false;
    for (let i = 0; i < groups.length && !changed; i += 1)
      for (let j = i + 1; j < groups.length && !changed; j += 1) {
        const a = groups[i];
        const b = groups[j];
        if (a === undefined || b === undefined) continue;
        const [ax, ay] = screenOf(a);
        const [bx, by] = screenOf(b);
        if (Math.hypot(ax - bx, ay - by) < MERGE_PX) {
          groups = groups
            .filter((_, k) => k !== j)
            .map((g, k) => (k === i ? { key: a.key, members: [...a.members, ...b.members] } : g));
          changed = true;
        }
      }
  }
  // A marker is a whole 44 px button: one that would be cut by the frame is not drawn until it is brought inside.
  const margin = -TARGET / 2;
  const out: Marker[] = [];
  for (const { key, members } of groups) {
    members.sort((a, b) => b.weight - a.weight || (a.id < b.id ? -1 : 1));
    const c = centre({ members });
    const [sx, sy] = toScreen(camera, size, c.x, c.y);
    if (sx < -margin || sy < -margin || sx > size.width + margin || sy > size.height + margin) continue;
    if (avoid.some((r) => hits(sx, sy, r))) continue;
    const first = members[0];
    if (first === undefined) continue;
    if (members.length === 1) {
      out.push({ kind: "place", id: first.id, sx, sy });
      continue;
    }
    const xs = members.map((m) => m.x);
    const ys = members.map((m) => m.y);
    const box = { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
    out.push({
      kind: "cluster",
      key,
      ids: members.map((m) => m.id),
      sx,
      sy,
      box,
      inseparable: box.x1 - box.x0 < 1e-9 && box.y1 - box.y0 < 1e-9,
    });
  }
  return out;
}

export interface LabelCandidate {
  readonly id: string;
  readonly sx: number;
  readonly sy: number;
  readonly text: string;
  readonly weight: number;
}

export interface PlacedLabel {
  readonly id: string;
  readonly left: number;
  readonly top: number;
  readonly side: "right" | "left";
}

const LABEL_HEIGHT = 18;
const CHAR_WIDTH = 6.6;
const LABEL_GAP = 26;

const overlaps = (
  a: readonly [number, number, number, number],
  b: readonly [number, number, number, number],
) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];

/**
 * Names beside their markers, heaviest first, skipping any that would cover another label or a marker. At the
 * whole-country scale only a handful fit; zooming in makes room for more, which is the point.
 */
export function placeLabels(
  candidates: readonly LabelCandidate[],
  markerPositions: readonly (readonly [number, number])[],
  size: Size,
  maxLabels = 60,
): PlacedLabel[] {
  const taken: [number, number, number, number][] = markerPositions.map(([x, y]) => [
    x - 22,
    y - 22,
    x + 22,
    y + 22,
  ]);
  const placed: PlacedLabel[] = [];
  const sorted = [...candidates].sort((a, b) => b.weight - a.weight || (a.id < b.id ? -1 : 1));
  for (const c of sorted) {
    if (placed.length >= maxLabels) break;
    const width = c.text.length * CHAR_WIDTH + 8;
    const sides: ("right" | "left")[] = c.sx + LABEL_GAP + width <= size.width ? ["right", "left"] : ["left"];
    for (const side of sides) {
      const left = side === "right" ? c.sx + LABEL_GAP : c.sx - LABEL_GAP - width;
      const top = c.sy - LABEL_HEIGHT / 2;
      const rect: [number, number, number, number] = [left, top, left + width, top + LABEL_HEIGHT];
      if (rect[0] < 0 || rect[2] > size.width || rect[1] < 0 || rect[3] > size.height) continue;
      if (taken.some((t) => overlaps(rect, t))) continue; // a label never covers a marker or another label
      taken.push(rect);
      placed.push({ id: c.id, left, top, side });
      break;
    }
  }
  return placed;
}

/** The centroid of a mapped place in projected units, or null when the place has no outline point. */
export function placePoint(
  geometry: Geometry,
  teryt: string | null,
  project: (p: readonly [number, number]) => readonly [number, number],
): readonly [number, number] | null {
  if (teryt === null) return null;
  const point = geometry.points.get(teryt);
  return point === undefined ? null : project(point);
}

/** Does `id` sit inside the frame with `margin` pixels to spare? Used to decide whether a selection needs a pan. */
export function isVisible(camera: Camera, size: Size, x: number, y: number, margin = 24): boolean {
  const [sx, sy] = toScreen(camera, size, x, y);
  return sx >= margin && sy >= margin && sx <= size.width - margin && sy <= size.height - margin;
}
