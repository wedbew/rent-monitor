# Rule: keep the repository shallow

- **No directory whose only child is a single directory.** Do not add pass-through folders (`src/`, `lib/`, `app/`, a folder
  named like the one inside it). If a folder would hold exactly one subfolder, put the contents one level up.
- **The package folder is the module itself:** `packages/rm_core/` (with `pyproject.toml` and the `.py` files directly inside),
  `services/rm_api/`. Never `…/src/rm_core/` and never `packages/rm-core/rm_core/`. The distribution name stays `rm-core`;
  hatch maps the folder (`sources = {"" = "rm_core"}`, `dev-mode-dirs = [".."]`).
- Allowed exceptions are paths a tool requires: `.github/workflows/`, `.cursor/rules/`, `.claude/skills/<name>/SKILL.md`, `migrations/versions/`,
  `docs/adr/`. Say so in the PR if you add another.
- Before adding a directory, check it will hold at least two entries (files or folders) or is on the list above.
- Moving files: `git mv` so history follows; update `pyproject.toml` (`packages = ["<module>"]`, pyright `extraPaths`, ruff
  per-file-ignores), docs paths and blueprint §4.1 in the same PR.
