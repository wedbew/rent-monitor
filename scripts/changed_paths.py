"""Decide whether a change is documentation only, so CI can skip the code stages (ADR 0012).

Prints `docs_only=true|false`. Conservative on purpose: any doubt (unknown base, git failure, empty diff) is
`false`, and only Markdown outside the code directories, Cursor `.mdc` pointers and `design/` count as
documentation.
`docs/openapi.json`, workflows, scripts, configuration and anything tests read are code. Security, lint, the
title check and the lockfile audit do not use this and always run.
"""

import subprocess
import sys

ZERO = "0" * 40
DOC_SUFFIXES = (".md", ".mdc")
DOC_DIRS = ("design/",)
# Markdown under these is an executable input (golden expected output, fixtures, packaged docs): it is code.
CODE_DIRS = (
    "tests/",
    "apps/",
    "packages/",
    "services/",
    "scripts/",
    "migrations/",
    "deploy/",
    ".github/",
    ".semgrep/",
)


def is_doc(path: str) -> bool:
    if path.startswith(CODE_DIRS):
        return False
    return path.endswith(DOC_SUFFIXES) or path.startswith(DOC_DIRS)


def docs_only(files: list[str]) -> bool:
    return bool(files) and all(is_doc(f) for f in files)


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
    files = changed_files(base, head)
    print(f"docs_only={'true' if files is not None and docs_only(files) else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
