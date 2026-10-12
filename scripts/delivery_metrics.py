"""Delivery timing per merged PR, from GitHub (ADR 0012). Read-only.

*calendar* = PR created to merged. *work* = created to the last non-merge commit pushed (editing, local
checks, fixes). *wait* = that commit to merged (CI, review, owner approval, queueing). Work done before the PR
was opened is not visible, and CI plus approval cannot be separated from the data GitHub keeps; a long *wait*
on a PR that needed approval is the approval wait. Not billed minutes.

    uv run python scripts/delivery_metrics.py [--limit 100] [--since 2026-10-13]
"""

import argparse
import json
import math
import statistics
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class PrTiming:
    number: int
    title: str
    calendar_s: float
    work_s: float | None
    wait_s: float | None


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def timing(pr: dict) -> PrTiming | None:
    if not pr.get("mergedAt"):
        return None
    created, merged = _ts(pr["createdAt"]), _ts(pr["mergedAt"])
    pushed = [
        _ts(c["committedDate"])
        for c in pr.get("commits") or []
        if not c["messageHeadline"].startswith("Merge")
    ]
    last = max(pushed) if pushed else None
    work = max(0.0, (last - created).total_seconds()) if last else None
    wait = max(0.0, (merged - max(last, created)).total_seconds()) if last else None
    return PrTiming(pr["number"], pr["title"], (merged - created).total_seconds(), work, wait)


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def summarise(rows: list[PrTiming]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for name in ("calendar_s", "work_s", "wait_s"):
        vals = [v for r in rows if (v := getattr(r, name)) is not None]
        if vals:
            out[name] = {
                "n": len(vals),
                "median_min": statistics.median(vals) / 60,
                "p90_min": percentile(vals, 0.9) / 60,
                "max_min": max(vals) / 60,
                "total_h": sum(vals) / 3600,
            }
    return out


PAGE = 40  # GitHub's GraphQL node limit rejects more PRs with their commits per query


def fetch(limit: int) -> list[dict]:
    """Merged PRs, newest first, paged by creation time because `gh pr list` cannot take an offset."""
    out: list[dict] = []
    before = ""
    while len(out) < limit:
        cmd = ["gh", "pr", "list", "--state", "merged", "--limit", str(min(PAGE, limit - len(out)))]
        cmd += ["--json", "number,title,createdAt,mergedAt,commits"]
        if before:
            cmd += ["--search", f"sort:created-desc created:<{before}"]
        page = json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)  # noqa: S603
        if not page:
            break
        out += page
        before = min(p["createdAt"] for p in page)
    return out[:limit]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--since", help="ISO date; only PRs merged on or after it")
    args = ap.parse_args(argv)
    raw = fetch(args.limit)
    since = datetime.fromisoformat(args.since).replace(tzinfo=UTC) if args.since else None
    rows = [t for pr in raw if (t := timing(pr)) and (since is None or _ts(pr["mergedAt"]) >= since)]
    print(json.dumps({"prs": len(rows), **summarise(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
