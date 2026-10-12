import pytest
from changed_paths import docs_only


@pytest.mark.parametrize(
    "files",
    [["README.md"], ["docs/STATUS.md", ".agent/rules/delivery.md"], ["design/v2/main-view.html", "CHANGELOG.md"]],
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
    ],
)
def test_anything_else_runs_the_full_pipeline(files: list[str]) -> None:
    assert not docs_only(files)
