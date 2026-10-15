"""The scenario registry covers the whole API contract (#263 acceptance 1 and 6). No database needed."""

import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from contract import load_spec, operations
from scenarios import PUBLIC, all_scenarios

ROOT = Path(__file__).resolve().parents[2]


def provoked_elsewhere(status: str, response: dict[str, Any]) -> bool:
    """Statuses a scenario cannot sensibly provoke on every operation: a crash (500), the database being
    away (503 NOT_READY alone) and rate limits (429, whose windows differ per route; the limited routes with
    scenarios are in test_api_smoke and every 429 that does happen is checked against the document)."""
    codes = set(response.get("x-problem-codes", []))
    return status in {"500", "429"} or (status == "503" and codes == {"NOT_READY"})


def test_every_operation_has_a_scenario() -> None:
    """Adding a route without a smoke scenario fails here: one success, one per documented error status, and
    a 401 for every route behind a session."""
    ops = operations(load_spec())
    by_key: dict[str, set[int]] = {}
    for s in all_scenarios():
        by_key.setdefault(s.key, set()).add(s.status)
    missing: list[str] = []
    for key, op in ops.items():
        have = by_key.get(key, set())
        if not any(200 <= status < 300 for status in have):
            missing.append(f"{key}: no success scenario")
        for documented, response in op.responses.items():
            if documented.startswith("2") or provoked_elsewhere(documented, response):
                continue
            if int(documented) not in have:
                missing.append(f"{key}: no scenario for documented {documented}")
        if key not in PUBLIC and 401 not in have:
            missing.append(f"{key}: no 401 scenario")
    assert missing == []


def test_no_scenario_points_at_a_removed_operation() -> None:
    ops = operations(load_spec())
    assert sorted({s.key for s in all_scenarios() if s.key not in ops}) == []


def test_scenario_ids_are_unique() -> None:
    ids = Counter(s.id for s in all_scenarios())
    assert [i for i, n in ids.items() if n > 1] == []


def test_there_are_five_distinct_succeeded_audit_scenarios() -> None:
    names = [s.name for s in all_scenarios() if s.key == "GET /api/audits/{audit_id}"]
    assert len([n for n in names if n.startswith("succeeded_") and n != "succeeded_degraded"]) >= 5


def test_samples_dir_is_gitignored() -> None:
    """Captured samples can hold third-party listing text: `data/` must never be committed."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", "data/api-samples/x"],  # noqa: S607
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0, "data/api-samples/ is not ignored by .gitignore"
