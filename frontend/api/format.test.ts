import { describe, expect, it } from "vitest";

import {
  formatAnalyses,
  formatArea,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatMoney,
  formatRatio,
  formatReports,
  NOT_COMPUTED,
  plural,
} from "./format";

const NBSP = " ";
const MINUS = "−";

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
