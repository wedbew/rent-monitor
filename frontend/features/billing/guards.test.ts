import { describe, expect, it } from "vitest";

import { readInvoiceUrl, readPack, readPacks, readPurchase, readPurchases } from "./guards";

const purchase = {
  purchase_id: "00000000-0000-4000-8000-000000000001",
  pack_code: "reports_5",
  reports: 5,
  gross_pln: "40",
  currency: "PLN",
  state: "created",
  transaction_id: "txn_fixture0001",
  checkout_url: null,
  created_at: "2026-10-01T10:00:00Z",
  granted_at: null,
  refunded_at: null,
};

describe("readPack / readPacks", () => {
  it("reads a pack and keeps the price as the API's own string", () => {
    expect(readPack({ code: "reports_1", reports: 1, gross_pln: "10.50" })).toEqual({
      code: "reports_1",
      reports: 1,
      grossPln: "10.50",
    });
  });

  it("refuses anything that is not a priced pack of a known code", () => {
    for (const bad of [
      null,
      { code: "reports_99", reports: 1, gross_pln: "10" },
      { code: "reports_1", reports: 0, gross_pln: "10" },
      { code: "reports_1", reports: 1.5, gross_pln: "10" },
      { code: "reports_1", reports: 1, gross_pln: 10 },
      { code: "reports_1", reports: 1, gross_pln: "1e3" },
      { code: "reports_1", reports: 1, gross_pln: "-5" },
      { code: "reports_1", reports: 1, gross_pln: "NaN" },
    ])
      expect(readPack(bad)).toBeNull();
  });

  it("an answer without a boolean `enabled`, or with only unreadable packs, is not a shop", () => {
    expect(readPacks({ enabled: "yes", packs: [] })).toBeNull();
    expect(readPacks({ enabled: true, packs: [{ junk: 1 }] })).toBeNull();
    expect(readPacks({ enabled: false, packs: [] })).toEqual({ enabled: false, packs: [] });
  });
});

describe("readPurchase / readPurchases", () => {
  it("reads a purchase", () => {
    expect(readPurchase(purchase)).toMatchObject({
      id: purchase.purchase_id,
      state: "created",
      transactionId: "txn_fixture0001",
      grossPln: "40",
    });
  });

  it("drops a state or id it does not know, and never hands a foreign transaction id to Paddle", () => {
    expect(readPurchase({ ...purchase, state: "paid_in_full" })).toBeNull();
    expect(readPurchase({ ...purchase, purchase_id: "../x" })).toBeNull();
    expect(readPurchase({ ...purchase, gross_pln: "1e3" })).toBeNull();
    expect(readPurchase({ ...purchase, transaction_id: "<script>" })?.transactionId).toBeNull();
    expect(readPurchase({ ...purchase, transaction_id: "ctx_abc" })?.transactionId).toBeNull();
  });

  it("a list of only unreadable rows is a failure; an empty list is an answer", () => {
    expect(readPurchases({ purchases: [{ junk: true }] })).toBeNull();
    expect(readPurchases({ purchases: [] })).toEqual({ purchases: [], hidden: 0 });
    expect(readPurchases([purchase])).toBeNull();
    const partial = readPurchases({ purchases: [purchase, { junk: 1 }] });
    expect(partial?.purchases).toHaveLength(1);
    expect(partial?.hidden).toBe(1); // reported, never silently dropped
  });
});

describe("readInvoiceUrl", () => {
  it("only an https address is ever opened", () => {
    expect(readInvoiceUrl({ url: "https://invoice.example.test/a.pdf" })).toBe(
      "https://invoice.example.test/a.pdf",
    );
    for (const bad of ["http://x.test/a", "javascript:alert(1)", "data:text/html,x", "not a url", 5, null])
      expect(readInvoiceUrl({ url: bad })).toBeNull();
    expect(readInvoiceUrl(null)).toBeNull();
  });
});
