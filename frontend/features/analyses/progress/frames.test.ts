import { describe, expect, it } from "vitest";

import { isTerminal, parseFrame, stageLabel } from "./frames";

const data = (body: object) => JSON.stringify(body);

describe("parseFrame", () => {
  it("reads a progress frame: stage and percentage are the server's", () => {
    expect(
      parseFrame("progress", "118", data({ audit_id: "x", stage: "fetch", pct: 5, message: "" })),
    ).toEqual({
      id: 118,
      kind: "progress",
      stage: "fetch",
      pct: 5,
      code: null,
      status: null,
    });
  });

  it("reads the terminal frames with their status and error code", () => {
    const done = parseFrame("done", "125", data({ stage: "persist", pct: 100, status: "succeeded" }));
    expect(done).toMatchObject({ kind: "done", status: "succeeded", pct: 100 });
    const error = parseFrame(
      "error",
      "128",
      data({ code: "RENT_NOT_DEAL", pct: null, stage: null, status: "rejected" }),
    );
    expect(error).toMatchObject({
      kind: "error",
      code: "RENT_NOT_DEAL",
      status: "rejected",
      pct: null,
      stage: null,
    });
    expect(done !== null && isTerminal(done)).toBe(true);
    const progress = parseFrame("progress", "1", "{}");
    expect(progress !== null && isTerminal(progress)).toBe(false);
  });

  it("keeps a synthesised terminal frame (no id) and drops a malformed id", () => {
    expect(parseFrame("done", "", data({ status: "succeeded" }))?.id).toBeNull();
    expect(parseFrame("done", "12abc", data({ status: "succeeded" }))?.id).toBeNull();
  });

  it("drops what does not fit instead of guessing", () => {
    expect(parseFrame("message", "1", data({}))).toBeNull();
    expect(parseFrame("progress", "1", "not json")).toBeNull();
    expect(parseFrame("progress", "1", "[1,2]")).toBeNull();
    expect(parseFrame("progress", "1", "null")).toBeNull();
    expect(parseFrame("progress", "1", undefined)).toBeNull();
    expect(parseFrame("progress", "1", "x".repeat(5000))).toBeNull();
  });

  it("ignores out-of-range percentages and over-long strings", () => {
    expect(parseFrame("progress", "1", data({ pct: 140 }))?.pct).toBeNull();
    expect(parseFrame("progress", "1", data({ pct: -1 }))?.pct).toBeNull();
    expect(parseFrame("progress", "1", data({ pct: 12.5 }))?.pct).toBeNull();
    expect(parseFrame("progress", "1", data({ stage: "s".repeat(200) }))?.stage).toBeNull();
  });
});

describe("stageLabel", () => {
  it("names every stage the pipeline reports and never shows an unknown raw name", () => {
    for (const stage of [
      "fetch",
      "extract",
      "context",
      "vision",
      "ocr",
      "anchors",
      "synthesize",
      "persist",
    ]) {
      expect(stageLabel(stage)).not.toBe("Przetwarzanie");
    }
    expect(stageLabel("new_stage")).toBe("Przetwarzanie");
    expect(stageLabel(null)).toBe("Przetwarzanie");
  });
});
