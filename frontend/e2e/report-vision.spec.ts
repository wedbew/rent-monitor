import { SUCCEEDED_AUDITS } from "../test/scenarios";
import { expect, test } from "./fixtures";

// The vision evidence the engine persists (RM-387). The mocked API serves the captured audit with these fields added,
// so the page shows what the API returned, and a reload must show the same values again.
const audit = SUCCEEDED_AUDITS[0];
const auditId = audit?.audit_id ?? "";

const evidence = {
  model: "vision-model",
  prompt_version: "vision-v2",
  photos_total: 4,
  photos_excluded: 0,
  equipment: [
    {
      item: "klimatyzacja",
      media_ordinal: 1,
      provenance: "photo",
      sale_status: "included",
      confidence: "0.85",
    },
    {
      item: "kuchenka indukcyjna",
      media_ordinal: 4,
      provenance: "floor_plan",
      sale_status: "visible_only",
      confidence: "0.4",
    },
  ],
  floor_plan_text: "Salon 24 m2, sypialnia 12 m2",
  notes: "Zdjęcie łazienki nieostre.",
};

test.describe("persisted vision evidence in the report", () => {
  test("shows the evidence the API returned, and the same values after a reload", async ({ page, serve }) => {
    if (audit === undefined) throw new Error("no audit fixture");
    await serve("loaded");
    // Registered after `serve`, so it runs first; anything but this audit's GET goes on to the mocked API.
    await page.route(/\/api\/audits\/[^/?]+$/, async (route) => {
      if (route.request().method() !== "GET" || !route.request().url().endsWith(`/api/audits/${auditId}`)) {
        await route.fallback();
        return;
      }
      await route.fulfill({
        // The captured vision record (an older one, without the evidence fields) keeps its own answer; the evidence
        // fields are added to it, as the engine writes them.
        json: {
          ...audit,
          result: {
            ...(audit.result as object),
            vision: { ...(audit.result as { vision: object }).vision, ...evidence },
          },
        },
      });
    });

    await page.goto(`/app/analyses/${auditId}`);
    await expect(page.getByRole("heading", { level: 2, name: "Podsumowanie" })).toBeVisible();
    await page.getByRole("button", { name: "Ocena zdjęć" }).click();
    await expect(page.getByText("klimatyzacja")).toBeVisible();
    await expect(page.getByText("źródło: zdjęcie nr 2")).toBeVisible();
    await expect(page.getByText("źródło: rzut, pozycja 5 na liście zdjęć i rzutów")).toBeVisible();
    await expect(page.getByText("Salon 24 m2, sypialnia 12 m2")).toBeVisible();

    await page.reload();
    await expect(page.getByRole("heading", { level: 2, name: "Podsumowanie" })).toBeVisible();
    await page.getByRole("button", { name: "Ocena zdjęć" }).click();
    await expect(page.getByText("kuchenka indukcyjna")).toBeVisible();
    await expect(page.getByText("Zdjęcie łazienki nieostre.")).toBeVisible();
  });
});
