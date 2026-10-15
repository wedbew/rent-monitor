/** @type {import("stylelint").Config} */
export default {
  extends: ["stylelint-config-standard"],
  ignoreFiles: ["dist/**", "node_modules/**"],
  rules: {
    // CSS Modules: `composes` and `:global(...)` are deliberate; unknown properties are not.
    "property-no-unknown": [true, { ignoreProperties: ["composes"] }],
    "selector-pseudo-class-no-unknown": [true, { ignorePseudoClasses: ["global", "local"] }],
    "declaration-no-important": true,
    "selector-max-id": 0,
    "selector-class-pattern": null,
  },
};
