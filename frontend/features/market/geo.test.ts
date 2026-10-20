import { describe, expect, it } from "vitest";

import { classify, classRanges, fullView, pathOf, panView, parseGeometry, project, zoomView } from "./geo";

const ring = [
  [20, 50],
  [21, 50],
  [21, 51],
  [20, 50],
] as const;
const good = { bbox: [14, 49, 24, 55], gminas: { "1007013": [ring] }, points: { "1007013": [20.5, 50.4] } };

describe("parseGeometry", () => {
  it("accepts the file the build script writes", () => {
    const g = parseGeometry(good);
    expect(g?.gminas.get("1007013")).toHaveLength(1);
    expect(g?.points.get("1007013")).toEqual([20.5, 50.4]);
  });
  it.each([
    ["not an object", 5],
    ["a short bbox", { ...good, bbox: [1, 2, 3] }],
    ["a name instead of a TERYT code", { ...good, gminas: { Torun: [ring] } }],
    ["a ring that is not closed enough to draw", { ...good, gminas: { "1007013": [[[1, 2]]] } }],
    ["a non-finite coordinate", { ...good, points: { "1007013": [Infinity, 1] } }],
  ])("refuses %s", (_name, raw) => {
    expect(parseGeometry(raw)).toBeNull();
  });
});

describe("view helpers", () => {
  const whole = fullView([14, 49, 24, 55]);
  it("puts north up and keeps a positive size", () => {
    expect(whole.width).toBeGreaterThan(0);
    expect(project([20, 55])[1]).toBeLessThan(project([20, 49])[1]);
  });
  it("draws rings as closed paths", () => {
    expect(pathOf([ring])).toMatch(/^M.*Z$/);
  });
  it("zooms about the centre within limits and pans without leaving the country", () => {
    const zoomed = zoomView(whole, whole, 2);
    expect(zoomed.width).toBeCloseTo(whole.width / 2);
    expect(zoomView(whole, whole, 0.1).width).toBe(whole.width);
    expect(zoomView(whole, whole, 1000).width).toBeCloseTo(whole.width / 40);
    expect(panView(zoomed, whole, -1e6, -1e6).x).toBe(whole.x);
    expect(panView(zoomed, whole, 1e6, 1e6).x + zoomed.width).toBeCloseTo(whole.x + whole.width);
  });
});

describe("classes", () => {
  it("gives equal-count classes and leaves a missing value unclassified", () => {
    const out = classify([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, null]);
    expect(out.at(-1)).toBeNull();
    expect(out[0]).toBe(0);
    expect(out[9]).toBe(4);
    expect(classify([null, null])).toEqual([null, null]);
  });
  it("describes each class by its own smallest and largest value", () => {
    expect(classRanges([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])).toEqual([
      [1, 2],
      [3, 4],
      [5, 6],
      [7, 8],
      [9, 10],
    ]);
  });
});
