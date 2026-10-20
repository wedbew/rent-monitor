import { describe, expect, it } from "vitest";

import {
  clusterMarkers,
  easeInOut,
  fitBox,
  fitScale,
  isVisible,
  lerpCamera,
  limitCamera,
  MAX_ZOOM,
  panBy,
  placeLabels,
  toScreen,
  toWorld,
  viewBoxOf,
  wholeCamera,
  zoomAt,
} from "./mapCamera";

const WHOLE = { x: 0, y: 0, width: 400, height: 300 };
const SIZE = { width: 800, height: 600 };

describe("camera", () => {
  it("fits the whole country and maps world to screen and back", () => {
    const cam = wholeCamera(WHOLE, SIZE);
    expect(cam.scale).toBeCloseTo((600 - 56) / 300, 6); // the height is the tight side
    const [sx, sy] = toScreen(cam, SIZE, 200, 150);
    expect([sx, sy]).toEqual([400, 300]); // the centre of the country is the centre of the frame
    const [wx, wy] = toWorld(cam, SIZE, sx, sy);
    expect([wx, wy]).toEqual([200, 150]);
  });

  it("draws exactly the camera's window as the SVG viewBox", () => {
    const cam = { cx: 100, cy: 50, scale: 4 };
    expect(viewBoxOf(cam, SIZE)).toBe("0 -25 200 150");
  });

  it("zooms about the point under the pointer and never past the limits", () => {
    const whole = wholeCamera(WHOLE, SIZE);
    const zoomed = zoomAt(whole, WHOLE, SIZE, 2, 600, 300);
    const [wx] = toWorld(whole, SIZE, 600, 300);
    const [after] = toWorld(zoomed, SIZE, 600, 300);
    expect(after).toBeCloseTo(wx, 6); // the point under the pointer did not move
    expect(zoomed.scale).toBeCloseTo(whole.scale * 2, 6);
    expect(zoomAt(whole, WHOLE, SIZE, 0.01, 0, 0).scale).toBeCloseTo(whole.scale, 6); // not past "whole"
    const max = limitCamera({ ...whole, scale: 1e9 }, WHOLE, SIZE);
    expect(max.scale).toBeCloseTo(fitScale(WHOLE, SIZE) * MAX_ZOOM, 4);
  });

  it("keeps the centre inside the country when panning", () => {
    const cam = { cx: 390, cy: 10, scale: 5 };
    const moved = panBy(cam, WHOLE, SIZE, -1000, 1000);
    expect(moved.cx).toBeLessThanOrEqual(400);
    expect(moved.cy).toBeGreaterThanOrEqual(0);
  });

  it("fits a box with padding, no closer than the ceiling", () => {
    const cam = fitBox({ x0: 100, y0: 100, x1: 140, y1: 120 }, WHOLE, SIZE, 100);
    const [sx0] = toScreen(cam, SIZE, 100, 100);
    const [sx1] = toScreen(cam, SIZE, 140, 100);
    expect(sx0).toBeGreaterThanOrEqual(100 - 1e-6);
    expect(sx1).toBeLessThanOrEqual(700 + 1e-6);
    const point = fitBox({ x0: 50, y0: 50, x1: 50, y1: 50 }, WHOLE, SIZE, 100, 30);
    expect(point.scale).toBe(30);
    expect([point.cx, point.cy]).toEqual([50, 50]);
  });

  it("interpolates the scale geometrically and eases gently at both ends", () => {
    const a = { cx: 0, cy: 0, scale: 1 };
    const b = { cx: 10, cy: 20, scale: 16 };
    expect(lerpCamera(a, b, 0.5).scale).toBeCloseTo(4, 9);
    expect(lerpCamera(a, b, 1)).toEqual(b);
    expect(easeInOut(0)).toBe(0);
    expect(easeInOut(1)).toBe(1);
    expect(easeInOut(0.1)).toBeLessThan(0.1); // slow start
  });

  it("knows whether a point is inside the frame", () => {
    const cam = wholeCamera(WHOLE, SIZE);
    expect(isVisible(cam, SIZE, 200, 150)).toBe(true);
    expect(isVisible({ ...cam, scale: cam.scale * 20 }, SIZE, 0, 0)).toBe(false);
  });
});

describe("clustering", () => {
  const cam = { cx: 100, cy: 100, scale: 1 };
  const size = { width: 400, height: 400 };
  const near = [
    { id: "a", x: 100, y: 100, weight: 5 },
    { id: "b", x: 110, y: 104, weight: 9 }, // within one 56 px cell of "a" at scale 1
    { id: "c", x: 180, y: 180, weight: 1 },
  ];

  it("groups neighbours that would overlap and keeps lone places", () => {
    const markers = clusterMarkers(near, cam, size);
    const cluster = markers.find((m) => m.kind === "cluster");
    expect(cluster?.kind === "cluster" && [...cluster.ids]).toEqual(["b", "a"]); // heaviest first
    expect(markers.filter((m) => m.kind === "place").map((m) => (m.kind === "place" ? m.id : ""))).toEqual([
      "c",
    ]);
  });

  it("separates them again when the camera zooms in", () => {
    const markers = clusterMarkers(near, { ...cam, scale: 20 }, { width: 4000, height: 4000 });
    expect(markers.every((m) => m.kind === "place")).toBe(true);
  });

  it("flags a cluster whose members share one point as inseparable", () => {
    const twins = [
      { id: "x", x: 50, y: 50, weight: 1 },
      { id: "y", x: 50, y: 50, weight: 1 },
    ];
    const [m] = clusterMarkers(twins, { cx: 50, cy: 50, scale: 100 }, size);
    expect(m?.kind === "cluster" && m.inseparable).toBe(true);
  });

  it("returns only what is inside the frame", () => {
    const far = [{ id: "far", x: 5000, y: 5000, weight: 1 }];
    expect(clusterMarkers(far, cam, size)).toEqual([]);
  });

  it("does not regroup when only the pan changes", () => {
    const a = clusterMarkers(near, cam, size).map((m) =>
      m.kind === "place" ? m.id : [...m.ids].sort().join("+"),
    );
    const b = clusterMarkers(near, { ...cam, cx: 101 }, size).map((m) =>
      m.kind === "place" ? m.id : [...m.ids].sort().join("+"),
    );
    expect(b).toEqual(a);
  });
});

describe("labels", () => {
  it("never lets a label cover a marker or another label, using the free side of each marker", () => {
    const size = { width: 600, height: 300 };
    const candidates = [
      { id: "big", sx: 100, sy: 100, text: "Warszawa", weight: 10 },
      { id: "close", sx: 110, sy: 104, text: "Piaseczno", weight: 1 },
      { id: "alone", sx: 400, sy: 200, text: "Kielce", weight: 2 },
    ];
    const placed = placeLabels(
      candidates,
      candidates.map((c) => [c.sx, c.sy] as const),
      size,
    );
    expect(placed.map((p) => p.id)).toEqual(["big", "alone", "close"]); // heaviest first
    // the neighbour sits on the right of "big", so "big" goes to its left and "close" to its right
    expect(Object.fromEntries(placed.map((p) => [p.id, p.side]))).toEqual({
      big: "left",
      alone: "right",
      close: "right",
    });
    const boxes = placed.map((p) => {
      const c = candidates.find((x) => x.id === p.id);
      return [p.left, p.top, p.left + (c?.text.length ?? 0) * 6.6 + 8, p.top + 18] as const;
    });
    for (const [i, a] of boxes.entries())
      for (const b of boxes.slice(i + 1))
        expect(a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]).toBe(false);
  });

  it("drops a label when no side is free", () => {
    const size = { width: 120, height: 100 };
    const crowded = [
      { id: "a", sx: 40, sy: 50, text: "Aaaaaaaaa", weight: 3 },
      { id: "b", sx: 50, sy: 52, text: "Bbbbbbbbb", weight: 2 },
      { id: "c", sx: 60, sy: 54, text: "Ccccccccc", weight: 1 },
    ];
    const placed = placeLabels(
      crowded,
      crowded.map((c) => [c.sx, c.sy] as const),
      size,
    );
    expect(placed.length).toBeLessThan(3);
  });

  it("flips a label to the left at the right edge and drops one that fits nowhere", () => {
    const size = { width: 200, height: 100 };
    const edge = [{ id: "edge", sx: 190, sy: 50, text: "Gdynia", weight: 1 }];
    expect(placeLabels(edge, [[190, 50]], size)[0]?.side).toBe("left");
    const tiny = [{ id: "x", sx: 100, sy: 50, text: "Bardzo długa nazwa miejscowości", weight: 1 }];
    expect(placeLabels(tiny, [[100, 50]], { width: 80, height: 100 })).toEqual([]);
  });
});
