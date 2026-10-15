/**
 * Self-tests of the gate itself, on synthetic pages: the gate must catch what it claims to catch. Without these a
 * broken inventory would pass silently on an empty registry.
 */
import { expect } from "@playwright/test";

import { test } from "./fixtures";
import { inventory } from "./inventory";
import type { Interaction } from "./interactions";
import { expectDialogContract } from "./popups";

const scope = { page: "synthetic", scenario: "firstVisit" };
const entry = (over: Partial<Interaction> & Pick<Interaction, "id" | "role" | "name">): Interaction => ({
  page: "synthetic",
  outcome: "url",
  ...over,
});

test.describe("inventory", () => {
  test("flags an unregistered button", async ({ page }) => {
    await page.setContent("<main><button>Kup pakiet</button></main>");
    const found = await inventory(page, scope, []);
    expect(found.map((v) => v.kind)).toEqual(["unregistered"]);
    expect(found[0]?.message).toContain('button "Kup pakiet"');
  });

  test("flags a control without an accessible name", async ({ page }) => {
    await page.setContent(
      '<main><button><svg width="10" height="10"></svg></button><a href="/x"></a></main>',
    );
    const found = await inventory(page, scope, []);
    expect(found.map((v) => v.kind)).toEqual(["unnamed", "unnamed"]);
  });

  test("accepts registered controls, by exact name or pattern, and ignores non-interactive roles", async ({
    page,
  }) => {
    await page.setContent(
      '<main><h1>Tytuł</h1><p>Tekst</p><a href="/a">Pulpit</a><button>Otwórz raport 12</button><input aria-label="Adres"></main>',
    );
    const registry = [
      entry({ id: "nav", role: "link", name: "Pulpit" }),
      entry({ id: "row", role: "button", name: /^Otwórz raport \d+$/ }),
      entry({ id: "addr", role: "textbox", name: "Adres" }),
    ];
    expect(await inventory(page, scope, registry)).toEqual([]);
  });

  test("flags a registered element that is no longer on the page", async ({ page }) => {
    await page.setContent("<main><p>Pusto</p></main>");
    const found = await inventory(page, scope, [entry({ id: "gone", role: "button", name: "Zapisz" })]);
    expect(found.map((v) => v.kind)).toEqual(["missing"]);
  });

  test("scopes registrations to their scenario", async ({ page }) => {
    await page.setContent("<main><button>Zapisz</button></main>");
    const registry = [entry({ id: "save", role: "button", name: "Zapisz", scenarios: ["loaded"] })];
    expect((await inventory(page, scope, registry)).map((v) => v.kind).sort()).toEqual(["unregistered"]);
    expect(await inventory(page, { ...scope, scenario: "loaded" }, registry)).toEqual([]);
  });
});

const GOOD_DIALOG = `
<main><button id="open">Usuń konto</button></main>
<dialog id="d" aria-label="Potwierdź usunięcie"><p>Na pewno?</p><button id="close" autofocus>Anuluj</button><button>Usuń</button></dialog>
<script>
  const d = document.getElementById("d");
  document.getElementById("open").addEventListener("click", () => d.showModal());
  document.getElementById("close").addEventListener("click", () => d.close());
</script>`;

const BAD_DIALOG = `
<main><button id="open">Usuń konto</button><button id="other">Inne</button></main>
<div id="d" role="dialog" aria-label="Potwierdź" hidden><button>Anuluj</button></div>
<script>
  document.getElementById("open").addEventListener("click", () => { document.getElementById("d").hidden = false; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") document.getElementById("d").hidden = true; });
</script>`;

test.describe("popup contract", () => {
  test("passes for a well-behaved modal dialog", async ({ page }) => {
    await page.setContent(GOOD_DIALOG);
    await expectDialogContract(page, {
      trigger: page.getByRole("button", { name: "Usuń konto" }),
      dialog: page.getByRole("dialog"),
      backdrop: "stays",
    });
  });

  test("catches a popup that does not move focus into itself", async ({ page }) => {
    await page.setContent(BAD_DIALOG);
    await expect(
      expectDialogContract(page, {
        trigger: page.getByRole("button", { name: "Usuń konto" }),
        dialog: page.getByRole("dialog"),
        backdrop: "stays",
      }),
    ).rejects.toThrow(/initial focus is inside the popup/);
  });

  test("catches a dialog without an accessible name", async ({ page }) => {
    await page.setContent(GOOD_DIALOG.replace(' aria-label="Potwierdź usunięcie"', ""));
    await expect(
      expectDialogContract(page, {
        trigger: page.getByRole("button", { name: "Usuń konto" }),
        dialog: page.locator("dialog"),
        backdrop: "stays",
      }),
    ).rejects.toThrow(/accessible name/);
  });
});
