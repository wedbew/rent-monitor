"""The local pipeline (`scripts/ci_local.sh`) must stay in step with `.github/workflows/`."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_invariants import REQUIRED, missing  # noqa: E402

CI = (ROOT / ".github/workflows/ci.yml").read_text()
SECURITY = (ROOT / ".github/workflows/security.yml").read_text()
SCRIPT = (ROOT / "scripts/ci_local.sh").read_text()


def test_the_required_invariants_match_the_ci_job_exactly() -> None:
    block = re.search(r"required = \{(.*?)\}", CI, re.DOTALL)
    assert block is not None
    in_ci = set(re.findall(r'"(test_invariant_[a-z0-9_]+)"', block.group(1)))
    assert in_ci == set(REQUIRED), "update scripts/check_invariants.py and .github/workflows/ci.yml together"


def _junit(*cases: tuple[str, str]) -> str:
    body = "".join(
        f'<testcase classname="t" name="{name}">{"" if state == "pass" else f"<{state}/>"}</testcase>' for name, state in cases
    )
    return f'<testsuites><testsuite name="x">{body}</testsuite></testsuites>'


def test_the_checker_passes_only_when_every_required_test_passed(tmp_path: Path) -> None:
    ok = tmp_path / "ok.xml"
    ok.write_text(_junit(*[(f"{n}[param]", "pass") for n in REQUIRED]))
    assert missing(str(ok)) == []
    gone = tmp_path / "gone.xml"
    gone.write_text(_junit(*[(n, "pass") for n in sorted(REQUIRED)[1:]]))
    assert missing(str(gone)) == [sorted(REQUIRED)[0]]


@pytest.mark.parametrize("state", ["skipped", "failure", "error"])
def test_a_skipped_or_failing_invariant_counts_as_missing(tmp_path: Path, state: str) -> None:
    victim = sorted(REQUIRED)[0]
    path = tmp_path / "x.xml"
    path.write_text(_junit((victim, state), *[(n, "pass") for n in sorted(REQUIRED)[1:]]))
    assert missing(str(path)) == [victim]


def test_every_ci_job_and_security_step_has_a_local_counterpart() -> None:
    for job in ("lint", "types", "migrations", "invariants"):
        assert re.search(rf"^  {job}:", CI, re.MULTILINE), job
        assert f"st_{job}" in SCRIPT
    assert "ty check packages services" in SCRIPT  # types-ty-trial
    assert "pytest -m \"not e2e\" --cov" in SCRIPT  # test
    for tool in ("gitleaks", "pip-audit", "semgrep", "zizmor", "actionlint"):
        assert tool in SECURITY
        assert tool in SCRIPT
    assert "check_commit_msg.py --range" in SCRIPT  # pr-title: every commit is ticket-tagged
    assert "squawk" in SCRIPT


def test_the_script_is_valid_bash_and_documents_its_modes() -> None:
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts/ci_local.sh")], check=False).returncode == 0  # noqa: S603, S607
    help_text = subprocess.run(  # noqa: S603
        [str(ROOT / "scripts/ci_local.sh"), "--help"], capture_output=True, text=True, check=False
    )
    assert help_text.returncode == 0
    for flag in ("--fast", "--full", "--only"):
        assert flag in help_text.stdout


def test_the_pre_push_hook_runs_the_fast_pipeline() -> None:
    config = (ROOT / ".pre-commit-config.yaml").read_text()
    assert "pre-push" in config
    assert "./scripts/ci_local.sh --fast" in config
