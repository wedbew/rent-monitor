import { describe, expect, it } from "vitest";

import {
  createNumberFormat,
  formatAnalyses,
  formatCount,
  formatPercent,
  formatArea,
  formatPricePerArea,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatMoney,
  formatPrice,
  formatRatio,
  formatReports,
  NOT_COMPUTED,
  plural,
} from "./format";

const NBSP = " ";
const MINUS = "−";

describe("formatPrice", () => {
  it("shows whole złoty plainly and keeps grosze of a fractional price", () => {
    expect(formatPrice("10")).toBe(`10${NBSP}zł`);
    expect(formatPrice("40.00")).toBe(`40${NBSP}zł`);
    expect(formatPrice("10.49")).toBe(`10,49${NBSP}zł`);
    expect(formatPrice("70.5")).toBe(`70,50${NBSP}zł`);
    expect(formatPrice("1234")).toBe(`1${NBSP}234${NBSP}zł`);
  });

  it("never throws and never appends a unit to a fallback", () => {
    expect(formatPrice(null)).toBe(NOT_COMPUTED);
    expect(formatPrice("abc")).toBe(NOT_COMPUTED);
    expect(formatPrice("-3")).toBe(formatMoney("-3", { decimals: 2 }));
  });
});

describe("formatMoney", () => {
  it("formats złoty with grosze and a non-breaking space group separator", () => {
    expect(formatMoney("450000.00")).toBe(`450${NBSP}000,00${NBSP}zł`);
    expect(formatMoney("1234")).toBe(`1${NBSP}234,00${NBSP}zł`);
    expect(formatMoney("0.5")).toBe(`0,50${NBSP}zł`);
  });

  it("keeps 0 as 0 and unknown as unknown", () => {
    expect(formatMoney("0")).toBe(`0,00${NBSP}zł`);
    expect(formatMoney("0.00")).toBe(`0,00${NBSP}zł`);
    expect(formatMoney(null)).toBe(NOT_COMPUTED);
    expect(formatMoney(undefined)).toBe(NOT_COMPUTED);
    expect(formatMoney("not a number")).toBe(NOT_COMPUTED);
    expect(formatMoney("")).toBe(NOT_COMPUTED);
  });

  it("does not lose precision on values a binary float cannot hold", () => {
    expect(formatMoney("123456789012345678901234.56")).toBe(
      `123${NBSP}456${NBSP}789${NBSP}012${NBSP}345${NBSP}678${NBSP}901${NBSP}234,56${NBSP}zł`,
    );
    expect(formatMoney("9007199254740993")).toBe(
      `9${NBSP}007${NBSP}199${NBSP}254${NBSP}740${NBSP}993,00${NBSP}zł`,
    );
    expect(formatMoney("0.30")).toBe(`0,30${NBSP}zł`);
  });

  it("rounds half away from zero, in decimal", () => {
    expect(formatMoney("1.005")).toBe(`1,01${NBSP}zł`);
    expect(formatMoney("2.675")).toBe(`2,68${NBSP}zł`);
    expect(formatMoney("1.004")).toBe(`1,00${NBSP}zł`);
    expect(formatMoney("-1.005")).toBe(`${MINUS}1,01${NBSP}zł`);
    expect(formatMoney("999999.995")).toBe(`1${NBSP}000${NBSP}000,00${NBSP}zł`);
  });

  it("shows negatives with a real minus and never a negative zero", () => {
    expect(formatMoney("-450.5")).toBe(`${MINUS}450,50${NBSP}zł`);
    expect(formatMoney("-0.001")).toBe(`0,00${NBSP}zł`);
  });

  it("can round to whole złoty for headline figures", () => {
    expect(formatMoney("450000.49", { decimals: 0 })).toBe(`450${NBSP}000${NBSP}zł`);
    expect(formatMoney("450000.50", { decimals: 0 })).toBe(`450${NBSP}001${NBSP}zł`);
  });
});

describe("formatRatio", () => {
  it("turns a ratio into a percentage", () => {
    expect(formatRatio("0.0734")).toBe("7,3%");
    expect(formatRatio("0.0734", 2)).toBe("7,34%");
    expect(formatRatio("-0.0046")).toBe(`${MINUS}0,5%`);
    expect(formatRatio("1")).toBe("100,0%");
    expect(formatRatio("0")).toBe("0,0%");
    expect(formatRatio("0.5")).toBe("50,0%");
  });
  it("keeps unknown as unknown", () => {
    expect(formatRatio(null)).toBe(NOT_COMPUTED);
    expect(formatRatio("abc")).toBe(NOT_COMPUTED);
  });
});

describe("formatDecimal and formatArea", () => {
  it("drops trailing zeros and uses a decimal comma", () => {
    expect(formatDecimal("74.90")).toBe("74,9");
    expect(formatDecimal("48.5")).toBe("48,5");
    expect(formatDecimal("62.0")).toBe("62");
    expect(formatDecimal("1234.567", 2)).toBe(`1${NBSP}234,57`);
    expect(formatDecimal(null)).toBe(NOT_COMPUTED);
  });
  it("adds the unit", () => {
    expect(formatArea("74.9")).toBe(`74,9${NBSP}m²`);
    expect(formatArea(null)).toBe(NOT_COMPUTED);
  });
});

describe("dates", () => {
  it("are shown in Europe/Warsaw, whatever the browser zone", () => {
    expect(formatDate("2026-10-31T23:30:00Z")).toBe("1 listopada 2026"); // CET, already the next day
    expect(formatDate("2026-07-01T22:30:00Z")).toBe("2 lipca 2026"); // CEST
    expect(formatDateTime("2026-10-01T10:00:00Z")).toMatch(/1 października 2026.*12:00/);
  });
  it("show a dash for a missing or invalid time", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDateTime("yesterday")).toBe("—");
  });
});

describe("Polish plurals", () => {
  const forms = ["raport", "raporty", "raportów"] as const;
  it.each([
    [0, "raportów"],
    [1, "raport"],
    [2, "raporty"],
    [4, "raporty"],
    [5, "raportów"],
    [11, "raportów"],
    [12, "raportów"],
    [14, "raportów"],
    [21, "raportów"],
    [22, "raporty"],
    [24, "raporty"],
    [25, "raportów"],
    [112, "raportów"],
    [122, "raporty"],
  ])("%i -> %s", (count, expected) => {
    expect(plural(count, forms)).toBe(expected);
  });
  it("formats counts", () => {
    expect(formatReports(5)).toBe(`5${NBSP}raportów`);
    expect(formatAnalyses(2)).toBe(`2${NBSP}analizy`);
  });
});

/**
 * Audit F07 and F16: every displayed number goes through Intl for its layout, digits stay exact, and bad input
 * never throws, never gets a unit and never shows a raw number.
 */
describe("Intl layout with exact digits", () => {
  it("groups counts like every other number and picks the Polish plural form", () => {
    expect(formatReports(1234)).toBe(`1${NBSP}234${NBSP}raporty`);
    expect(formatAnalyses(1)).toBe(`1${NBSP}analiza`);
    for (const [count, form] of [
      [12, "raportów"],
      [22, "raporty"],
      [112, "raportów"],
      [1_000_002, "raporty"],
    ] as const)
      expect(formatReports(count)).toMatch(new RegExp(`${NBSP}${form}$`));
    expect(formatCount(1_000_000)).toBe(`1${NBSP}000${NBSP}000`);
  });

  it("refuses a count that is not a whole number instead of printing it raw", () => {
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, 1.5, 2 ** 60]) {
      expect(formatCount(bad)).toBe(NOT_COMPUTED);
      expect(formatReports(bad)).toBe(NOT_COMPUTED);
    }
  });

  it("formats whole percentages for progress", () => {
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(35)).toBe("35%");
    expect(formatPercent(100)).toBe("100%");
    expect(formatPercent(Number.NaN)).toBe(NOT_COMPUTED);
  });

  it("never puts a unit on an unknown or unreadable area", () => {
    expect(formatArea("abc")).toBe(NOT_COMPUTED);
    expect(formatArea("")).toBe(NOT_COMPUTED);
    expect(formatArea("1e3")).toBe(NOT_COMPUTED);
  });

  it("accepts only bounded integer precision and never throws on another", () => {
    for (const digits of [Number.NaN, -1, 2.5, 99, Number.POSITIVE_INFINITY]) {
      expect(() => formatRatio("0.0734", digits)).not.toThrow();
      expect(formatRatio("0.0734", digits)).toBe("7,3%");
      expect(formatDecimal("74.95", digits)).toBe("74,95");
    }
    expect(formatRatio("0.0734", 0)).toBe("7%");
    expect(formatRatio("0.07345678", 6)).toBe("7,345678%");
  });

  it("refuses an absurdly long input instead of doing unbounded work", () => {
    expect(formatMoney("9".repeat(65))).toBe(NOT_COMPUTED);
    expect(formatMoney("9".repeat(60))).toMatch(/zł$/);
  });

  it("negative zero rounds to plain zero in every style", () => {
    expect(formatRatio("-0.00001")).toBe("0,0%");
    expect(formatDecimal("-0.001")).toBe("0");
  });

  it("takes separators, symbols and their order from the locale (a second locale)", () => {
    const en = createNumberFormat("en-US");
    expect(en.compose("currency", true, 123456n, 2)).toBe(`${MINUS}PLN${NBSP}1,234.56`);
    expect(en.compose("percent", false, 73n, 1)).toBe("7.3%");
    expect(en.compose("decimal", false, 1234567n, 3)).toBe("1,234.567");
    expect(en.plural(1, ["one", "few", "many"])).toBe("one");
    expect(en.plural(3, ["one", "few", "many"])).toBe("many"); // English has no "few"
    expect(en.formatCount(1234)).toBe("1,234");
  });
});

describe("formatPricePerArea", () => {
  it("shows złoty per square metre with the exact decimals", () => {
    expect(formatPricePerArea("45.50")).toBe("45,50\u00a0zł/m²");
    expect(formatPricePerArea("1234.5")).toBe("1\u00a0234,50\u00a0zł/m²");
  });

  it("never appends the unit to a fallback", () => {
    expect(formatPricePerArea(null)).toBe("nie obliczono");
    expect(formatPricePerArea(undefined)).toBe("nie obliczono");
    expect(formatPricePerArea("abc")).toBe("nie obliczono");
  });
});
