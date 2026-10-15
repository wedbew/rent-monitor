from delivery_metrics import percentile, summarise, timing


def pr(created: str, merged: str | None, *checks: tuple[str, str]) -> dict:
    return {
        "number": 1,
        "title": "t",
        "createdAt": created,
        "mergedAt": merged,
        "commits": [{"committedDate": c, "messageHeadline": h} for c, h in checks],
    }


def test_splits_open_to_last_commit_from_last_commit_to_merge() -> None:
    t = timing(pr("2026-10-13T10:00:00Z", "2026-10-13T11:00:00Z", ("2026-10-13T10:10:00Z", "feat: a"), ("2026-10-13T10:20:00Z", "fix: b"), ("2026-10-13T10:50:00Z", "Merge branch staging")))
    assert t is not None
    assert (t.calendar_s, t.open_to_last_commit_s, t.last_commit_to_merge_s) == (3600, 1200, 2400)


def test_unmerged_and_commit_less_prs() -> None:
    assert timing(pr("2026-10-13T10:00:00Z", None)) is None
    t = timing(pr("2026-10-13T10:00:00Z", "2026-10-13T10:05:00Z"))
    assert t is not None
    assert (t.open_to_last_commit_s, t.last_commit_to_merge_s) == (None, None)


def test_percentile_is_nearest_rank() -> None:
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9
    assert summarise([])  == {}
