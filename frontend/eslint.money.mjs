// Guardrails that keep money, ratios and areas out of binary floats in the SPA (invariant 4: the browser formats
// numbers, it never computes them). Shared by eslint.config.mjs and tested in eslint.money.test.ts against the
// bypasses the 2026-10-15 audit found (F16). A lint rule is a guardrail, not a proof: a value renamed through a
// plain variable (`const p = r.price_pln; Number(p)`) needs data flow to catch and stays a review item.

/** Field names that carry money or rates in the API and the report. */
export const MONEY_NAME = String.raw`/_pln$|^irr|ratio$|yield$|^moic$|^cagr$|^hurdle$|^haircut$|^discount|^multiplier$/`;

const MONEY_MEMBER = `MemberExpression[property.name=${MONEY_NAME}]`;
const MONEY_COMPUTED = `MemberExpression[computed=true][property.value=${MONEY_NAME}]`;
const MONEY_IDENTIFIER = `Identifier[name=${MONEY_NAME}]`;
/** A money value read directly, through `?.`, by `["name"]`, or from a destructured/same-named binding. */
const MONEY_VALUE = [
  MONEY_MEMBER,
  MONEY_COMPUTED,
  `ChainExpression > ${MONEY_MEMBER}`,
  `ChainExpression > ${MONEY_COMPUTED}`,
  MONEY_IDENTIFIER,
];

const NUMBER_CALLEE = [
  "CallExpression[callee.name=/^(Number|parseInt|parseFloat|BigInt)$/]",
  "CallExpression[callee.property.name=/^(Number|parseInt|parseFloat)$/]",
  "CallExpression[callee.object.name='Math']",
];

const each = (parents, children) => parents.flatMap((p) => children.map((c) => `${p} > ${c}`)).join(", ");

export const MONEY_SYNTAX = [
  {
    selector: each(NUMBER_CALLEE, MONEY_VALUE),
    message:
      "Money and ratios are decimal strings: format them with api/format.ts, never through Number() or Math.",
  },
  {
    selector: each(["UnaryExpression[operator=/^[-+]$/]"], MONEY_VALUE),
    message: "Money and ratios are decimal strings: format them with api/format.ts, never coerce them.",
  },
  {
    selector: each(["BinaryExpression[operator=/^([-*\\/%]|\\*\\*|\\+)$/]"], MONEY_VALUE),
    message: "No arithmetic on money or rates in the browser: the engine computes, api/format.ts formats.",
  },
  {
    selector: "CallExpression[callee.name='parseFloat'], CallExpression[callee.property.name='parseFloat']",
    message: "No binary floats for money, areas or rates: use api/format.ts.",
  },
];
