// @vitest-environment node
import { Linter } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

// @ts-expect-error -- a plain ES module shared with eslint.config.mjs; it has no type declarations
import { COPY_SYNTAX } from "../eslint.copy.mjs";

/** Audit F06: visible copy comes from the catalog. These are the shapes the rule must refuse and allow. */
const linter = new Linter({ configType: "flat" });
const config: Linter.Config[] = [
  {
    files: ["**/*.tsx"],
    languageOptions: { parser: tseslint.parser, parserOptions: { ecmaFeatures: { jsx: true } } },
    rules: {
      "no-restricted-syntax": ["error", ...(COPY_SYNTAX as { selector: string; message: string }[])],
    },
  },
];
const problems = (code: string) =>
  linter.verify(code, config, "case.tsx").filter((m) => m.ruleId === "no-restricted-syntax");

describe("the copy lint rule", () => {
  it.each([
    ["text in JSX", "<p>Zaloguj się</p>;"],
    ["a label prop", '<Field label="Hasło" />;'],
    ["an aria-label", '<nav aria-label="Dokumenty" />;'],
    ["a title in braces", '<Notice title={"Błąd"} />;'],
    ["a sentence glued in a template", "<Page lead={`Cześć, ${name}.`} />;"],
    ["a string expression child", '<p>{"Spróbuj ponownie"}</p>;'],
  ])("refuses %s", (_, code) => {
    expect(problems(code).length).toBeGreaterThan(0);
  });

  it.each([
    ["catalog text", "<p>{t.auth.signIn}</p>;"],
    ["a catalog label", "<Field label={t.auth.password} />;"],
    ["punctuation between values", "<p>{a} · {b} — {c}</p>;"],
    ["machine props", '<Button type="submit" variant="primary" icon="arrow" />;'],
  ])("allows %s", (_, code) => {
    expect(problems(code)).toEqual([]);
  });
});
