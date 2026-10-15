// @vitest-environment node
import { Linter } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

// @ts-expect-error -- a plain ES module shared with eslint.config.mjs; it has no type declarations
import { MONEY_SYNTAX } from "../eslint.money.mjs";

/**
 * Audit F16: the money guardrail matched only `Number(x.price_pln)` and `+x.price_pln`. Each case below is a
 * bypass it missed, plus the forms that must stay allowed (formatting, comparisons, ids).
 */
const linter = new Linter({ configType: "flat" });
const config: Linter.Config[] = [
  {
    files: ["**/*.ts"],
    languageOptions: { parser: tseslint.parser },
    rules: {
      "no-restricted-syntax": ["error", ...(MONEY_SYNTAX as { selector: string; message: string }[])],
    },
  },
];
const problems = (code: string) =>
  linter.verify(code, config, "case.ts").filter((m) => m.ruleId === "no-restricted-syntax");

describe("the money lint guardrail", () => {
  it.each([
    ["Number() on a field", "Number(r.price_pln);"],
    ["Number() through optional chaining", "Number(r?.price_pln);"],
    ["Number() on a computed key", 'Number(r["price_pln"]);'],
    ["Number() on a destructured field", "const { price_pln } = r; Number(price_pln);"],
    ["globalThis.Number()", "globalThis.Number(r.max_bid_pln);"],
    ["Number.parseFloat", "Number.parseFloat(r.net_yield);"],
    ["parseInt", "parseInt(r.price_pln, 10);"],
    ["BigInt()", "BigInt(r.price_pln);"],
    ["Math on a rate", "Math.round(r.irr);"],
    ["unary plus", "+r.gross_yield;"],
    ["unary minus", "-r.discount_to_asking;"],
    ["multiplication", "r.price_pln * 1.02;"],
    ["subtraction of two prices", "a.price_pln - b.max_bid_pln;"],
    ["exponent", "r.moic ** 2;"],
    ["string concatenation of money", '"Cena: " + r.price_pln;'],
    ["parseFloat anywhere", "parseFloat(text);"],
  ])("refuses %s", (_, code) => {
    expect(problems(code).length).toBeGreaterThan(0);
  });

  it.each([
    ["formatting", "formatMoney(r.price_pln);"],
    ["a null check", "r.price_pln === null;"],
    ["a comparison of codes", 'r.grade === "A";'],
    ["counts and ids", "Number(r.rooms); r.year + 1; Number(id);"],
  ])("allows %s", (_, code) => {
    expect(problems(code)).toEqual([]);
  });
});
