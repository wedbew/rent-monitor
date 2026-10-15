import { describe, expect, it } from "vitest";

import { ApiError, TransportError } from "../../../api/errors";
import { createRun } from "../../../test/scenarios";
import { useScenario } from "../../../test/handlers";
import { otodomIdOf, reconcileAfterAmbiguousFailure } from "./useCreateAudit";

const created = (at: Date) => ({
  audit_id: "00000000-0000-4000-8000-0000000000a1",
  otodom_id: "IDFIX0099",
  status: "queued" as const,
  error_code: null,
  created_at: at.toISOString(),
  finished_at: null,
  grade: null,
  asking_price_pln: null,
  max_bid_pln: null,
});

const REF = "https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-IDFIX0099";

describe("otodomIdOf", () => {
  it("reads the id from an id or the end of a listing URL, ignoring query and fragment", () => {
    expect(otodomIdOf("ID4abcd")).toBe("ID4abcd");
    expect(otodomIdOf("  ID4abcd  ")).toBe("ID4abcd");
    expect(otodomIdOf("https://www.otodom.pl/pl/oferta/x-ID4abcd")).toBe("ID4abcd");
    expect(otodomIdOf("https://www.otodom.pl/pl/oferta/x-ID4abcd?utm=1#a")).toBe("ID4abcd");
    expect(otodomIdOf("https://example.test/nope")).toBeNull();
    expect(otodomIdOf("")).toBeNull();
  });
});

describe("reconcileAfterAmbiguousFailure", () => {
  it("does nothing for an answer the API gave: it said what happened", async () => {
    expect(await reconcileAfterAmbiguousFailure(new ApiError(402, null), REF, Date.now())).toBeNull();
    expect(await reconcileAfterAmbiguousFailure(new Error("x"), REF, Date.now())).toBeNull();
    expect(await reconcileAfterAmbiguousFailure(new TransportError("aborted"), REF, Date.now())).toBeNull();
  });

  it("finds an analysis of THIS listing created since the click", async () => {
    useScenario(createRun({ listAfterPost: [created(new Date())] }));
    const result = await reconcileAfterAmbiguousFailure(new TransportError("network"), REF, Date.now());
    expect(result).toEqual({ found: { auditId: "00000000-0000-4000-8000-0000000000a1" } });
    useScenario(createRun({ listAfterPost: [created(new Date())] }));
    expect(
      await reconcileAfterAmbiguousFailure(new TransportError("timeout"), REF, Date.now()),
    ).toMatchObject({
      found: { auditId: "00000000-0000-4000-8000-0000000000a1" },
    });
  });

  it("an unrelated recent analysis proves nothing", async () => {
    useScenario(createRun({ listAfterPost: [{ ...created(new Date()), otodom_id: "IDOTHER1" }] }));
    expect(await reconcileAfterAmbiguousFailure(new TransportError("network"), REF, Date.now())).toEqual({
      unknown: true,
    });
  });

  it("an old analysis of the same listing proves nothing either", async () => {
    useScenario(createRun({ listAfterPost: [created(new Date(Date.now() - 3_600_000))] }));
    expect(await reconcileAfterAmbiguousFailure(new TransportError("network"), REF, Date.now())).toEqual({
      unknown: true,
    });
  });

  it("an empty list is inconclusive, not 'not sent'", async () => {
    useScenario(createRun());
    expect(await reconcileAfterAmbiguousFailure(new TransportError("network"), REF, Date.now())).toEqual({
      unknown: true,
    });
  });

  it("says it does not know when no id can be read from what was typed, or the list fails", async () => {
    useScenario(createRun());
    expect(
      await reconcileAfterAmbiguousFailure(
        new TransportError("network"),
        "https://example.test/x",
        Date.now(),
      ),
    ).toEqual({ unknown: true });
    useScenario(createRun({ listFails: true }));
    expect(await reconcileAfterAmbiguousFailure(new TransportError("network"), REF, Date.now())).toEqual({
      unknown: true,
    });
  });
});
