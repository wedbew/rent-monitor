"""Pick the next ready issue for the headless agent, or resume/block a stuck one (ADR 0012, docs/AUTONOMY.md).

One action per run, idempotent, and a dry run unless `--apply`:

* an issue labelled `agent` is in flight: leave it while it has recent activity; after `--stale-minutes`
  without activity, resume it (a comment that mentions @claude, up to `--max-attempts` times), then mark
  it `blocked` with the owner action instead of retrying forever;
* nothing in flight: label the first `ready` issue `agent` (which starts `.github/workflows/claude.yml`)
  when every `Depends on: #n` is closed and it is not `blocked`, `umbrella` or `owner`.

The pure decision is `decide`; `main` only talks to `gh`. Concurrency is one issue at a time by construction.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

MARKER = "<!-- rm-dispatch attempt="
SKIP_LABELS = {"blocked", "umbrella", "owner", "agent", "in-progress"}
BRANCH = r"^(rm-{n}-|claude/issue-{n}-)"


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    labels: frozenset[str]
    body: str
    updated_at: datetime
    comments: tuple[str, ...] = ()


@dataclass(frozen=True)
class Pr:
    number: int
    branch: str
    updated_at: datetime


@dataclass(frozen=True)
class Decision:
    action: str  # idle | dispatch | resume | block
    issue: int | None = None
    reason: str = ""
    attempt: int = 0
    notes: list[str] = field(default_factory=list)


def depends_on(body: str) -> list[int]:
    """Issue numbers on the `Depends on:` line; `none` or no line means no prerequisite."""
    m = re.search(r"(?im)^\s*Depends on:\s*(.*)$", body)
    return [int(n) for n in re.findall(r"#(\d+)", m.group(1))] if m else []


def priority(body: str) -> int:
    m = re.search(r"(?im)^\s*Priority:\s*P(\d)", body)
    return int(m.group(1)) if m else 1


def attempts(issue: Issue) -> int:
    return sum(1 for c in issue.comments if MARKER in c)


def decide(
    issues: list[Issue],
    closed: set[int],
    prs: list[Pr],
    now: datetime,
    *,
    stale: timedelta = timedelta(minutes=60),
    max_attempts: int = 2,
) -> Decision:
    for issue in sorted(
        (i for i in issues if "agent" in i.labels and "blocked" not in i.labels), key=lambda i: i.number
    ):
        own = [p for p in prs if re.match(BRANCH.format(n=issue.number), p.branch)]
        last = max([issue.updated_at, *[p.updated_at for p in own]])
        if now - last < stale:
            return Decision(
                "idle", issue.number, f"#{issue.number} is in flight (last activity {last.isoformat()})"
            )
        n = attempts(issue)
        if n < max_attempts:
            return Decision("resume", issue.number, "no activity; resume from the checkpoint", attempt=n + 1)
        return Decision(
            "block", issue.number, f"no activity after {n} attempts; owner must look at the run log"
        )
    ready = [
        i
        for i in issues
        if "ready" in i.labels
        and not (i.labels & SKIP_LABELS)
        and attempts(i) < max_attempts
        and all(d in closed for d in depends_on(i.body))
    ]
    if not ready:
        return Decision("idle", None, "no ready issue with all dependencies closed")
    pick = min(ready, key=lambda i: (priority(i.body), i.number))
    return Decision(
        "dispatch", pick.number, f"first ready issue (P{priority(pick.body)})", attempt=attempts(pick) + 1
    )


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout  # noqa: S603, S607


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load() -> tuple[list[Issue], set[int], list[Pr]]:
    raw = json.loads(
        _gh(
            "issue",
            "list",
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,labels,body,updatedAt,comments",
        )
    )
    issues = [
        Issue(
            r["number"],
            r["title"],
            frozenset(label["name"] for label in r["labels"]),
            r["body"] or "",
            _ts(r["updatedAt"]),
            tuple(c["body"] for c in r["comments"]),
        )
        for r in raw
    ]
    closed = {
        r["number"]
        for r in json.loads(_gh("issue", "list", "--state", "closed", "--limit", "500", "--json", "number"))
    }
    prs = [
        Pr(r["number"], r["headRefName"], _ts(r["updatedAt"]))
        for r in json.loads(_gh("pr", "list", "--state", "open", "--json", "number,headRefName,updatedAt"))
    ]
    return issues, closed, prs


def _comment(n: str, body: str) -> None:
    _gh("issue", "comment", n, "--body", body)


def apply(d: Decision) -> None:
    n = str(d.issue)
    if d.action == "dispatch":
        _comment(
            n,
            f"{MARKER}{d.attempt} -->\nDispatched to the headless agent (attempt {d.attempt}). "
            "Resume rules: `.agent/rules/delivery.md`.",
        )
        _gh("issue", "edit", n, "--add-label", "agent")
    elif d.action == "resume":
        _comment(
            n,
            f"{MARKER}{d.attempt} -->\n@claude resume: find branch `rm-{n}-*` and the latest `rm-checkpoint` "
            "comment, continue there, do not open a new PR, and post a checkpoint before you stop.",
        )
    elif d.action == "block":
        _gh("issue", "edit", n, "--add-label", "blocked", "--remove-label", "agent")
        _comment(
            n,
            f"Blocked by the dispatcher: {d.reason}. Owner action: read the latest `claude` run log, fix the "
            "cause, then remove the `blocked` label to allow another attempt.",
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform the action (default: print it)")
    ap.add_argument("--stale-minutes", type=int, default=60)
    ap.add_argument("--max-attempts", type=int, default=2)
    args = ap.parse_args(argv)
    issues, closed, prs = load()
    d = decide(
        issues,
        closed,
        prs,
        datetime.now(UTC),
        stale=timedelta(minutes=args.stale_minutes),
        max_attempts=args.max_attempts,
    )
    print(json.dumps({"action": d.action, "issue": d.issue, "reason": d.reason, "attempt": d.attempt}))
    if args.apply and d.action != "idle":
        apply(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
