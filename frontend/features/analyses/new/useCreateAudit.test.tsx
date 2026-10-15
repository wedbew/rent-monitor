import { describe, expect, it } from "vitest";

import { ApiError, TransportError } from "../../../api/errors";
import { advanceSessionGeneration } from "../../../shell/tenant";
import { createRun, RUN_AUDIT_ID } from "../../../test/scenarios";
import { useScenario } from "../../../test/handlers";
import { reconcileAfterAmbiguousFailure, submission } from "./useCreateAudit";

const REF = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-ID4abcd";

/** A recent analysis of the very same listing, made by an EARLIER request (another key). */
const earlierOfSameListing = {
  audit_id: "00000000-0000-4000-8000-0000000000a1",
  otodom_id: "ID4abcd",
  status: "queued" as const,
  error_code: null,
  created_at: new Date().toISOString(),
  finished_at: null,
  grade: null,
  asking_price_pln: null,
  max_bid_pln: null,
};

describe("submission", () => {
  it("gives every new submission its own request key", () => {
    const a = submission(REF);
    const b = submission(REF);
    expect(a.requestKey).toMatch(/^[0-9a-f-]{36}$/);
    expect(b.requestKey).not.toBe(a.requestKey);
  });

  it("sending the same listing again after a lost answer is the SAME submission (same key)", () => {
    const lost = submission(REF);
    expect(submission(REF, lost)).toBe(lost);
    expect(submission("ID9other", lost).requestKey).not.toBe(lost.requestKey); // another listing: new request
  });

  it("a submission from an earlier session is never reused", () => {
    const lost = submission(REF);
    advanceSessionGeneration();
    expect(submission(REF, lost).requestKey).not.toBe(lost.requestKey);
  });
});

/**
 * Audit F05: recovery used to match the listing within a time window, so an earlier analysis of the same listing
 * could be reported as this request. It now asks the server about THIS request's key and nothing else.
 */
describe("reconcileAfterAmbiguousFailure", () => {
  it("does nothing for an answer the API gave: it said what happened", async () => {
    const s = submission(REF);
    expect(await reconcileAfterAmbiguousFailure(new ApiError(402, null), s)).toBeNull();
    expect(await reconcileAfterAmbiguousFailure(new Error("x"), s)).toBeNull();
    expect(await reconcileAfterAmbiguousFailure(new TransportError("aborted"), s)).toBeNull();
  });

  it("finds the audit THIS request created, by its key", async () => {
    const run = createRun({ post: { status: 0, networkError: true }, lostAnswer: true });
    useScenario(run);
    const s = submission(REF);
    await fetch(new URL("/api/audits", window.location.origin), {
      method: "POST",
      headers: { "Idempotency-Key": s.requestKey, "content-type": "application/json" },
      body: "{}",
    }).catch(() => undefined); // the server got it; the answer was lost
    expect(await reconcileAfterAmbiguousFailure(new TransportError("timeout"), s)).toEqual({
      found: { auditId: RUN_AUDIT_ID },
    });
  });

  it("an earlier analysis of the same listing is NOT mistaken for this request", async () => {
    useScenario(
      createRun({ post: { status: 0, networkError: true }, listAfterPost: [earlierOfSameListing] }),
    );
    expect(await reconcileAfterAmbiguousFailure(new TransportError("network"), submission(REF))).toEqual({
      notReceived: true,
    });
  });

  it("says it does not know when the server cannot be asked", async () => {
    useScenario(createRun({ listFails: true }));
    expect(await reconcileAfterAmbiguousFailure(new TransportError("network"), submission(REF))).toEqual({
      unknown: true,
    });
  });

  it("a lookup answered after the session changed says nothing about this request", async () => {
    useScenario(createRun());
    const s = submission(REF);
    const pending = reconcileAfterAmbiguousFailure(new TransportError("network"), s);
    advanceSessionGeneration();
    expect(await pending).toBeNull();
  });
});
