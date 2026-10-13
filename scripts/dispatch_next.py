"""Pick the next ready issue for the headless agent, or resume/block a stuck one (ADR 0012, docs/AUTONOMY.md).

One action per run, idempotent, and a dry run unless `--apply`. Work is in one of these states:

* running: a `claude` workflow run is queued or active, or the PR's checks are pending: leave it alone;
* awaiting approval or merge: an open PR with passing checks: never resumed, never blocked;
* failing: an open PR with failing checks, idle for `--stale-minutes`: resume (up to `--max-attempts`);
* stalled: labelled `agent`, no PR, idle for `--stale-minutes`: resume, then `blocked` with the owner action;
* nothing in flight, `staging` green, no run active: label the first `ready` issue `agent` (starts
  `claude.yml`) when every `Depends on: #n` is closed and it is not `blocked`, `umbrella`, `owner`
  or `in-progress`.

In flight means labelled `agent` or having an open PR (branch `rm-<n>-*`, `claude/issue-<n>-*`, or `RM-<n>`
in the title), whoever opened it. A blocked issue is retried only after the owner comments `/retry`
(attempts count from the latest one) and removes `blocked`. `decide` is pure; `main` talks to `gh`.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

MARKER = "<!-- rm-dispatch attempt="
RETRY = "/retry"
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
    title: str = ""
    checks: str = "passing"  # pending | passing | failing


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
    """Dispatch attempts since the owner's latest `/retry` comment, not over the issue's lifetime."""
    start = 0
    for i, c in enumerate(issue.comments):
        if c.strip().startswith(RETRY):
            start = i + 1
    return sum(1 for c in issue.comments[start:] if MARKER in c)


def owns(issue_number: int, pr: Pr) -> bool:
    return bool(
        re.match(BRANCH.format(n=issue_number), pr.branch) or re.search(rf"\bRM-{issue_number}\b", pr.title)
    )


def decide(  # noqa: PLR0911
    issues: list[Issue],
    closed: set[int],
    prs: list[Pr],
    now: datetime,
    *,
    stale: timedelta = timedelta(minutes=60),
    max_attempts: int = 2,
    claude_running: bool = False,
    staging_green: bool = True,
) -> Decision:
    if claude_running:
        return Decision("idle", None, "a claude workflow run is active")
    in_flight = sorted(
        (
            i
            for i in issues
            if "blocked" not in i.labels and ("agent" in i.labels or any(owns(i.number, p) for p in prs))
        ),
        key=lambda i: i.number,
    )
    for issue in in_flight:
        own = [p for p in prs if owns(issue.number, p)]
        last = max([issue.updated_at, *[p.updated_at for p in own]])
        n = attempts(issue)
        if own:
            if any(p.checks == "pending" for p in own):
                return Decision("idle", issue.number, f"#{issue.number}: PR checks are running")
            if all(p.checks == "passing" for p in own):
                return Decision("idle", issue.number, f"#{issue.number}: PR awaits approval or merge")
            if now - last < stale:
                return Decision("idle", issue.number, f"#{issue.number}: PR checks failed, fix in progress")
            if n < max_attempts:
                return Decision(
                    "resume", issue.number, "PR checks failing and idle; resume the fix", attempt=n + 1
                )
            return Decision("block", issue.number, f"PR checks still failing after {n} attempts")
        if now - last < stale:
            return Decision(
                "idle", issue.number, f"#{issue.number} is in flight (last activity {last.isoformat()})"
            )
        if n < max_attempts:
            return Decision("resume", issue.number, "no activity; resume from the checkpoint", attempt=n + 1)
        return Decision(
            "block", issue.number, f"no activity after {n} attempts; owner must look at the run log"
        )
    if not staging_green:
        return Decision("idle", None, "staging CI is red: fix it before starting new work")
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


FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE"}


def _checks(rollup: list[dict[str, str]]) -> str:
    """failing if any check failed, pending if any is unfinished, else passing (skipped is passing)."""
    if any((c.get("conclusion") or c.get("state")) in FAILED for c in rollup):
        return "failing"
    done = all(c.get("status") == "COMPLETED" or c.get("state") == "SUCCESS" for c in rollup)
    return "passing" if done else "pending"


def claude_active() -> bool:
    for status in ("in_progress", "queued"):
        runs = json.loads(
            _gh("run", "list", "--workflow", "claude.yml", "--status", status, "--json", "databaseId")
        )
        if runs:
            return True
    return False


def staging_is_green() -> bool:
    runs = json.loads(
        _gh(
            "run",
            "list",
            "--workflow",
            "ci.yml",
            "--branch",
            "staging",
            "--event",
            "push",
            "--limit",
            "1",
            "--json",
            "conclusion,status",
        )
    )
    return not runs or runs[0]["conclusion"] != "failure"


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
        Pr(r["number"], r["headRefName"], _ts(r["updatedAt"]), r["title"], _checks(r["statusCheckRollup"]))
        for r in json.loads(
            _gh(
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,headRefName,updatedAt,title,statusCheckRollup",
            )
        )
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
            "cause, comment `/retry` and remove the `blocked` label to allow new attempts.",
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
        claude_running=claude_active(),
        staging_green=staging_is_green(),
    )
    print(json.dumps({"action": d.action, "issue": d.issue, "reason": d.reason, "attempt": d.attempt}))
    if args.apply and d.action != "idle":
        apply(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
