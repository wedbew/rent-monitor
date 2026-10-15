import { describe, expect, it } from "vitest";

import { listingRefError, MAX_LISTING_REF } from "./NewAnalysisPage";

describe("listingRefError", () => {
  it("asks for something when the field is empty or blank", () => {
    expect(listingRefError("")).toBe("Wklej adres ogłoszenia lub jego numer.");
    expect(listingRefError("   \n")).toBe("Wklej adres ogłoszenia lub jego numer.");
  });

  it("accepts anything the server may accept (a URL, an id): it is the server's call", () => {
    expect(listingRefError("https://www.otodom.pl/pl/oferta/x-ID4abcd")).toBeNull();
    expect(listingRefError("ID4abcd")).toBeNull();
    expect(listingRefError("  ID4abcd  ")).toBeNull();
    expect(listingRefError("https://example.test/nie-otodom")).toBeNull();
  });

  it("refuses what the API would refuse for length, counted in characters after trimming", () => {
    expect(listingRefError("a".repeat(MAX_LISTING_REF))).toBeNull();
    expect(listingRefError(` ${"a".repeat(MAX_LISTING_REF)} `)).toBeNull();
    expect(listingRefError("a".repeat(MAX_LISTING_REF + 1))).toBe(
      `Adres może mieć najwyżej ${MAX_LISTING_REF} znaków.`,
    );
    expect(listingRefError("ł".repeat(MAX_LISTING_REF))).toBeNull();
  });
});
