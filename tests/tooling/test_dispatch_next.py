from datetime import UTC, datetime, timedelta

from dispatch_next import MARKER, RETRY, Decision, Issue, Pr, _checks, decide, depends_on

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def issue(n: int, *labels: str, body: str = "", ago: int = 5, comments: tuple[str, ...] = ()) -> Issue:
    return Issue(n, f"t{n}", frozenset(labels), body, NOW - timedelta(minutes=ago), comments)


def test_depends_on_parses_only_the_depends_line() -> None:
    body = "see #99\nDepends on: #3, #4 (merged)\nFiles: a.py"
    assert depends_on(body) == [3, 4]
    assert depends_on("Depends on: none") == []
    assert depends_on("no line #7") == []


def test_dispatches_first_ready_issue_with_dependencies_closed() -> None:
    issues = [issue(5, "ready", body="Depends on: #2"), issue(6, "ready", body="Depends on: none")]
    assert decide(issues, {2}, [], NOW) == Decision("dispatch", 5, "first ready issue (P1)", attempt=1)
    assert decide(issues, set(), [], NOW).issue == 6  # #5 waits on an open #2


def test_priority_beats_number() -> None:
    issues = [issue(5, "ready", body="Priority: P1"), issue(9, "ready", body="Priority: P0")]
    assert decide(issues, set(), [], NOW).issue == 9


def test_never_dispatches_blocked_umbrella_owner_or_unlabelled() -> None:
    issues = [
        issue(1, "ready", "blocked"),
        issue(2, "ready", "umbrella"),
        issue(3, "ready", "owner"),
        issue(4),
    ]
    assert decide(issues, set(), [], NOW).action == "idle"


def test_one_in_flight_issue_means_idle() -> None:
    issues = [issue(7, "agent", ago=10), issue(8, "ready")]
    d = decide(issues, set(), [], NOW)
    assert (d.action, d.issue) == ("idle", 7)


def test_pr_activity_counts_as_activity() -> None:
    issues = [issue(7, "agent", ago=300)]
    prs = [Pr(70, "rm-7-thing", NOW - timedelta(minutes=3))]
    assert decide(issues, set(), prs, NOW).action == "idle"


def test_stale_issue_resumes_then_blocks_and_is_not_retried() -> None:
    d1 = decide([issue(7, "agent", ago=300)], set(), [], NOW)
    assert (d1.action, d1.attempt) == ("resume", 1)
    one = (f"{MARKER}1 -->",)
    assert decide([issue(7, "agent", ago=300, comments=one)], set(), [], NOW).attempt == 2
    two = (f"{MARKER}1 -->", f"{MARKER}2 -->")
    assert decide([issue(7, "agent", ago=300, comments=two)], set(), [], NOW).action == "block"
    # once blocked (label), the same issue is neither resumed nor re-dispatched
    assert decide([issue(7, "ready", "blocked", comments=two)], set(), [], NOW).action == "idle"


def test_exhausted_attempts_are_not_redispatched() -> None:
    two = (f"{MARKER}1 -->", f"{MARKER}2 -->")
    assert decide([issue(7, "ready", comments=two)], set(), [], NOW).action == "idle"


def test_a_pr_awaiting_approval_is_never_resumed_or_blocked() -> None:
    prs = [Pr(70, "rm-7-thing", NOW - timedelta(hours=9), "feat(RM-7): x", "passing")]
    d = decide([issue(7, "agent", ago=600, comments=(f"{MARKER}1 -->", f"{MARKER}2 -->"))], set(), prs, NOW)
    assert (d.action, d.issue) == ("idle", 7)
    assert "approval" in d.reason


def test_running_checks_are_not_stalled_work() -> None:
    prs = [Pr(70, "rm-7-thing", NOW - timedelta(hours=9), "", "pending")]
    assert decide([issue(7, "agent", ago=600)], set(), prs, NOW).action == "idle"


def test_failing_checks_resume_only_when_idle_and_then_block() -> None:
    old = [Pr(70, "rm-7-thing", NOW - timedelta(hours=3), "", "failing")]
    assert decide([issue(7, "agent", ago=200)], set(), old, NOW).action == "resume"
    fresh = [Pr(70, "rm-7-thing", NOW - timedelta(minutes=5), "", "failing")]
    assert decide([issue(7, "agent", ago=200)], set(), fresh, NOW).action == "idle"
    two = (f"{MARKER}1 -->", f"{MARKER}2 -->")
    assert decide([issue(7, "agent", ago=200, comments=two)], set(), old, NOW).action == "block"


def test_a_pr_without_the_agent_label_still_counts_as_in_flight() -> None:
    issues = [issue(7, "in-progress"), issue(8, "ready")]
    by_branch = [Pr(70, "rm-7-thing", NOW, "", "passing")]
    by_title = [Pr(71, "somebranch", NOW, "feat(RM-7): thing", "passing")]
    for prs in (by_branch, by_title):
        d = decide(issues, set(), prs, NOW)
        assert (d.action, d.issue) == ("idle", 7)


def test_retry_resets_the_attempt_count_after_a_block() -> None:
    two = (f"{MARKER}1 -->", f"{MARKER}2 -->")
    assert decide([issue(7, "ready", comments=two)], set(), [], NOW).action == "idle"
    after = (*two, f"{RETRY} the secret is fixed")
    d = decide([issue(7, "ready", comments=after)], set(), [], NOW)
    assert (d.action, d.issue, d.attempt) == ("dispatch", 7, 1)
    # only /retry resets: a later attempt after it counts again
    again = (*after, f"{MARKER}1 -->", f"{MARKER}2 -->")
    assert decide([issue(7, "ready", comments=again)], set(), [], NOW).action == "idle"


def test_nothing_new_starts_while_claude_runs_or_staging_is_red() -> None:
    issues = [issue(8, "ready")]
    assert decide(issues, set(), [], NOW, claude_running=True).action == "idle"
    d = decide(issues, set(), [], NOW, staging_green=False)
    assert (d.action, "staging" in d.reason) == ("idle", True)
    assert decide(issues, set(), [], NOW).action == "dispatch"


def test_check_rollup_states() -> None:
    ok = {"status": "COMPLETED", "conclusion": "SUCCESS"}
    skipped = {"status": "COMPLETED", "conclusion": "SKIPPED"}
    assert _checks([ok, skipped]) == "passing"
    assert _checks([ok, {"status": "IN_PROGRESS", "conclusion": ""}]) == "pending"
    assert _checks([ok, {"status": "COMPLETED", "conclusion": "FAILURE"}]) == "failing"
    assert _checks([{"state": "SUCCESS"}]) == "passing"
