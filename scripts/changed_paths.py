"""Decide which CI stages a change needs, so a PR only pays for what it can affect (ADR 0012).

Prints one `name=true|false` line per flag, for `$GITHUB_OUTPUT`:

- `docs_only`: Markdown outside the code directories, Cursor `.mdc` pointers and `design/`. Only the title
  check and the secret scan run.
- `python`: the Python stages (lint, types, tests, migrations). False for documentation and for a change that
  only touches `frontend/`. The OpenAPI document and the report schema stay `python`: tests read them.
- `frontend`: the SPA stages (`pnpm check`, mocked browser lane, visual lane). Anything under `frontend/`, the
  OpenAPI document and the report schema its generated types come from, and the workflows themselves.
- `journey`: the SPA against the real Compose stack. `frontend/`, plus everything the stack is built from.

Conservative on purpose: any doubt (unknown base, git failure, empty diff) turns every flag on except
`docs_only`. Workflows, scripts, configuration and anything tests read are code. The lockfile audit, secret
scan and title check do not use these flags and run on every change.
"""

import subprocess
import sys
from dataclasses import dataclass

ZERO = "0" * 40
DOC_SUFFIXES = (".md", ".mdc")
DOC_DIRS = ("design/",)
# Markdown under these is an executable input (golden expected output, fixtures, packaged docs) or is checked
# by a tool (Prettier on the SPA docs): it is code.
CODE_DIRS = (
    "tests/",
    "apps/",
    "packages/",
    "services/",
    "scripts/",
    "migrations/",
    "deploy/",
    "frontend/",
    ".github/",
    ".semgrep/",
)
FRONTEND_DIR = "frontend/"
# Read by the generated-API drift check in `pnpm check` (and by Python tests).
FRONTEND_CONTRACT_INPUTS = ("docs/openapi.json", "docs/deal-analysis.schema.json")
# What the Compose stack of the journey lane is built from, besides frontend/.
JOURNEY_STACK = (
    "services/",
    "packages/",
    "apps/",
    "migrations/",
    "deploy/",
    "scripts/e2e_session.py",
    "pyproject.toml",
    "uv.lock",
    "alembic.ini",
    ".github/",
)


@dataclass(frozen=True)
class Stages:
    docs_only: bool
    python: bool
    frontend: bool
    journey: bool

    def lines(self) -> list[str]:
        return [f"{name}={'true' if value else 'false'}" for name, value in vars(self).items()]


EVERYTHING = Stages(docs_only=False, python=True, frontend=True, journey=True)


def is_doc(path: str) -> bool:
    if path.startswith(CODE_DIRS):
        return False
    return path.endswith(DOC_SUFFIXES) or path.startswith(DOC_DIRS)


def docs_only(files: list[str]) -> bool:
    return bool(files) and all(is_doc(f) for f in files)


def classify(files: list[str] | None) -> Stages:
    if not files:
        return EVERYTHING
    if docs_only(files):
        return Stages(docs_only=True, python=False, frontend=False, journey=False)
    code = [f for f in files if not is_doc(f)]
    return Stages(
        docs_only=False,
        python=any(not f.startswith(FRONTEND_DIR) for f in code),
        frontend=any(f.startswith((FRONTEND_DIR, ".github/")) or f in FRONTEND_CONTRACT_INPUTS for f in code),
        journey=any(f.startswith(JOURNEY_STACK) or f.startswith(FRONTEND_DIR) for f in code),
    )


def changed_files(base: str, head: str) -> list[str] | None:
    if not base or base == ZERO:
        return None
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "diff", "--name-only", "--no-renames", base, head],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None
    return [line for line in out.splitlines() if line]


def main(argv: list[str]) -> int:
    base, head = [*argv, "", "HEAD"][:2]
    print("\n".join(classify(changed_files(base, head)).lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
