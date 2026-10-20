import pytest
from changed_paths import classify, docs_only


@pytest.mark.parametrize(
    "files",
    [
        ["README.md"],
        ["docs/STATUS.md", ".agent/rules/delivery.md"],
        ["design/v2/main-view.html", "CHANGELOG.md"],
    ],
)
def test_documentation_only(files: list[str]) -> None:
    assert docs_only(files)


@pytest.mark.parametrize(
    "files",
    [
        [],  # empty diff or unknown: run everything
        ["docs/openapi.json"],  # read by a drift test
        ["README.md", "scripts/x.py"],
        [".github/workflows/ci.yml"],
        ["pyproject.toml"],
        ["docs/STATUS.md", "uv.lock"],
        ["migrations/versions/0007.py"],
        ["tests/engine/golden/leszno_with_vision.md"],  # read by test_golden as expected output
        ["apps/deal_analyzer/README.md"],
        ["services/rm_api/NOTES.md", "README.md"],
    ],
)
def test_anything_else_runs_the_full_pipeline(files: list[str]) -> None:
    assert not docs_only(files)


def stages(files: list[str] | None) -> tuple[bool, bool, bool, bool]:
    s = classify(files)
    return s.docs_only, s.python, s.frontend, s.journey


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        # documentation: nothing runs
        (["README.md", "docs/STATUS.md"], (True, False, False, False)),
        (["design/v2/main-view.html"], (True, False, False, False)),
        # SPA only: no Python stages, SPA stages and the journey lane run
        (["frontend/features/market/LocationPage.tsx"], (False, False, True, True)),
        (["frontend/README.md"], (False, False, True, True)),  # Prettier checks it
        (["frontend/docs/AUDIT.md", "docs/STATUS.md"], (False, False, True, True)),
        # backend only: no SPA check, no mocked lane, no visual lane; the journey lane runs the real stack
        (["services/rm_api/market.py", "tests/unit/test_x.py"], (False, True, False, True)),
        (["packages/rm_core/market_history.py"], (False, True, False, True)),
        (["migrations/versions/0021_x.py"], (False, True, False, True)),
        (["uv.lock", "pyproject.toml"], (False, True, False, True)),
        # tests, scripts and tooling are Python work and cannot change the SPA or the stack
        (["tests/integration/test_audit_list.py"], (False, True, False, False)),
        (["scripts/changed_paths.py"], (False, True, False, False)),
        (["docs/BLUEPRINT.md", "tests/tooling/test_changed_paths.py"], (False, True, False, False)),
        # the contract the SPA's generated types come from is read by both sides
        (["docs/openapi.json"], (False, True, True, False)),
        (["docs/deal-analysis.schema.json"], (False, True, True, False)),
        (["scripts/e2e_session.py"], (False, True, False, True)),
        # a mixed change runs the union
        (["frontend/ui/Button.tsx", "services/rm_api/auth.py"], (False, True, True, True)),
        # workflows run everything
        ([".github/workflows/ci.yml"], (False, True, True, True)),
    ],
)
def test_each_stage_group_runs_only_for_the_paths_it_can_depend_on(
    files: list[str], expected: tuple[bool, bool, bool, bool]
) -> None:
    assert stages(files) == expected


@pytest.mark.parametrize("files", [None, []])
def test_unknown_or_empty_diff_runs_everything_but_is_not_docs(files: list[str] | None) -> None:
    assert stages(files) == (False, True, True, True)


def test_output_lines_are_github_outputs() -> None:
    assert classify(["frontend/a.ts"]).lines() == [
        "docs_only=false",
        "python=false",
        "frontend=true",
        "journey=true",
    ]
