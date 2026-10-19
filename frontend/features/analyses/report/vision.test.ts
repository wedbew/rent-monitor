import { describe, expect, it } from "vitest";

import { readVisionEvidence, stripControls } from "./vision";

const full = {
  equipment: [
    {
      item: "klimatyzacja",
      media_ordinal: 0,
      provenance: "photo",
      sale_status: "included",
      confidence: "0.85",
    },
    {
      item: "kuchenka indukcyjna",
      media_ordinal: 3,
      provenance: "floor_plan",
      sale_status: "visible_only",
      confidence: "0.4",
    },
    {
      item: "szafa",
      media_ordinal: null,
      provenance: "unattributed",
      sale_status: "unknown",
      confidence: "1",
    },
  ],
  floor_plan_text: "Salon 24 m2",
  notes: "Zdjęcia jasne.",
};

describe("readVisionEvidence", () => {
  it("reports a failed vision analysis only when the audit is degraded", () => {
    expect(readVisionEvidence(null, true)).toEqual({ kind: "failed" });
    expect(readVisionEvidence(null, false)).toEqual({ kind: "not-run" });
    expect(readVisionEvidence(undefined, true)).toEqual({ kind: "failed" });
  });

  it("treats a vision record without the evidence fields as an older report", () => {
    const older = { model: "m", prompt_version: "vision-v1", photos_total: 2, photos_excluded: 0 };
    expect(readVisionEvidence(older, false)).toEqual({ kind: "older" });
  });

  it("reads equipment with provenance, sale status, confidence and text", () => {
    const evidence = readVisionEvidence(full, false);
    expect(evidence.kind).toBe("ready");
    if (evidence.kind !== "ready") return;
    expect(evidence.equipment).toEqual([
      {
        item: "klimatyzacja",
        mediaOrdinal: 0,
        provenance: "photo",
        saleStatus: "included",
        confidence: "0.85",
      },
      {
        item: "kuchenka indukcyjna",
        mediaOrdinal: 3,
        provenance: "floor_plan",
        saleStatus: "visible_only",
        confidence: "0.4",
      },
      {
        item: "szafa",
        mediaOrdinal: null,
        provenance: "unattributed",
        saleStatus: "unknown",
        confidence: "1",
      },
    ]);
    expect(evidence.floorPlanText).toBe("Salon 24 m2");
    expect(evidence.notes).toBe("Zdjęcia jasne.");
    expect(evidence.skipped).toBe(0);
  });

  it("is empty when the evidence fields hold nothing", () => {
    expect(readVisionEvidence({ equipment: [], floor_plan_text: null, notes: null }, false)).toEqual({
      kind: "empty",
    });
  });

  it("drops malformed items, counts them and never throws", () => {
    const hostile = {
      equipment: [
        "tekst zamiast obiektu",
        { item: "", provenance: "photo" },
        {
          item: "<img src=x onerror=alert(1)>",
          media_ordinal: -2,
          provenance: "video",
          sale_status: 9,
          confidence: "NaN",
        },
        null,
      ],
      floor_plan_text: 42,
      notes: "   ",
    };
    const evidence = readVisionEvidence(hostile, false);
    expect(evidence.kind).toBe("ready");
    if (evidence.kind !== "ready") return;
    expect(evidence.skipped).toBe(3);
    expect(evidence.equipment).toEqual([
      {
        item: "<img src=x onerror=alert(1)>",
        mediaOrdinal: null,
        provenance: "unattributed",
        saleStatus: "unknown",
        confidence: null,
      },
    ]);
    expect(evidence.floorPlanText).toBeNull();
    expect(evidence.notes).toBeNull();
  });

  it("says a vision value that is not an object is unreadable", () => {
    expect(readVisionEvidence("tekst", false)).toEqual({ kind: "unreadable" });
    expect(readVisionEvidence([], false)).toEqual({ kind: "unreadable" });
  });

  it("caps long text and bounds the equipment count", () => {
    const many = Array.from({ length: 45 }, (_, i) => ({ item: `poz ${i}`, provenance: "photo" }));
    const evidence = readVisionEvidence({ equipment: many, floor_plan_text: "x".repeat(4001) }, false);
    expect(evidence.kind).toBe("ready");
    if (evidence.kind !== "ready") return;
    expect(evidence.equipment).toHaveLength(40);
    expect(evidence.skipped).toBe(5);
    expect(evidence.floorPlanText).toBeNull();
  });
});

describe("stripControls", () => {
  it("removes control characters but keeps line breaks and tabs", () => {
    expect(stripControls("a\u0000b\u001bc\nd\te")).toBe("abc\nd\te");
  });
});
