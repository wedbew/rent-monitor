"""Validate ticket-tagged commit messages: ``type(RM-<n>): subject``.

Used three ways:
  * commit-msg hook (prek):   python scripts/check_commit_msg.py <msg-file>
  * PR title check (CI):      python scripts/check_commit_msg.py --text "$PR_TITLE"
  * history check (CI):       python scripts/check_commit_msg.py --range origin/staging..HEAD

Only the repository's root commit (no parent) may omit the ticket.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

TYPES = ("feat", "fix", "perf", "refactor", "test", "docs", "build", "ci", "chore", "revert")
PATTERN = re.compile(rf"^({'|'.join(TYPES)})\(RM-[1-9][0-9]*\)!?: \S.{{0,71}}$")
# Bot-authored scopes with no ticket: Dependabot ("build(deps): ...", "ci(deps): ...") and
# release-please ("chore(release): 1.4.0"). Nothing else may omit the ticket.
BOT_PATTERN = re.compile(r"^((build|ci)\(deps\)|chore\(release\)): \S.{0,71}$")
# Messages git itself generates; never authored by people or agents.
GIT_GENERATED = re.compile(r"^(Merge (branch|pull request|remote-tracking branch) |fixup! |squash! |amend! )")


def subject(message: str) -> str:
    for line in message.splitlines():
        if line.strip() and not line.startswith("#"):
            return line.rstrip()
    return ""


def is_valid(message: str) -> bool:
    s = subject(message)
    return bool(PATTERN.match(s) or BOT_PATTERN.match(s) or GIT_GENERATED.match(s))


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def repo_has_head() -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True).returncode == 0


def check_range(rev_range: str) -> list[str]:
    bad = []
    for line in _git("rev-list", "--parents", rev_range).splitlines():
        sha, *parents = line.split()
        if not parents:  # root commit: the bootstrap exception
            continue
        msg = _git("log", "-1", "--format=%B", sha)
        if not is_valid(msg):
            bad.append(f"{sha[:10]}  {subject(msg)}")
    return bad


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("msg_file", nargs="?")
    p.add_argument("--text")
    p.add_argument("--range", dest="rev_range")
    a = p.parse_args(argv)

    if a.rev_range:
        bad = check_range(a.rev_range)
        for b in bad:
            print(f"invalid commit message: {b}", file=sys.stderr)
        return 1 if bad else 0

    if a.text is not None:
        message = a.text
    elif a.msg_file:
        if not repo_has_head():  # committing the root commit
            return 0
        with open(a.msg_file, encoding="utf-8") as fh:
            message = fh.read()
    else:
        p.error("give a message file, --text or --range")

    if is_valid(message):
        return 0
    print(
        f"invalid: {subject(message)!r}\n"
        "expected: type(RM-<issue>): subject   e.g. feat(RM-12): add credit ledger\n"
        f"types: {', '.join(TYPES)}; max 72 chars after ': '",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
