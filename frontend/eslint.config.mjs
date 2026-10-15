import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

const HTML_SINKS = ["innerHTML", "outerHTML"];

export default tseslint.config(
  {
    ignores: [
      "dist",
      "node_modules",
      "api/schema.generated.ts",
      "api/report.generated.ts",
      "coverage",
      "playwright-report",
      "test-results",
    ],
  },
  js.configs.recommended,
  tseslint.configs.recommendedTypeChecked,
  reactHooks.configs.flat["recommended-latest"],
  jsxA11y.flatConfigs.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/ban-ts-comment": [
        "error",
        { "ts-expect-error": "allow-with-description", minimumDescriptionLength: 10 },
      ],
      "no-console": "error",
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "User and listing content is rendered as text (guide section 7). No raw HTML.",
        },
        {
          selector:
            "CallExpression[callee.name='Number'] > MemberExpression[property.name=/_pln$|^irr|ratio$/]",
          message:
            "Money and ratios are decimal strings: format them with api/format.ts, never through Number().",
        },
        {
          selector: "UnaryExpression[operator='+'] > MemberExpression[property.name=/_pln$|^irr|ratio$/]",
          message: "Money and ratios are decimal strings: format them with api/format.ts, never coerce them.",
        },
        {
          selector:
            "CallExpression[callee.name='parseFloat'], CallExpression[callee.property.name='parseFloat']",
          message: "No binary floats for money, areas or rates: use api/format.ts.",
        },
        ...HTML_SINKS.map((name) => ({
          selector: `AssignmentExpression[left.property.name='${name}']`,
          message: `Assigning ${name} is banned: it renders untrusted text as HTML.`,
        })),
      ],
    },
  },
  {
    // Production code never imports test tooling, mocks or fixtures.
    files: ["**/*.{ts,tsx}"],
    ignores: ["**/*.test.{ts,tsx}", "test/**", "e2e/**", "playwright.config.ts", "vite.config.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["msw", "msw/*", "vitest", "vitest/*", "@testing-library/*"],
              message: "Test tooling stays out of production code.",
            },
            {
              group: ["**/test/*", "**/fixtures/*", "**/e2e/*"],
              message: "Fixtures and mocks stay out of production code.",
            },
          ],
        },
      ],
    },
  },
  {
    // `ui` is domain-free: no API, no features, no shell.
    files: ["ui/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/api/*", "**/features/*", "**/shell/*"],
              message: "ui/ primitives know nothing about the API or features.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "test/**"],
    languageOptions: { globals: { ...globals.vitest } },
  },
  {
    // Tooling files run in Node, outside the app: no type-aware rules, console output is their interface.
    files: ["*.mjs", "*.config.ts"],
    extends: [tseslint.configs.disableTypeChecked],
    languageOptions: { globals: { ...globals.node } },
    rules: { "no-console": "off", "no-restricted-imports": "off" },
  },
  prettier,
);
