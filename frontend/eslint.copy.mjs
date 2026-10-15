// Copy lives in the typed Polish catalog (i18n/pl.ts, audit F06, #305), never as literals in components. These
// selectors refuse visible text written into JSX and into props a person reads or hears. Text without a letter
// (punctuation, separators such as "·" or "—") is not copy. Tested in test/eslint-copy.test.ts.

const LETTER = String.raw`/\p{L}/u`;

/** Props whose value a person reads or hears. */
export const VISIBLE_PROPS = [
  "title",
  "label",
  "aria-label",
  "alt",
  "placeholder",
  "hint",
  "description",
  "lead",
  "eyebrow",
  "closeLabel",
  "message",
];

const PROPS = `/^(${VISIBLE_PROPS.join("|")})$/`;

export const COPY_SYNTAX = [
  {
    selector: `JSXText[value=${LETTER}]`,
    message: "Visible text comes from the catalog (i18n/pl.ts): use t.<area>.<key>, not a literal in JSX.",
  },
  {
    selector: `JSXAttribute[name.name=${PROPS}] > Literal[value=${LETTER}]`,
    message: "A label, title or description a person reads comes from the catalog (i18n/pl.ts).",
  },
  {
    selector: `JSXAttribute[name.name=${PROPS}] > JSXExpressionContainer > Literal[value=${LETTER}]`,
    message: "A label, title or description a person reads comes from the catalog (i18n/pl.ts).",
  },
  {
    selector: `JSXAttribute[name.name=${PROPS}] > JSXExpressionContainer > TemplateLiteral > TemplateElement[value.raw=${LETTER}]`,
    message: "Build the sentence in the catalog (a message function), not from fragments in a template.",
  },
  {
    selector: `JSXExpressionContainer > Literal[value=${LETTER}]`,
    message: "Visible text comes from the catalog (i18n/pl.ts).",
  },
];
