import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BarCompare } from "./BarCompare";

describe("BarCompare", () => {
  it("keeps the quartile band inside the track even when it ends beyond the largest value", () => {
    const { container } = render(
      <BarCompare
        label="x"
        items={[{ id: "a", name: "A", value: 70, valueText: "70", low: 60, high: 90 }]}
      />,
    );
    const range = container.querySelector<HTMLElement>("[class*=barRange]");
    const left = Number.parseInt(range?.style.left ?? "0", 10);
    const width = Number.parseInt(range?.style.width ?? "0", 10);
    expect(left + width).toBeLessThanOrEqual(100);
    const fill = container.querySelector<HTMLElement>("[class*=barFill]");
    expect(Number.parseInt(fill?.style.width ?? "0", 10)).toBeLessThan(100);
  });
});
