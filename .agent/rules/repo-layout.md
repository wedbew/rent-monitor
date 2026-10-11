# Rule: keep the repository shallow

- **No directory whose only child is a single directory.** Do not add pass-through folders (`src/`, `lib/`, `app/`, a folder
  named like the one inside it). If a folder would hold exactly one subfolder, put the contents one level up.
- **Python packages use a flat layout:** `packages/rm-core/rm_core/…`, `services/api/rm_api/…`; never `…/src/rm_core/`.
  The distribution folder holds `pyproject.toml` and the module next to each other.
- Allowed exceptions are paths a tool requires: `.github/workflows/`, `.cursor/rules/`, `.claude/skills/<name>/SKILL.md`, `migrations/versions/`,
  `docs/adr/`. Say so in the PR if you add another.
- Before adding a directory, check it will hold at least two entries (files or folders) or is on the list above.
- Moving files: `git mv` so history follows; update `pyproject.toml` (`packages = ["<module>"]`, pyright `extraPaths`, ruff
  per-file-ignores), docs paths and blueprint §4.1 in the same PR.
